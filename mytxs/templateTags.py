from django import template
from django.forms import FileField
from django.utils.safestring import mark_safe

from mytxs.models import Logg
from mytxs.utils.formAccess import formIsEnabled as FormIsEnabled, formIsVisible as FormIsVisible

# Her legg vi til custom template tags and filters

register = template.Library()

@register.simple_tag(takes_context=True)
def setURLParams(context, **kwargs):
    'Returns a link to the current page, with kwargs set as url parameters'
    urlParams = context['request'].GET.copy()

    for key, value in kwargs.items():
        urlParams[key] = value

    return '?' + urlParams.urlencode()

@register.simple_tag(takes_context=True)
def addLoggLink(context, instance):
    'Returns the link to the logg corresponsing to the instance, if the user has access to that page'
    if instance:
        logg = Logg.objects.getLoggFor(instance)
        if logg and context['user'].medlem.harSideTilgang(logg):
            return mark_safe(f'<a class="text-sm" href="{logg.get_absolute_url()}">(Logg)</a>')
    return ''

@register.simple_tag()
def fixFileField(*forms):
    '''
    Adds 'enctype="multipart/form-data"' to the form if form contains a filefield
    Accepts forms, formsets, or lists of them as arguments
    '''

    for form in forms:
        if hasattr(form, 'fields') and any(list(map(lambda field: isinstance(field, FileField), form.fields.values()))):
            # Om det e et form
            return mark_safe('enctype="multipart/form-data"')
        if hasattr(form, 'forms'):
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
