from django import template
from django.forms import BaseForm, BaseFormSet, FileField
from django.utils.safestring import mark_safe
from django.urls import reverse

from mytxs.models import Logg
from mytxs.utils.formAccess import formIsEnabled as FormIsEnabled, formIsVisible as FormIsVisible

# Her legg vi til custom template tags and filters

register = template.Library()

@register.simple_tag(takes_context=True)
def setURLParams(context, **kwargs):
    'Returne link til den nåværende siden, med url parameters satt fra kwargs.'
    urlParams = context['request'].GET.copy()

    for key, value in kwargs.items():
        urlParams[key] = value

    return '?' + urlParams.urlencode()

@register.simple_tag(takes_context=True)
def addLoggLink(context, instance):
    '''
    Returne link til loggen, dersom brukeren har tilgang til den. 

    Kompleksiteten her va at om vi laste inn hver logg for å sjekk om vi har tilgang til loggen e det 
    veldig treigt. Istedet sjekke vi derfor om brukeren har tilgang til instansen (som alt e lasta inn), 
    og sie at isåfall har brukeren også tilgan til loggen. 
    '''

    if instance.pk and not isinstance(instance, Logg):
        medlem = context['request'].user.medlem
        if instance in medlem.redigerTilgangQueryset(type(instance)):
            return mark_safe(f'<a class="text-sm" href="{reverse("loggRedirect", args=[type(instance).__name__, instance.pk])}">(Logg)</a>')
    return ''

@register.simple_tag()
def fixFileField(*forms):
    '''
    Adds 'enctype="multipart/form-data"' to the form if form contains a filefield
    Accepts forms, formsets, or lists of them as arguments
    '''

    for form in forms:
        if isinstance(form, BaseForm) and any(list(map(lambda field: isinstance(field, FileField), form.fields.values()))):
            # Om det e et form
            return mark_safe('enctype="multipart/form-data"')
        if isinstance(form, BaseFormSet):
            # Om det e et formset
            if rtrn := fixFileField(*form.forms):
                return rtrn
        if hasattr(form, '__iter__'):
            # Om det e en liste av noe
            if rtrn := fixFileField(*form):
                return rtrn
    return ''

@register.filter
def formIsEnabled(form):
    return FormIsEnabled(form)

@register.filter
def formIsVisible(form):
    return FormIsVisible(form)

@register.simple_tag(takes_context=True)
def getPaginatorNavigation(context, paginatorPage, navName=''):
    'Produsere en meny med linker for å navigere paginatoren'
    if not hasattr(paginatorPage, 'has_other_pages') or not paginatorPage.has_other_pages():
        return ''
    
    navName = navName+'Page' if navName else 'page'

    pages = []

    for pageNumber in paginatorPage.paginator.get_elided_page_range(number=paginatorPage.number, on_ends=1):
        if pageNumber == paginatorPage.number:
            pages.append(f'<span class="text-3xl">{pageNumber}</span>')
        elif isinstance(pageNumber, int):
            pages.append(f'<a href="{setURLParams(context, **{navName: pageNumber})}">{pageNumber}</a>')
        else:
            pages.append(f'<span>{pageNumber}</span>')

    return mark_safe(f'<div>Sider: {" ".join(pages)}</div>')
