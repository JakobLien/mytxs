from django.core.paginator import Paginator
import datetime
from django.http import HttpResponse

# Alle generelle ting ellers

def getPaginatorPage(request):
    'Gitt et request med satt request.queryset og url param "page", returne denne en paginator page'
    paginator = Paginator(request.queryset, 30)
    return paginator.get_page(request.GET.get('page'))

def generateVCard(medlemmer):
    'Returne et gyldig vcard innhold gitt et queryset av medlemmer'
    vCardContent = ''
    for medlem in medlemmer:
        vCardContent += f'''\
begin:vcard
version:4.0
fn:{medlem.navn}
tel;type=cell:{medlem.tlf.replace(' ', '')}
note:Generert av MyTXS 2.0 {datetime.date.today()}
end:vcard
'''
    return vCardContent

def downloadFile(fileName, content, content_type='text/plain'):
    'I en view, return returnverdien av denne funksjonen'
    response = HttpResponse(content, content_type=f'{content_type}; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{fileName}"'
    response['Content-Length'] = len(content)
    return response
