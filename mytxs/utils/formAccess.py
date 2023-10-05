from django import forms
from mytxs.utils.formUtils import addHelpText, formsetToForm
from mytxs.utils.modelUtils import getSourceM2MModel

# Alt relatert til om forms e hidden og disabled

def fieldIsVisible(field):
    return not(isinstance(field.widget, forms.HiddenInput) or isinstance(field.widget, forms.MultipleHiddenInput))


def formIsEnabled(form):
    'Returne true om det e minst ett felt som ikke e disabled i formet/formsettet'
    if isinstance(form, forms.BaseFormSet):
        return any(map(lambda form: formIsEnabled(form), form.forms))

    return any(map(lambda field: not field.disabled and fieldIsVisible(field), form.fields.values()))


def formIsVisible(form):
    'Returne true om det e minst ett felt som ikke e invisible i formet'
    if isinstance(form, forms.BaseFormSet):
        return any(map(lambda form: formIsVisible(form), form.forms))

    return any(map(lambda field: fieldIsVisible(field), form.fields.values()))


@formsetToForm
def removeFields(form, *fieldNames):
    'Fjerne fields fra formet'
    for fieldName in fieldNames:
        if fieldName in form.fields.keys():
            del form.fields[fieldName]


@formsetToForm
def hideFields(form, *fieldNames):
    if not fieldNames:
        fieldNames = form.fields.keys()

    for fieldName in fieldNames:
        form.fields[fieldName].widget = form.fields[fieldName].hidden_widget()


@formsetToForm
def hideDisabledFields(form):
    if not formIsEnabled(form):
        hideFields(form)


@formsetToForm
def disableFields(form, *fieldNames, helpText=None):
    '''
    Disable fields ved navn fieldNames på formet/formsetettet.
    Om fieldNames er tom vil den kjøre på alle synlige fields. 
    helpText er om man vil legge til en forklaring for hvorfor fields er disabled. 
    '''
    if not fieldNames:
        fieldNames = list(map(lambda f: f.name, form.visible_fields()))
    
    if helpText:
        addHelpText(form, *fieldNames, helpText=helpText)

    for fieldName in fieldNames:
        form.fields[fieldName].disabled = True

        # Dersom det e en dropdown
        if isinstance(form.fields[fieldName], forms.ModelChoiceField) and fieldIsVisible(form.fields[fieldName]):
            if getattr(getattr(form, 'instance', None), 'pk', None) != None:
                if isinstance(form.fields[fieldName], forms.ModelMultipleChoiceField):
                    # Om det e en multiselect, vis selected options
                    form.fields[fieldName].queryset = getattr(form.instance, fieldName).distinct()
                else:
                    # Om det e en select, vis selected option
                    form.fields[fieldName].queryset = form.fields[fieldName].queryset.filter(pk=getattr(form.instance, fieldName).pk)
            else:
                # Om det ikkje har en instance, bare fjern alle options
                form.fields[fieldName].queryset = form.fields[fieldName].queryset.none()


