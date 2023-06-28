from django import forms
from mytxs.utils.formUtils import callForEveryForm

from mytxs.utils.modelUtils import toolTip

# Alt relatert til om forms e hidden og disabled

def fieldIsVisible(field):
    return not(isinstance(field.widget, forms.HiddenInput) or isinstance(field.widget, forms.MultipleHiddenInput))

def formIsEnabled(form):
    'Returne true om det e minst ett felt som ikke e disabled i formet/formsettet'
    if hasattr(form, 'forms') and form.forms != None:
        return any(map(lambda form: formIsEnabled(form), form.forms))

    return any(map(lambda field: not field.disabled and fieldIsVisible(field), form.fields.values()))

def formIsVisible(form):
    'Returne true om det e minst ett felt som ikke e invisible i formet'
    if hasattr(form, 'forms') and form.forms != None:
        return any(map(lambda form: formIsVisible(form), form.forms))

    return any(map(lambda field: fieldIsVisible(field), form.fields.values()))

def hideFields(form, *fieldNames):
    if callForEveryForm(hideFields, form, *fieldNames):
        return
    
    if not fieldNames:
        fieldNames = form.fields.keys()

    for fieldName in fieldNames:
        form.fields[fieldName].widget = form.fields[fieldName].hidden_widget()

def hideDisabledFields(form):
    if callForEveryForm(hideDisabledFields, form):
        return
    
    if not formIsEnabled(form):
        hideFields(form)

def disableFields(form, *fieldNames, helpText=None):
    if callForEveryForm(disableFields, form, *fieldNames, helpText=helpText):
        return

    for fieldName in fieldNames:
        form.fields[fieldName].disabled = True

        if helpText:
            form.fields[fieldName].help_text = toolTip(helpText)

        # Fjern unødvendige alternativ når en dropdown e disabled (funke pr no bare for ModelChoiceField, 
        # fordi e ikkje klare å skaff selected option fra et vanlig form)
        if hasattr(form, 'instance') and hasattr(form.fields[fieldName], 'queryset') and len(form.fields[fieldName].queryset) > 0:
            if hasattr(form.instance, fieldName) and getattr(form.instance, fieldName) != None and hasattr(getattr(form.instance, fieldName), 'pk'):
                form.fields[fieldName].queryset = form.fields[fieldName].queryset.filter(pk=getattr(form.instance, fieldName).pk)
            else:
                form.fields[fieldName].queryset = form.fields[fieldName].queryset.none()
            # print(f'{fieldName} {hasattr(form, 'instance')} {hasattr(form.fields[fieldName], 'queryset')} {len(form.fields[fieldName].queryset)}')

def disableForm(form):
    '''
    Disable alle fields i formet (untatt id, for da funke det ikkje på modelformsets)
    Funke på forms og formsets. 
    '''
    if callForEveryForm(disableForm, form):
        return
    
    for name, field in form.fields.items():
        if name == 'DELETE':
            form.fields['DELETE'].disabled = True
            field.widget = field.hidden_widget()
        elif fieldIsVisible(field):
            disableFields(form, name)

def partiallyDisableFormset(formset, queryset, fieldNavn):
    'Sett queryset og disable forms som ikke er i det'
    if not queryset.exists():
        formset.extra = 0

    for form in formset.forms:
        if form.instance.pk and getattr(form.instance, fieldNavn) not in queryset:
            # Om de ikke har tilgang: Disable formet
            disableForm(form)
        else:
            # Om de har tilgang: Begrens verdiene de kan velge. 
            form.fields[fieldNavn].queryset = queryset.distinct()

def partiallyDisableFormsetKor(formset, korMedTilgang, fieldNavn):
    'Disable fields som ikke tilhører et kor brukeren har den tilgangen i'
    if not korMedTilgang.exists():
        formset.extra = 0

    for form in formset.forms:
        if form.instance.pk and getattr(form.instance, fieldNavn).kor not in korMedTilgang:
            disableForm(form)
        else:
            form.fields[fieldNavn].queryset = form.fields[fieldNavn].queryset.filter(kor__in=korMedTilgang)

def setRequiredDropdownOptions(form, fieldNavn, korMedTilgang):
    'Set options for dropdown, og disable formet dersom det er ingen options'

    if callForEveryForm(setRequiredDropdownOptions, form, fieldNavn, korMedTilgang):
        return

    if form.fields[fieldNavn].queryset.model.__name__ == 'Kor':
        # Dropdownen har queryset av kor modellen
        if form.instance.pk and not getattr(form.instance, fieldNavn) in korMedTilgang:
            # Om vi ikke har tilgang til selected option
            disableForm(form)
            return
        else:
            # Om vi har tilgang til selected option
            form.fields[fieldNavn].queryset = korMedTilgang.distinct()
    else:
        # Dropdownen har queryset av en model med fk til kor modellen
        if form.instance.pk and not getattr(form.instance, fieldNavn).kor in korMedTilgang:
            # Om vi ikke har tilgang til selected option
            disableForm(form)
            return
        else:
            # Om vi har tilgang til selected option
            form.fields[fieldNavn].queryset = form.fields[fieldNavn].queryset.filter(kor__in=korMedTilgang)
    
    if not form.fields[fieldNavn].queryset.exists():
        disableForm(form)
