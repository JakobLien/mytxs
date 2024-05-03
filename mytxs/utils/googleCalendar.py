import base64
import datetime
import os
import sys
import threading
import traceback

from django.core import mail

from mytxs import settings
from mytxs.utils.downloadUtils import getVeventFromHendelse

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
# from google_auth_oauthlib.flow import InstalledAppFlow # La stå
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

def mailException(func):
    def _decorator(self, *args, **kwargs):
        if hasattr(self, 'skipMailing') or settings.DEBUG:
            return func(self, *args, **kwargs)
        
        try:
            return func(self, *args, **kwargs)
        except Exception as exception:
            arguments = ''
            if args:
                if not isinstance(args, list):
                    args = [args]
                arguments += '\nArgs:\n- ' + '\n- '.join(map(lambda a: str(a), args))
            if kwargs:
                arguments += '\nKwargs:\n- ' + '\n- '.join(map(lambda kv: f'{kv[0]}: {kv[1]}', kwargs.items()))
            exception_traceback = ''.join(traceback.format_exception(type(exception), exception, exception.__traceback__))
            mail.mail_admins(
                subject='Google Calenadar Exception!', 
                message=f'GoogleCalendarManager method {func.__name__} hadd et exception!\n{arguments}\n\n\n{exception_traceback}'
            )
            sys.exit(1)
    return _decorator


class GoogleCalendarManager:
    def __init__(self, *args, **kwargs):
        self.service = None
        creds = None
        SCOPES = ["https://www.googleapis.com/auth/calendar"]

        tokenPath = os.environ.get('GOOGLE_CALENDAR_TOKEN_PATH')
        if not tokenPath or not os.path.exists(tokenPath):
            return
        
        creds = Credentials.from_authorized_user_file(tokenPath, SCOPES)

        if not creds: 
            return
        
        if creds.expired:
            creds.refresh(Request())

            # # Alternativt for å regenerer googleCalendarToken
            # flow = InstalledAppFlow.from_client_secrets_file(
            #     "credentials.json", SCOPES
            # )
            # creds = flow.run_local_server(port=0)

            with open(tokenPath, "w") as token:
                print('Wrote new google calendar token!')
                token.write(creds.to_json())
        try:
            self.service = build("calendar", "v3", credentials=creds)
        except HttpError as error:
            print(f"An error occurred: {error}")

    @mailException
    def createCalendar(self, name, description):
        return self.service.calendars().insert(body={
            'summary': name,
            'timeZone': 'Europe/Oslo',
            'description': description
        }).execute()['id']

    @mailException
    def shareCalendar(self, calendarId, gmail):
        return self.service.acl().insert(calendarId=calendarId, body={
            'scope': {
                'type': 'user',
                'value': gmail
            },
            'role': 'reader'
        }).execute()

    @mailException
    def getCalendarList(self):
        return self.service.calendarList().list(maxResults=250).execute().get('items', [])
    
    @mailException
    def listEvents(self, calendarId):
        return self.service.events().list(calendarId=calendarId, maxResults=2500).execute().get('items', [])

    @mailException
    def getEventId(self, calendarId, UID):
        return self.service.events().list(calendarId=calendarId, privateExtendedProperty=[f'UID={UID}']).execute().get('items', [])[0]['id']

    @mailException
    def createEvent(self, calendarId, body):
        return self.service.events().insert(calendarId=calendarId, body=body).execute()

    @mailException
    def updateEvent(self, calendarId, body):
        eventId = self.getEventId(calendarId, body['extendedProperties']['private']['UID'])
        return self.service.events().update(calendarId=calendarId, eventId=eventId, body=body).execute()

    @mailException
    def deleteEvent(self, calendarId, UID):
        eventId = self.getEventId(calendarId, UID)
        return self.service.events().delete(calendarId=calendarId, eventId=eventId).execute()

    def getCalendarIDs(self, korNavn, medlemmer):
        'Returne en dicitonary som mappe fra medlem til google kalender id'
        calendars = {}
        for calendar in self.getCalendarList():
            if not calendar.get('description', ''):
                # Dette vil være tilfelle for google brukeren sin (uslettelige) personal calendar
                continue
            if calendar.get('description', '').split('-')[0] != korNavn:
                continue
            medlemPK = int(calendar.get('description', '').split('-')[1])
            for medlem in medlemmer:
                if medlem.pk == medlemPK:
                    calendars[medlem] = calendar['id']
        return calendars


