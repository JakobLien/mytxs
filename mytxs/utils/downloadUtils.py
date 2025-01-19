import datetime
from urllib.parse import unquote

from django.db.models import Q
from django.http import HttpResponse
from django.urls import reverse

from mytxs import settings as mytxsSettings

def downloadFile(fileName, content='', content_type='text/plain'):
    'I en view, return returnverdien av denne funksjonen'
    return HttpResponse(content, content_type=f'{content_type}; charset=utf-8', headers={"Content-Disposition": f'attachment; filename="{fileName}"'})


def downloadVCard(queryset):
    'Laste ned vCard for medlemmene i request.queryset, som har tlf og sjekkhefteSynlig tlf'
    medlemmer = queryset.annotatePublic().exclude(Q(public__tlf__isnull=True))

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


def dateToICal(date):
    if isinstance(date, datetime.datetime):
        return date.strftime('%Y%m%dT%H%M%S')
    return date.strftime('%Y%m%d')


def getVeventFromHendelse(hendelse, medlem, hendelsePK=None):
    'Genererer en dictionary med keys og values tilsvarende en iCal hendelse'
    veventDict = {
        'BEGIN': 'VEVENT',
        'UID': f'{hendelse.kor}-{hendelsePK if hendelsePK else hendelse.pk}@mytxs.samfundet.no'
    }

    veventDict['SUMMARY'] = hendelse.navnMedPrefiks

    veventDict['DESCRIPTION'] = [hendelse.beskrivelse.replace('\r\n', '\\n')] if hendelse.beskrivelse else []
    if hendelse.kategori == type(hendelse).UNDERGRUPPE:
        veventDict['DESCRIPTION'].append('De inviterte:\\n- ' + '\\n- '.join([str(m) for m in hendelse.oppmøteMedlemmer]))
    elif hendelse.pk and (oppmøte := hendelse.oppmøter.filter(medlem=medlem).first()) and oppmøte.fraværTekst:
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
    
    veventDict['DTSTAMP'] = dateToICal(datetime.datetime.now(datetime.timezone.utc)) + 'Z'

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
X-WR-CALNAME:{korNavn} semesterplan (iCal)
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

    return downloadFile(f'{korNavn} semesterplan (iCal).ics', iCalString, content_type='text/calendar')
