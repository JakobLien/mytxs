from django.core.management.base import BaseCommand

from mytxs.models import Kor, Medlem
from mytxs.utils.downloadUtils import getVeventFromHendelse
from mytxs.utils.googleCalendar import GoogleCalendarManager, getHendelseBody
from mytxs.utils.modelUtils import stemmegruppeVerv, vervInnehavelseAktiv

class Command(BaseCommand):
    help = 'Denne sjekke alle mytxs sine google calendars, og fikser feil.'

    def handle(self, *args, **options):
        fixGoogleCalendar()


def fixGoogleCalendar(gCalManager=None):
    'Denne sjekke alle mytxs sine google calendars, og fikser feil.'
    if not gCalManager:
        gCalManager = GoogleCalendarManager()
    
    for calendar in gCalManager.getCalendarList():
        if not calendar.get('description', ''):
            # Dette vil være tilfelle for google brukeren sin (uslettelige) personal calendar
            continue
        kor = Kor.objects.filter(navn=calendar.get('description', '').split('-')[0]).first()
        if not kor:
            continue
        medlem = Medlem.objects.filter(pk=int(calendar.get('description', '').split('-')[1])).first()
        if not medlem:
            continue

        # Håndter sletting av kalendere for gamle korister
        if not medlem.vervInnehavelser.filter(
            vervInnehavelseAktiv(''),
            stemmegruppeVerv(includeDirr=True),
            verv__kor=kor
        ).exists():
            gCalManager.deleteCalendar(calendarId=calendar['id'])
            continue

        remoteEvents = gCalManager.listEvents(calendar['id'])

        localEvents = list(map(lambda h: getHendelseBody(getVeventFromHendelse(h, medlem)), medlem.getHendelser(kor.navn)))

        onlyRemote = []

        # Hendelser som er begge steder
        for gCalEvent in remoteEvents:
            localEvent = next(filter(lambda e: e['extendedProperties']['private']['UID'] == gCalEvent['extendedProperties']['private']['UID'], localEvents), {})
            if not localEvent:
                onlyRemote.append(gCalEvent)
                continue

            localEvents.remove(localEvent)

            if diffEvents(localEvent, gCalEvent):
                print('Updating', localEvent['extendedProperties']['private']['UID'], 'for', medlem, '\n', localEvent, '\n', gCalEvent)
                gCalManager.updateEvent(
                    calendar['id'],
                    localEvent
                )

        # Hendelser som bare er lokalt
        for localEvent in localEvents:
            print('Creating', localEvent['extendedProperties']['private']['UID'], 'for', medlem)
            gCalManager.createEvent(
                calendar['id'],
                localEvent
            )

        # Hendelser som bare er remote
        for event in onlyRemote:
            print('Deleting', localEvent['extendedProperties']['private']['UID'], 'for', medlem)
            gCalManager.deleteEvent(
                calendar['id'],
                event['extendedProperties']['private']['UID']
            )


def diffEvents(localEvent, gCalEvent):
    for key, value in localEvent.items():
        if key in ['start', 'end']:
            if 'dateTime' in gCalEvent[key]:
                gCalEvent[key]['dateTime'] = gCalEvent[key]['dateTime'][:len(value['dateTime'])]
        if value and gCalEvent.get(key) != value:
            return True
    return False