def disableFormMedlem(medlem, form):
    '''
    Disable et form/formset basert på medlemmets tilganger. Returne en boolean som sie om noen fields 
    ikkje e disabled, som burde brukes for å sjekk om vi treng å disable fleir fields.

    Ved å ha denne funksjonen, selv med litt sammensatt logikk for relaterte fields, spare vi å prøv å implementer
    samme tilgang logikk på tvers av alle views, og kan heller bare si 'disableFormMedlem(request.user.medlem, form)', og
    dersom den returne true (og det er felt som man har tilgang til), kan vi apply ekstra view-specific logikk der.
    Dette gjør kodebasen veldig my mere bærekraftig/ryddig, og er følgelig utrolig viktig for hele siden. 
    '''

    # Om det e et formset
    if isinstance(form, forms.BaseFormSet):
        # Dersom vi har brukt viewUtils.py sin extendedRedigerTilgangQueryset så må vi sett includeExtended til false.
        includeExtendedKwarg = {}
        if 'includeExtended' in medlem.redigerTilgangQueryset.__code__.co_varnames:
            includeExtendedKwarg['includeExtended'] = False

        # Om det e et inlineFormset kan vi bare sjekk om vi har tilgang til form.instance, og om ikke fjern extra:)
        if isinstance(form, forms.BaseInlineFormSet) and not medlem.redigerTilgangQueryset(form.queryset.model, type(form.instance), fieldType=forms.ModelChoiceField, **includeExtendedKwarg).contains(form.instance):
            form.extra = 0
            disableFields(form)
            return False

        # Ellers, gå gjennom instance for instance
        anyNotDisabled = False
        for formet in form.forms:
            if disableFormMedlem(medlem, formet):
                anyNotDisabled = True
            # Dette vedde e ka enn på at burda funk istedet her, virke som python cache resultatet og optimalisere det bort: 
            # anyNotDisabled = anyNotDisabled or disableFormMedlem(medlem, formet)
        return anyNotDisabled
    
    # Herunder har vi et form (ikke et formset)

    # Om vi ikke har tilgang til form.instance
    if not medlem.harRedigerTilgang(form.instance):
        # Disable alle visible fields untatt m2m fields
        for fieldName, field in form.fields.items():
            if not isinstance(field, forms.ModelMultipleChoiceField) and fieldIsVisible(field):
                disableFields(form, fieldName)
    
    # Om vi har tilgang til form.instance, sett queryset av ModelChoiceFields, 
    # evt med disabled options for ModelMultipleChoiceField
    for fieldName, field in form.fields.items():
        if field.disabled or not fieldIsVisible(field):
            continue

        if isinstance(field, forms.ModelMultipleChoiceField):
            # Dette e litt innvikla fordi det skal fungere på begge sider av alle m2m relasjoner, med og uten tversAvKor 
            # tilgangen. Målet er at du skal kunne opprette og slette m2m relasjoner mellom 2 ting du har tilgang til.
            # (Tilgang betyr her at vi får form.instance opp som et alternativ på motsatt side). 
            
            # Skaff modellen som styre vår tilgang til dette feltet
            tilgangModel = getSourceM2MModel(type(form.instance), fieldName)

            # Skaff options du kan redigere
            tilgangQueryset = medlem.redigerTilgangQueryset(tilgangModel, field.queryset.model, fieldType=forms.ModelMultipleChoiceField)

            # Dersom form.instance er i tilgangQuerysett på den andre siden 
            # (type(form.instance) og field.queryset.model vil være de 2 ulike sidene av relasjonen)
            # (vi anntar her at vi aldri har m2mFelt på forms uten lagret instance, f.eks. i tomme forms på inlineformset)
            if medlem.redigerTilgangQueryset(tilgangModel, type(form.instance), fieldType=forms.ModelMultipleChoiceField).contains(form.instance):
                # Vis selected options + options du har tilgang til, og enable options du har tilgang til
                field.queryset = getattr(form.instance, fieldName).distinct() | tilgangQueryset.distinct()
                field.setEnableQueryset(tilgangQueryset, getattr(form.instance, fieldName))
            else:
                # Ellers bare disable fieldet
                disableFields(form, fieldName)

        elif isinstance(field, forms.ModelChoiceField):
            # Sett querysettet til det du har tilgang til. 
            tilgangQueryset = medlem.redigerTilgangQueryset(type(form.instance), field.queryset.model, fieldType=forms.ModelChoiceField)

            # Om du ikke har tilgang til selected option, disable feltet
            # Dette for å sikre at queryset ikke varierer mellom ulike forms i formsettet, se lazyDropdown.py
            if form.instance.pk and not tilgangQueryset.contains(getattr(form.instance, fieldName)):
                disableFields(form, fieldName)
            else:
                field.queryset = tilgangQueryset.distinct()
        
        # Om vi har ingen options, disable feltet
        if isinstance(field, forms.ModelChoiceField) and not field.queryset.exists():
            disableFields(form, fieldName)

    return any(map(lambda field: not field.disabled, form.fields.values()))


def disableBrukt(form):
    'Hjelpefunksjon som sjekke form.instance.bruktIKode og følgelig kjøre disableFields på navn og DELETE'
    if form.instance.bruktIKode:
        disableFields(form, 'navn', 'DELETE', helpText='Selv ikke de med tilgang kan endre på noe som er brukt i kode')
