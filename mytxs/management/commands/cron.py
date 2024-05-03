import datetime
import sys
import traceback

from django.core import mail
from django.core.management.base import BaseCommand
from django.db.models import Q, F, IntegerField
from django.db.models.functions import Cast

from mytxs.management.commands.fixGoogleCalendar import fixGoogleCalendar
from mytxs.models import Hendelse, Medlem, Oppmøte
from mytxs.utils.modelUtils import vervInnehavelseAktiv


def mailException(func):
    def _decorator(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as exception:
            exception_traceback = ''.join(traceback.format_exception(type(exception), exception, exception.__traceback__))
            mail.mail_admins(
                subject='Exception in cron function!', 
                message=f'Cron function {func.__name__} hadd følgende exception {exception_traceback}'
            )
            sys.exit(1)
    return _decorator


class Command(BaseCommand):
    help = 'Dette kjøre en gong hvert minutt på serveren, slik får vi cron jobs'

    def handle(self, *args, **options):
        now = datetime.datetime.now()

        fraværEpost(now)

        if now.minute == 0:
            # Dette medføre refresh av tokenet, slik at vi aldri går 7 dager uten bruk
            # https://developers.google.com/identity/protocols/oauth2#expiration
            mailException(fixGoogleCalendar)()


@mailException
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
            fraværEpost=Cast(F('innstillinger__epost'), IntegerField()).bitand(1)
        ).filter(
            ~Q(epost=''),
            vervInnehavelseAktiv(),
            vervInnehavelser__verv__kor=hendelse.kor,
            vervInnehavelser__verv__tilganger__navn='fravær',
            fraværEpost=0
        ).values_list('epost', flat=True)

        # Stemmefordeling table
        content = '<table><tr><th>Stemmefordeling</th><th>Kommer</th><th>Kanskje</th><th>Ikke</th></tr>'
        for stemmegruppe, oppmøteAntall in hendelse.getStemmeFordeling().items():
            content += f'<tr><td>{stemmegruppe}</td><td>{oppmøteAntall[0]}</td><td>{oppmøteAntall[1]}</td><td>{oppmøteAntall[2]}</td></tr>'
        content += '</table>\n\n'

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
