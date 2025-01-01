import datetime
import os
from time import sleep

from mytxs import consts
from mytxs.utils.downloadUtils import getVeventFromHendelse
from mytxs.utils.threadUtils import thread

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
# from google_auth_oauthlib.flow import InstalledAppFlow # La stå
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

def exponentialBackoff(func):
    'Implementasjon av exponential backoff, samt at den begrense antall requests.'
    def _decorator(self, *args, **kwargs):
        attempt = 0
        while True:
            if self.requestCountDown != None:
                if self.requestCountDown <= 0:
                    raise Exception('Google Calendar exceeded 100 requests.')
                self.requestCountDown -= 1
            try:
                return func(self, *args, **kwargs)
            except HttpError as httpError:
                if attempt >= 5 or not (httpError.status_code in [403, 429] or httpError.status_code >= 500):
                    raise httpError
                sleep(2**attempt)
                attempt += 1
    return _decorator


class GoogleCalendarManager:
    'Denne raise diverse exceptions om den ikkje kan instansieres.'
    def __init__(self, requestCountDown=None):
        self.requestCountDown = requestCountDown
        self.service = None
        creds = None
        SCOPES = ["https://www.googleapis.com/auth/calendar"]

        tokenPath = os.environ.get('GOOGLE_CALENDAR_TOKEN_PATH')
        if not tokenPath or not os.path.exists(tokenPath):
            raise Exception('Missing Google Calendar Token')
        
        creds = Credentials.from_authorized_user_file(tokenPath, SCOPES)

        if not creds:
            raise Exception('Credentials could not be created')
        
        if creds.expired:
            creds.refresh(Request())

            # # Alternativt for å regenerer googleCalendarToken
            # flow = InstalledAppFlow.from_client_secrets_file(
            #     "credentials.json", SCOPES
            # )
            # creds = flow.run_local_server(port=0)

            with open(tokenPath, "w") as token:
                token.write(creds.to_json())
                # print('Wrote new google calendar token!')
        self.service = build("calendar", "v3", credentials=creds)

    @exponentialBackoff
    def createCalendar(self, name, description):
        return self.service.calendars().insert(body={
            'summary': name,
            'timeZone': 'Europe/Oslo',
            'description': description
        }).execute()['id']

    @exponentialBackoff
    def shareCalendar(self, calendarId, gmail):
        return self.service.acl().insert(calendarId=calendarId, body={
            'scope': {
                'type': 'user',
                'value': gmail
            },
            'role': 'reader'
        }).execute()

    @exponentialBackoff
    def deleteCalendar(self, calendarId):
        return self.service.calendars().delete(calendarId=calendarId).execute()

    @exponentialBackoff
    def getCalendarList(self):
        return self.service.calendarList().list(maxResults=250).execute().get('items', [])
    
    @exponentialBackoff
    def listEvents(self, calendarId):
        return self.service.events().list(calendarId=calendarId, maxResults=2500).execute().get('items', [])

    @exponentialBackoff
    def getEventId(self, calendarId, UID):
        return self.service.events().list(calendarId=calendarId, privateExtendedProperty=[f'UID={UID}']).execute().get('items', [])[0]['id']

    @exponentialBackoff
    def createEvent(self, calendarId, body):
        return self.service.events().insert(calendarId=calendarId, body=body).execute()

    @exponentialBackoff
    def updateEvent(self, calendarId, body):
        eventId = self.getEventId(calendarId, body['extendedProperties']['private']['UID'])
        return self.service.events().update(calendarId=calendarId, eventId=eventId, body=body).execute()

    @exponentialBackoff
    def deleteEvent(self, calendarId, UID):
        return self.service.events().delete(calendarId=calendarId, eventId=self.getEventId(calendarId, UID)).execute()

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
    '''
    Konverterer en veventDict fra iCal eksport koden til en Google Calendar Request body.
    Dette medfører at Google Calendar semesterplan vil være identisk til en iCal semesterplan,
    og at vi bare må endre på iCal eksport for å fikse på all kalendereksport.
    '''
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


@thread
def getOrCreateAndShareCalendar(korNavn, medlem, gmail):
    gCalManager = GoogleCalendarManager(requestCountDown=200)

    calendarId = gCalManager.getCalendarIDs(korNavn, [medlem]).get(medlem)

    if not calendarId:
        calendarId = gCalManager.createCalendar(f'{korNavn} semesterplan', f'{korNavn}-{medlem.pk}')

        gCalManager.shareCalendar(calendarId, gmail)

        for hendelse in medlem.getHendelser(korNavn):
            gCalManager.createEvent(
                calendarId,
                getHendelseBody(getVeventFromHendelse(hendelse, medlem))
            )


@thread
def updateGoogleCalendar(hendelse, changed=False, oldMedlemmer=[], newMedlemmer=[], hendelsePK=None):
    'Oppdatere Google Calendar gitt liste av gamle og nye medlemmer. hendelsePK til bruk ved sletting.'
    gCalManager = GoogleCalendarManager(requestCountDown=200)
    
    # Sangern hendelser er i begge storkor kalendere
    if hendelse.kor.navn == consts.Kor.Sangern:
        medlemCalendars = gCalManager.getCalendarIDs(consts.Kor.TSS, oldMedlemmer+newMedlemmer) | gCalManager.getCalendarIDs(consts.Kor.TKS, oldMedlemmer+newMedlemmer)
    else:
        medlemCalendars = gCalManager.getCalendarIDs(hendelse.kor.navn, oldMedlemmer+newMedlemmer)
    
    for medlem, calendarId in medlemCalendars.items():
        vevent = getVeventFromHendelse(hendelse, medlem, hendelsePK=hendelsePK)
        old = medlem in oldMedlemmer
        new = medlem in newMedlemmer
        if new and not old:
            gCalManager.createEvent(
                calendarId, 
                getHendelseBody(vevent)
            )
        elif new and old and changed:
            gCalManager.updateEvent(
                calendarId,
                getHendelseBody(vevent)
            )
        elif old and not new:
            gCalManager.deleteEvent(
                calendarId, 
                vevent['UID']
            )
