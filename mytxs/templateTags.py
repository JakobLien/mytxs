import datetime
from django import template
from django.core.paginator import Paginator
from django.forms import BaseForm, BaseFormSet, FileField
from django.template import TemplateSyntaxError, defaultfilters, defaulttags
from django.utils.safestring import mark_safe
from django.urls import reverse

from mytxs.models import Logg
from mytxs.utils.formAccess import formIsEnabled, formIsVisible

# Her legg vi til custom template tags and filters

register = template.Library()

# Ting som skal være identisk med en eksisterende funksjon kan vi bare import hit og register, 
# istedet for å wrap dem i en større funksjon. E enklere og ryddigere. 

register.filter(formIsEnabled)
register.filter(formIsVisible)


@register.simple_tag(takes_context=True)
def setURLParams(context, **kwargs):
    '''
    Returne link (url) til den nåværende siden, med url parameters satt fra kwargs. 
    Om et parameter e satt til None vil det fjernes fra urlen. 
    '''
    urlParams = context['request'].GET.copy()

    for key, value in kwargs.items():
        if value == None:
            urlParams.pop(key, None)
        else:
            urlParams[key] = value

    return '?' + urlParams.urlencode()


@register.simple_tag(takes_context=True)
def addLoggLink(context, instance):
    '''
    Returne link (<a>) til loggen, dersom brukeren har tilgang til den. 

    Kompleksiteten her va at om vi laste inn hver logg for å sjekk om vi har tilgang til loggen e det 
    veldig treigt, siden vi i formsets vil ha mange "finn nyeste logg queries". Istedet sjekke vi derfor 
    om brukeren har tilgang til instansen (som alt e lasta inn), og sie at isåfall har brukeren også tilgang 
    til loggen. (og bruke loggRedirect for å ikkje måtta lookup loggen for å skaff urlen) 
    '''
    if instance.pk and not isinstance(instance, Logg):
        medlem = context['request'].user.medlem
        if medlem.redigerTilgangQueryset(type(instance)).contains(instance):
            return mark_safe(f'<a class="text-sm" href="{reverse("loggRedirect", args=[type(instance).__name__, instance.pk])}">(Logg)</a>')
    return ''


@register.simple_tag()
def fixFileField(*forms):
    '''
    Adds 'enctype="multipart/form-data"' to the form if form contains a filefield
    Accepts forms, formsets, or lists of them as arguments
    '''
    for form in forms:
        if isinstance(form, BaseForm) and any(map(lambda field: isinstance(field, FileField), form.fields.values())):
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


@register.filter
def bitIs1(int, bitNr):
    return bool(int & 1 << bitNr)


@register.simple_tag(takes_context=True)
def toggleURLparam(context, urlParamName, linkName=None):
    'Produsere en <a> tag som heter enten linkName eller "Ikke" + linkName, som legger til og fjerner urlParamName'
    if linkName == None:
        linkName = urlParamName

    urlParams = context['request'].GET.copy()

    if urlParamName not in urlParams.keys():
        return mark_safe(f'<a href="{setURLParams(context, **{urlParamName: True})}">{defaultfilters.capfirst(linkName)}</a>')
    else:
        return mark_safe(f'<a href="{setURLParams(context, **{urlParamName: None})}">Ikke {linkName}</a>')


@register.filter
def filterMedlemFirst(queryset, medlem):
    'For når man treng å filtrer et queryset på medlem=medlem, også si .first()'
    return queryset.filter(medlem=medlem).first()


@register.filter
def past(moment):
    'For å sjekk om en date eller datetime var i fortiden'
    if isinstance(moment, datetime.datetime):
        return moment < datetime.datetime.now()
    else:
        return moment < datetime.date.today()


@register.simple_tag(takes_context=True)
def addSubNavigation(context):
    'Denne opprette en navigasjonsmeny (på denne siden) basert på medlem.navBar'

    # Skip navigation på instance sider
    if hasattr(context['request'], 'instance'):
        return ''
    
    node = context['request'].user.medlem.navBar[context['request']]
    if node:
        return mark_safe(node.buildNavigation())
    return ''