def iCalDateTimeToISO(dateTimeStr, addTimeDelta=None):
    if len(dateTimeStr) == 8:
        date = datetime.datetime.strptime(dateTimeStr, "%Y%m%d").date()
        if addTimeDelta:
            date += addTimeDelta
        return date.strftime("%Y-%m-%d")
    else:
        dateTime = datetime.datetime.strptime(dateTimeStr, "%Y%m%dT%H%M%S")
        if addTimeDelta:
            date += addTimeDelta
        return dateTime.strftime("%Y-%m-%dT%H:%M:%S")


def getHendelseBody(veventDict):
    # Vi tar utgangspunkt i downloadUtils.py sin getVeventFromHendelse, slik at endringer der reflekteres her!
    body = {
        'summary': veventDict['SUMMARY'],
        'location': veventDict['LOCATION'],
        'description': veventDict['DESCRIPTION'].replace('\\n', '\n'),
        'extendedProperties': {
            'private': {
                'UID': veventDict['UID']
            }
        }
    }

    if veventDict.get('DTSTART;TZID=Europe/Oslo'):
        body['start'] = {
            'dateTime': iCalDateTimeToISO(veventDict['DTSTART;TZID=Europe/Oslo']),
            'timeZone': 'Europe/Oslo',
        }
    else:
        body['start'] = {'date': iCalDateTimeToISO(veventDict['DTSTART;VALUE=DATE'])}

    if veventDict.get('DTEND;TZID=Europe/Oslo'):
        body['end'] = {
            'dateTime': iCalDateTimeToISO(veventDict['DTEND;TZID=Europe/Oslo']),
            'timeZone': 'Europe/Oslo',
        }
    elif veventDict.get('DTEND;VALUE=DATE'):
        body['end'] = {'date': iCalDateTimeToISO(veventDict['DTEND;VALUE=DATE'])}
    else:
        # Man må ha en slutt date/dateTime når man interagere med google calendar
        # Vi har alltid slutt når vi har startTime, så må bare fikse dette for heldags hendelser
        body['end'] = body['start'].copy()
        body['end']['date'] = iCalDateTimeToISO(veventDict['DTSTART;VALUE=DATE'], addTimeDelta=datetime.timedelta(days=1))

    return body


def thread(func):
    def _decorator(*args, **kwargs):
        t = threading.Thread(
            target=func, 
            args=args, 
            kwargs=kwargs,
            daemon=True
        )
        t.start()
        return t
    return _decorator


@thread
def getOrCreateAndShareCalendar(korNavn, medlem, gmail):
    gCalManager = GoogleCalendarManager()
    
    if not gCalManager.service:
        return

    calendarId = gCalManager.getCalendarIDs(korNavn, [medlem]).get(medlem)

    if not calendarId:
        calendarId = gCalManager.createCalendar(f'{korNavn} semesterplan', f'{korNavn}-{medlem.pk}')

        for hendelse in medlem.getHendelser(korNavn):
            gCalManager.createEvent(
                calendarId,
                getHendelseBody(getVeventFromHendelse(hendelse, medlem))
            )

    gCalManager.shareCalendar(calendarId, gmail)


@thread
def updateGoogleCalendar(hendelse, oldMedlemmer=[], newMedlemmer=[]):
    gCalManager = GoogleCalendarManager()

    if not gCalManager.service:
        return
    
    # Sangern hendelser kan vær i begge storkor sine kalendere
    if hendelse.kor.navn == 'Sangern':
        medlemCalendars = gCalManager.getCalendarIDs('TSS', oldMedlemmer+newMedlemmer) | gCalManager.getCalendarIDs('TKS', oldMedlemmer+newMedlemmer)
    else:
        medlemCalendars = gCalManager.getCalendarIDs(hendelse.kor.navn, oldMedlemmer+newMedlemmer)
    
    for medlem, calendarId in medlemCalendars.items():
        vevent = getVeventFromHendelse(hendelse, medlem)
        old = medlem in oldMedlemmer
        new = medlem in newMedlemmer
        if old and new:
            gCalManager.updateEvent(
                calendarId,
                getHendelseBody(vevent)
            )
        elif old:
            gCalManager.deleteEvent(
                calendarId, 
                vevent['UID']
            )
        elif new:
            gCalManager.createEvent(
                calendarId, 
                getHendelseBody(vevent)
            )
