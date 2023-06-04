from django import forms
from mytxs.fields import MyModelMultipleChoiceField

from mytxs.utils.modelUtils import toolTip

def disableFormField(form, *fieldNames, helpText=False):
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
            # print(f'{fieldName} {hasattr(form, "instance")} {hasattr(form.fields[fieldName], "queryset")} {len(form.fields[fieldName].queryset)}')

def disableForm(form):
    """ Disable alle fields i formet (untatt id, for da funke det ikkje på modelformsets)
        Funke på forms og formsets. 
    """

    if hasattr(form, 'forms') and form.forms != None:
        for formet in form.forms:
            disableForm(formet)
    else:
        for name, field in form.fields.items():
            if name not in ['id', 'TOTAL_FORMS', 'INITIAL_FORMS']:
                disableFormField(form, name)

def partiallyDisableFormset(formset, korMedTilgang, fieldNavn):
    """Disable fields som ikke tilhører et kor brukeren har den tilgangen i"""
    for form in formset.forms:
        # if det ikkje e et nytt felt, og det e en vervinnehavelse brukeren ikke har lov til å endre på
        if form.instance.pk is not None and not getattr(form.instance, fieldNavn).kor in korMedTilgang:
            # Det eneste alternativet skal være det vervet som er der
            #form.fields[fieldNavn].queryset = form.fields[fieldNavn].queryset.filter(pk=getattr(form.instance, fieldNavn).pk)
            disableForm(form)
        else:
            # Bare la brukeren velge blant verv de har tilgang til å kan endre på
            form.fields[fieldNavn].queryset = form.fields[fieldNavn].queryset.filter(kor__in=korMedTilgang)
            if form.instance.pk is None and not korMedTilgang.exists():
                disableForm(form)

def setRequiredDropdownOptions(form, field, korMedTilgang):
    "Set options for dropdown, og disable formet dersom det er ingen options"

    if form.fields[field].queryset.model._meta.model_name == 'kor':
        form.fields[field].queryset = korMedTilgang
    else:
        form.fields[field].queryset = form.fields[field].queryset\
            .filter(kor__in=korMedTilgang)
    
    if not form.fields[field].queryset.exists():
        disableForm(form)

def addReverseM2M(ModelForm, related_name):
    """Utility funksjon for å hiv på reverse relaterte M2M relasjoner"""

    relatedModel = getattr(ModelForm._meta.model, related_name).rel.related_model

    # Mesteparten av dette kjem herifra: https://stackoverflow.com/a/53859922/6709450
    class NewForm(ModelForm):
        # Triksete løsning hentet herifra: https://stackoverflow.com/a/20608050/6709450
        vars()[related_name] = MyModelMultipleChoiceField(
            queryset=relatedModel.objects.all(),
            required=False,
        )

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.fields[related_name].initial = getattr(self.instance, related_name).all().values_list('id', flat=True)

        def save(self, *args, **kwargs):
            instance = super().save(*args, **kwargs)
            getattr(instance, related_name).set(self.cleaned_data[related_name])
            return instance

    return NewForm

def addDeleteCheckbox(ModelForm):
    """ Legg til en delte checkbox og at når modelform.save kjøre slettes instansen.
        Boolean verdien kan aksesseres etter is_valid() via form.cleaned_data['delete'].
    """
    class NewForm(ModelForm):
        delete = forms.BooleanField(label="Slett", required=False)

        def save(self, commit=True):
            if self.cleaned_data['delete']:
                return self.instance.delete()
            return super().save()
    
    return NewForm

def prefixPresent(POST, prefix):
    """
    Utility funksjon for å bare gi POST til modelforms som har relevante keys. 
    Må brukes på sider som har fleire forms for å oppnå korrekt form error handling
    På sider som har bare ett form er 'request.POST or None' akseptabelt
    """
    if any([key.startswith(prefix) for key in POST.keys()]):
        return POST
    else:
        return None