@register.filter
def divideAndShowPercent(num1, num2):
    if num2 == 0:
        return '0%'
    return f'{int(num1/num2*100)}%'


@register.filter
def showFravær(medlem, gyldig):
    'Hjelpefunksjon som tar et medlem og vise gyldig eller ugyldig fravær formatert som "minutt (prosent)"'
    fravær = medlem.gyldigFravær if gyldig else medlem.ugyldigFravær
    return mark_safe(f'{fravær} ({divideAndShowPercent(fravær, medlem.hendelseVarighet)})')


@register.simple_tag(takes_context=True)
def paginateList(context, list, navName, pageSize=30):
    '''
    Returne paginator navigasjonen og lagre paginatorPage som navName+Page i context som kan itereres over under dette.
    Generelt virke det rotåt at tags skal driv å sett ting inn i context som brukes andre steder, men siden paginator
    navigasjonen alltid kommer like over itereringa i templaten syns e det går fint å bruk her:)
    
    For eksempel:
    ```
    {% paginateList request.instance.getReverseRelated 'reverseRelated' %}
    {% for related in reverseRelatedPage %}
    ```'''
    pageNum = context['request'].GET.get(navName+'Page')
    context[navName+'Page'] = Paginator(list, pageSize).get_page(pageNum)
    return getPaginatorNavigation(context, context[navName+'Page'], navName)


@register.filter
def linkTo(instance, label=''):
    return mark_safe(f'<a href="{instance.get_absolute_url()}">{label if label else instance}</a>')


@register.filter
def tilgangExists(medlem, tilgangNavn):
    return medlem.tilganger.filter(navn__in=tilgangNavn.split(',')).exists()


class IfAllNode(template.Node):
    def __init__(self, nodelists):
        self.nodelists = nodelists

    def render(self, context):
        returnStr = ''
        for nodelist in self.nodelists:
            currStr = nodelist.render(context)
            # Dersom en av nodene returner bare whitespace, ikke return noe totalt sett.
            if not currStr.strip():
                return ''
            returnStr += currStr
        
        # Ellers, return alt
        return mark_safe(returnStr)


@register.tag()
def ifAll(parser, token):
    'Et templateTag som bare renderer alle deler dersom alle deler inneholder non whitespace post parse'
    # Koden her ser komplisert ut, men det er bare mye boilerplate. Se if tag-en:)
    nodelist = parser.parse(("ifAll", "endIfAll"))
    nodelists = [nodelist]
    token = parser.next_token()

    # {% ifAll %} (repeatable)
    while token.contents.startswith("ifAll"):
        nodelist = parser.parse(("ifAll", "endIfAll"))
        nodelists.append(nodelist)
        token = parser.next_token()

    # {% endIfAll %}
    if token.contents != "endIfAll":
        raise TemplateSyntaxError(
            'Malformed template tag at line {}: "{}"'.format(
                token.lineno, token.contents
            )
        )

    return IfAllNode(nodelists)


class linkIfAccessNode(template.Node):
    def __init__(self, nodelist, navBarPath):
        self.nodelist = nodelist
        self.navBarPath = navBarPath

    def render(self, context):
        if node := context['request'].user.medlem.navBar[self.navBarPath]:
            return mark_safe(f'<a href="{node.url}">' + self.nodelist.render(context) + '</a>')
        return ''


@register.tag()
def linkIfAccess(parser, token):
    'Lenke til en side dersom du har navBar sidetilgang til den'
    # Koden her ser komplisert ut, men det er bare boilerplate. Se if tag-en:)
    bits = token.split_contents()[1:]
    nodelist = parser.parse(("endLinkIfAccess"))
    token = parser.next_token()

    # {% endLinkIfAccess %}
    if token.contents != "endLinkIfAccess":
        raise TemplateSyntaxError(
            'Malformed template tag at line {}: "{}"'.format(
                token.lineno, token.contents
            )
        )

    return linkIfAccessNode(nodelist, bits)
