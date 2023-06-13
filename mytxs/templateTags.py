from django import template
from django.forms import FileField
from django.utils.safestring import mark_safe

from mytxs.models import Logg
from mytxs.utils.formAccess import fieldIsVisible

# Her legg vi til custom template tags and filters

register = template.Library()

@register.simple_tag(takes_context=True)
def setURLParams(context, **kwargs):
    """Returns a link to the current page, with kwargs set as url parameters."""
    urlParams = context['request'].GET.copy()

    for key, value in kwargs.items():
        urlParams[key] = value

    return '?' + urlParams.urlencode()

@register.filter
def logLink(instance):
    'Returns the link to the logg corresponsing to the instance.'
    return Logg.objects.getLoggLinkFor(instance)

@register.filter
def fixFileField(form):
    'Adds \'enctype="multipart/form-data"\' to the form if form contains a filefield'
    if any(list(map(lambda field: isinstance(field, FileField), form.fields.values()))):
        return mark_safe('enctype="multipart/form-data"')

@register.filter
def formIsEnabled(form):
    "Returne true om det e minst ett felt som ikke e disabled i formet/formsettet"
    # Om det e et formset
    if hasattr(form, 'forms') and form.forms != None:
        return any(map(lambda form: formIsEnabled(form), form.forms))

    return any(map(lambda field: not field.disabled and fieldIsVisible(field), form.fields.values()))

@register.filter
def formIsVisible(form):
    "Returne true om det e minst ett felt som ikke e visible i formet"
    # Om det e et formset
    if hasattr(form, 'forms') and form.forms != None:
        return any(map(lambda form: formIsVisible(form), form.forms))

    return any(map(lambda field: fieldIsVisible(field), form.fields.values()))
