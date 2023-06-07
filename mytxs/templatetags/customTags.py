from django import template
from django.template.defaulttags import url

register = template.Library()

@register.simple_tag(takes_context=True)
def setURLParams(context, **kwargs):
    """Returns a link to the current page, with url paramets updated from kwargs."""

    urlParams = context['request'].GET.copy()

    for key, value in kwargs.items():
        urlParams[key] = value

    return '?' + urlParams.urlencode()