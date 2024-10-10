from django.forms import BaseFormSet

# Alt forøverig om forms

inlineFormsetArgs = {
    'exclude': [],
    'extra': 1,
    'can_delete_extra': False
}
'Args for inline formsets'


formsetArgs = {
    'extra': 1,
    'can_delete_extra': False
}
'Args for formsets forøvrig'


def postIfPost(request, prefix=''):
    '''
    Return subset med prefix av request.POST dersom request.method == 'POST', ellers None.
    
    E trur ikkje strengt tatt det e nødvendig å separer ut hvilke felt som går til hvilke forms, 
    (det e jo heile poenget med prefix at det ikkje skal vær konflikta), men e trur det bli 
    lettar å debug når noko wack skjer, når hvert form bare får dataen tiltenkt dem:)

    Grunnen til at koden e meir komplisert enn man sku tru den måtta vær e fordi querydict sitt interface
    sug, se: https://docs.djangoproject.com/en/4.2/ref/request-response/#django.http.QueryDict.items
    '''
    if not request.method == 'POST':
        return None
        
    queryDict = request.POST.copy()
    for key in list(filter(lambda k: not k.startswith(prefix), queryDict.keys())):
        queryDict.pop(key)
    return queryDict


def filesIfPost(request, prefix=''):
    'Return subset med prefix av request.FILES dersom request.method == "POST", ellers None.'
    if not request.method == 'POST':
        return None
    
    queryDict = request.FILES.copy()
    for key in list(filter(lambda k: not k.startswith(prefix), queryDict.keys())):
        queryDict.pop(key)
    return queryDict


def formsetToForm(func):
    '''
    Decorator som dersom første argument er et formset, calle vi funksjonen fleir gong, 
    en gong på hvert form i formsettet.  Ellers skjer ingenting spesielt
    '''
    def _decorator(formset, *args, **kwargs):
        if isinstance(formset, BaseFormSet):
            for form in formset.forms:
                func(form, *args, **kwargs)
        else:
            func(formset, *args, **kwargs)

    return _decorator


def toolTip(helpText):
    return f'<span title="{helpText}">(?)</span>'


@formsetToForm
def addHelpText(form, *fieldNames, helpText=''):
    for fieldName in fieldNames:
        form.fields[fieldName].help_text = toolTip(helpText)
