import json
from django import forms
from django.db.models.fields import BLANK_CHOICE_DASH
from django.http import JsonResponse

from mytxs.utils.formAccess import formIsEnabled

# Alt relatert til å gjør forms raskar å render

def formsetGroupQueries(formset, *fieldNames):
    'Denne gjør at dropdownmenyer i et formset bruke samme queryset resultat for dropdown. Hjelpe om vi ikkje bruke lazyDropdown'

    if len(formset.forms) == 0:
        return
    
    choices = []

    for fieldName in fieldNames:
        choices.append(list(forms.ModelChoiceField(formset.forms[0].fields[fieldName].queryset).choices))

    # Hentet herifra: https://code.djangoproject.com/ticket/22841#comment:10
    for form in formset.forms:
        for i, fieldName in enumerate(fieldNames):
            form.fields[fieldName].choices = choices[i]


def onlyRenderSelected(formset, fieldName):
    'Gjør at fields bare renderes med BLANK_CHOICE_DASH og selected options'
    for form in formset.forms:
        if formIsEnabled(form):
            if not hasattr(form.instance, fieldName):
                form.fields[fieldName].widget.choices = BLANK_CHOICE_DASH
            elif not hasattr(form.instance.medlem, '__iter__'):
                # TODO: Liten bug med dette er at selects med options som er preselected men som ikkje er i model vil 
                # forsvinne på render. Dette skjer f.eks. når valideringen ikke passer, så ikke krise, men liten bug da. 
                form.fields[fieldName].widget.choices = [*BLANK_CHOICE_DASH, (getattr(form.instance, fieldName).pk, getattr(form.instance, fieldName))]
            else:
                raise Exception('Yoyo, implement me!')
                # ish: form.fields['medlem'].widget.choices = [(m.pk, m) for m in [*BLANK_CHOICE_DASH, *form.instance.medlemmer]]


def getLazyDropdownOptions(request, formset, fieldName):
    '''
    Returne et JsonResponse av feltets queryset, som er en liste av lister. 
    I alle listene er første indeks pk, mens andre index er str representasjonen. 
    '''
    if request.GET.get('getOptions') == f'{formset.prefix}-{fieldName}':
        # Skaff det første feltet som ikke er disabled.
        # Merk at denne koden anntar at i alle formsets vil det første feltet som ikke er disabled 
        # ha samme queryset som alle andre ikke disabled felt i det formsettet. Den anntakelsen 
        # virke som den held godt for no, men vær bevisst på det!
        field = formset.forms[0].fields[fieldName]
        i = 1
        while field.disabled and i < len(formset.forms):
            field = formset.forms[i].fields[fieldName]
            i += 1
        
        return JsonResponse([[m.pk, str(m)] for m in field.queryset], safe=False)


def lazyDropdown(request, formset, fieldName):
    '''
    Snarvei som kombinere getLazyDropdownOptions med onlyRenderSelected, så einaste man må skriv i viewet er typ:

    if res := makeDropdownLazy(request, vervInnehavelseFormset, 'medlem'):
        return res
    '''

    if request.GET.get('getOptions') and request.GET.get('getOptions') != f'{formset.prefix}-{fieldName}':
        # Om dette er et request for å get options, men det ikke er dette formsettet+feltet, 
        # ikkje gjør nå meir her, siden forms ikke avhenger av hverandre på den måten. Spare litt ressurser:)
        return

    if not formIsEnabled(formset):
        # Om formet ikkje har noen fields som er enabled, skip
        return

    if res := getLazyDropdownOptions(request, formset, fieldName):
        return res
    
    onlyRenderSelected(formset, fieldName)

    # Hiv på JSON lazyDropdownData som settes inn i head av base.html og brukes av lazyDropdown.js
    # for å vite hvilke selects den skal sende request for og sette inn options i. 
    if hasattr(request, 'lazyDropdownData'):
        request.lazyDropdownData = json.dumps(json.loads(request.lazyDropdownData) + [f'{formset.prefix}-{fieldName}'])
    else:
        request.lazyDropdownData = json.dumps([f'{formset.prefix}-{fieldName}'])