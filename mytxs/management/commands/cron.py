import datetime

from django.core import mail
from django.core.management.base import BaseCommand
from django.db.models import Q, F, IntegerField
from django.db.models.functions import Cast

from mytxs import consts
from mytxs.management.commands.fixGoogleCalendar import fixGoogleCalendar
from mytxs.models import Hendelse, Medlem, Oppmøte
from mytxs.utils.googleCalendar import GoogleCalendarManager
from mytxs.utils.modelUtils import vervInnehavelseAktiv
from mytxs.utils.threadUtils import mailException

# Til info har ITK satt det opp slik at om cron jobben printe nå som helst, 
# eller om den raise et exception, så vil den send epost med output te meg:)

class Command(BaseCommand):
    help = 'Dette kjøre en gong hvert minutt på serveren, slik får vi cron jobs'

    @mailException
    def handle(self, *args, **options):
        now = datetime.datetime.now()

        fraværEpost(now)

        if now.minute == 0:
            # Dette medføre refresh av tokenet, slik at vi aldri går 7 dager uten bruk
            # https://developers.google.com/identity/protocols/oauth2#expiration
            fixGoogleCalendar(gCalManager=GoogleCalendarManager(requestCountDown=100))


def fraværEpost(now):
    start = now + datetime.timedelta(hours=2)
    hendelser = Hendelse.objects.filter(
        navn__icontains='øv',
        kategori=Hendelse.OBLIG,
        startDate=start.date(),
        startTime__hour=start.hour,
        startTime__minute=start.minute
    )

    for hendelse in hendelser:
        mottakere = Medlem.objects.annotate(
            fraværEpost=Cast(F('innstillinger__epost'), IntegerField()).bitand(2**1)
        ).filter(
            ~Q(epost=''),
            vervInnehavelseAktiv(),
            vervInnehavelser__verv__kor=hendelse.kor,
            vervInnehavelser__verv__tilganger__navn=consts.Tilgang.fravær,
            fraværEpost=0
        ).values_list('epost', flat=True)

        # Stemmefordeling table
        content = 'Stemmegruppe: Kommer, Kommer kanskje, Kommer ikke'
        for stemmegruppe, oppmøteAntall in hendelse.getStemmeFordeling().items():
            content += f'\n{stemmegruppe}: {oppmøteAntall[0]}, {oppmøteAntall[1]}, {oppmøteAntall[2]}'
        content += '\n\n'

        # Individuelle fraværsmeldinger
        for oppmøte in Oppmøte.objects.filter(
            ~Q(melding=''),
            hendelse=hendelse
        ).prefetch_related('medlem'):
            content += f'{oppmøte.medlem}:\nAnkomst: {oppmøte.get_ankomst_display()}\nMelding: {oppmøte.melding}\n\n'

        # Langtidspermisjon
        if permiterte := '\n- '.join(Medlem.objects.filter(
            vervInnehavelseAktiv(dato=hendelse.startDate),
            vervInnehavelser__verv__navn='Permisjon',
            vervInnehavelser__verv__kor=hendelse.kor
        ).annotateFulltNavn().values_list('fulltNavn', flat=True)):
            content += f'I tillegg har disse langtidspermisjon:\n- {permiterte}'

        mail.send_mail(
            subject=f'Fraværsoversikt for {hendelse}',
            message=content,
            from_email=None,
            recipient_list=list(mottakere)
        )
