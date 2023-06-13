from django import forms

from mytxs.utils.modelUtils import toolTip

# Alt relatert til om forms e hidden og disabled

def fieldIsVisible(field):
    return not(isinstance(field.widget, forms.HiddenInput) or isinstance(field.widget, forms.MultipleHiddenInput))

def disableFormField(form, *fieldNames, helpText=None):
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
        return
    
    for name, field in form.fields.items():
        if name == 'DELETE':
            form.fields['DELETE'].disabled = True
            field.widget = field.hidden_widget()
        elif fieldIsVisible(field):
            disableFormField(form, name)

def partiallyDisableFormset(formset, queryset, fieldNavn):
    """Sett queryset og disable forms som ikke er i det."""
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
    """Disable fields som ikke tilhører et kor brukeren har den tilgangen i"""
    if not korMedTilgang.exists():
        formset.extra = 0

    for form in formset.forms:
        if form.instance.pk and getattr(form.instance, fieldNavn).kor not in korMedTilgang:
            disableForm(form)
        else:
            form.fields[fieldNavn].queryset = form.fields[fieldNavn].queryset.filter(kor__in=korMedTilgang)

def setRequiredDropdownOptions(form, field, korMedTilgang):
    "Set options for dropdown, og disable formet dersom det er ingen options"

    if form.fields[field].queryset.model.__name__ == 'Kor':
        form.fields[field].queryset = korMedTilgang.distinct()
    else:
        form.fields[field].queryset = form.fields[field].queryset\
            .filter(kor__in=korMedTilgang)
    
    if not form.fields[field].queryset.exists():
        disableForm(form)
