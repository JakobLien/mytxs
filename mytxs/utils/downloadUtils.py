import datetime

from django.db.models import Q, F
from django.http import HttpResponse

def downloadFile(fileName, content, content_type='text/plain'):
    'I en view, return returnverdien av denne funksjonen'
    response = HttpResponse(content, content_type=f'{content_type}; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{fileName}"'
    response['Content-Length'] = len(response.content)
    return response


def downloadVCard(queryset):
    'Laste ned vCard for medlemmene i request.queryset, som har tlf og sjekkhefteSynlig tlf'
    medlemmer = queryset.annotate(
        sjekkhefteSynligTlf=F('sjekkhefteSynlig').bitand(2**2)
    ).exclude(Q(tlf='') | Q(sjekkhefteSynligTlf=0))

    content = ''
    for medlem in medlemmer:
        content += f'''\
begin:vcard
version:4.0
fn:{medlem.navn}
tel;type=cell:{medlem.tlf.replace(' ', '')}
note:Generert av MyTXS 2.0 {datetime.date.today()}
end:vcard
'''
    return downloadFile('MyTXS.vcf', content, content_type='text/vcard')


def processCSVValue(value):
    'Normalisere en verdi til en string som kan brukes i en csv'
    if not isinstance(value, str):
        if isinstance(value, int) or isinstance(value, bool):
            value = str(value)
        elif isinstance(value, float):
            value = str(round(value, 2))
        elif value == None:
            value = ''
    if any(map(lambda c: c in value, [',', '\n', ' '])):
        if '"' in value:
            value = value.replace('"', '""')
        value = f'"{value}"'
    return value


def downloadCSV(fileName, csvArray):
    '''
    csvArray er en 2d array (kollonne først) som inneholder all daten på et naturlig format (str, int, bool, float osv). 
    Denne funksjonen fikse konvertering av alt til string, med fornuftige defaults. None bli f.eks. til en tom streng. 
    Om dette ikkje e ønskelig må man selv konverter til string slik man ønsker. Funksjonen fikse også escaping av verdier,
    at det blir en gylidg CSV liksom. 

    Vi følge CSV spesifikasjonen i rfc4180: https://datatracker.ietf.org/doc/html/rfc4180
    '''
    for y in range(len(csvArray)):
        for x in range(len(csvArray[y])):
            csvArray[y][x] = processCSVValue(csvArray[y][x])
    
    csv = [','.join(lineArr) for lineArr in csvArray]
    csv = '\r\n'.join(csv)

    return downloadFile(fileName, csv, content_type='text/csv')
