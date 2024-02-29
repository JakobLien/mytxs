import datetime
from urllib.parse import unquote

from django.db.models import Q, F
from django.http import HttpResponse
from django.urls import reverse

from mytxs import settings as mytxsSettings
from mytxs.models import Hendelse, Medlem

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


def dateToICal(date):
    if isinstance(date, datetime.datetime):
        return date.strftime('%Y%m%dT%H%M%S')
    return date.strftime('%Y%m%d')


def getVeventFromHendelse(hendelse, medlem):
    veventDict = {
        'BEGIN': 'VEVENT',
        'UID': f'{hendelse.kor}-{hendelse.pk}@mytxs.samfundet.no'
    }

    veventDict['SUMMARY'] = hendelse.navnMedPrefiks

    veventDict['DESCRIPTION'] = [hendelse.beskrivelse.replace('\r\n', '\\n')] if hendelse.beskrivelse else []
    if hendelse.kategori == Hendelse.UNDERGRUPPE:
        veventDict['DESCRIPTION'].append('De inviterte:\\n- ' + '\\n- '.join([str(m) for m in hendelse.medlemmer]))
    elif (oppmøte := hendelse.oppmøter.filter(medlem=medlem).first()) and oppmøte.fraværTekst:
        veventDict['DESCRIPTION'].append(oppmøte.fraværTekst + ': ' + mytxsSettings.ALLOWED_HOSTS[0] + unquote(reverse('meldFravær', args=[medlem.pk, hendelse.pk])))
    veventDict['DESCRIPTION'] = '\\n\\n'.join(veventDict['DESCRIPTION'])

    veventDict['LOCATION'] = hendelse.sted

    if isinstance(hendelse.start, datetime.datetime):
        veventDict['DTSTART;TZID=Europe/Oslo'] = dateToICal(hendelse.start)
    else:
        veventDict['DTSTART;VALUE=DATE'] = dateToICal(hendelse.start)

    if hendelse.slutt:
        if isinstance(hendelse.slutt, datetime.datetime):
            veventDict['DTEND;TZID=Europe/Oslo'] = dateToICal(hendelse.slutt)
        else:
            # I utgangspunktet er slutt tiden (hovedsakling tidspunktet) ekskludert i ical formatet, 
            # men følgelig om det er en sluttdato (uten tid), vil det vises som en dag for lite
            # i kalenderapplikasjonene. Derfor hive vi på en dag her, så det vises rett:)
            veventDict['DTEND;VALUE=DATE'] = dateToICal(hendelse.slutt + datetime.timedelta(days=1))
    
    veventDict['DTSTAMP'] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S") + 'Z'

    veventDict['END'] = 'VEVENT'

    return veventDict


def downloadICal(medlem, korNavn):
    '''
    Denne funksjonen returne basert på hendelseQueryset og medlem, en ical download response. 
    Den håndterer generering av gyldig ical content, med hjelp fra getVeventFromHendelse
    '''
    iCalString = f'''\
BEGIN:VCALENDAR
PRODID:-//mytxs.samfundet.no//MyTXS semesterplan//
VERSION:2.0
CALSCALE:GREGORIAN
METHOD:PUBLISH
X-WR-CALNAME:MyTXS 2.0 Semesterplan
X-WR-CALDESC:Denne kalenderen ble oppdatert av MyTXS {
datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S')}Z
X-WR-TIMEZONE:Europe/Oslo
BEGIN:VTIMEZONE
TZID:Europe/Oslo
X-LIC-LOCATION:Europe/Oslo
BEGIN:DAYLIGHT
TZOFFSETFROM:+0100
TZOFFSETTO:+0200
TZNAME:CEST
DTSTART:19700329T020000
RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU
END:DAYLIGHT
BEGIN:STANDARD
TZOFFSETFROM:+0200
TZOFFSETTO:+0100
TZNAME:CET
DTSTART:19701025T030000
RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU
END:STANDARD
END:VTIMEZONE
'''
    for hendelse in medlem.getHendelser(korNavn):
        for key, value in getVeventFromHendelse(hendelse, medlem).items():
            if value:
                iCalString += key + ':' + value + '\n'

    iCalString += 'END:VCALENDAR\n'

    # Split lines som e lenger enn 75 characters over fleir linja
    iCalLines = iCalString.split('\n')
    l = 0
    while l < len(iCalLines):
        if len(iCalLines[l]) > 75:
            iCalLines.insert(l+1, ' ' + iCalLines[l][75:])
            iCalLines[l] = iCalLines[l][:75]
        l += 1

    # Join alle lines med CRLF
    iCalString = '\r\n'.join(iCalLines)

    return downloadFile(f'{korNavn} semesterplan.ics', iCalString, content_type='text/calendar')
