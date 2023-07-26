# Alt forøverig om forms

from django.forms import BaseFormSet


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

def callForEveryForm(func, formset, *args, **kwargs):
    '''
    Utility funksjon som kalle func for hvert form i formsettet. 
    Dersom den returne true burde func return så resten av parent
    funksjonen ikke burde kalles for selve formsettet. Eksempel kode:

    if callForEveryForm(hideFields, form, *fieldNames):
        return
    '''
    if isinstance(formset, BaseFormSet):
        for form in formset.forms:
            func(form, *args, **kwargs)
        return True
