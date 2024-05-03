from django.core.management.base import BaseCommand, CommandError

from mytxs.models import Kor, Medlem
from mytxs.utils.downloadUtils import getVeventFromHendelse
from mytxs.utils.googleCalendar import GoogleCalendarManager, getHendelseBody


class Command(BaseCommand):
    help = 'Denne sjekke alle mytxs sine google calendars, og fikser feil.'

    def handle(self, *args, **options):
        fixGoogleCalendar()

def fixGoogleCalendar():
    'Denne sjekke alle mytxs sine google calendars, og fikser feil.'
    gCalManager = GoogleCalendarManager()

    if not gCalManager:
        raise CommandError(f'gCalManager could not be created')
    
    gCalManager.skipMailing = True
    
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
                print('Updating event:', localEvent['extendedProperties']['private']['UID'])
                gCalManager.updateEvent(
                    calendar['id'],
                    localEvent
                )

        # Hendelser som bare er lokalt
        for localEvent in localEvents:
            print('Creating missing event:', localEvent['extendedProperties']['private']['UID'])
            gCalManager.createEvent(
                calendar['id'],
                localEvent
            )

        # Hendelser som bare er remote
        for event in onlyRemote:
            print('Deleting old event:', event['extendedProperties']['private']['UID'])
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
            print(f'Found diff {key}: {value} {gCalEvent.get(key)}')
            return True
    return False