
from django.core.management.base import BaseCommand

from django.core import mail
from django.core.mail import send_mail

from mytxs.models import Medlem
from django.db.models import Q


class Command(BaseCommand):
    help = 'seed database for testing and development.'

    def add_arguments(self, parser):
        # Positional arguments
        # parser.add_argument('poll_ids', nargs='+', type=int)

        # Named (optional) arguments

        parser.add_argument(
            '--missingUsers',
            action='store_true',
            help='List the users who don\'t have an email address, and thus won\'t recieve emails sent. \
If this argument is set, all other functionality is skipped!'
        )

        parser.add_argument(
            '--actualEmail',
            action='store_true',
            help='Send an email instead of logging to the console (only works on server)'
        )

        parser.add_argument(
            '--actualContent',
            action='store_true',
            help='Populate the acatual content to test'
        )

    def handle(self, *args, **options):
        if options['missingUsers']:
            medlemmer = Medlem.objects.filter(user__isnull=True, epost="")

            print(f'Missing users: {len(medlemmer)}')

            for medlem in medlemmer:
                print(f'mytxs.samfundet.no{medlem.get_absolute_url()}')
            
            return

        # Sett defaults som endres gitt arguments for det
        backend = 'django.core.mail.backends.console.EmailBackend'
        messages = {
            'jakoblien01@gmail.com': 'Hei!\nDu kan nå registrere deg på mytxs.samfundet.no/register/1'
        }
        
        if options['actualEmail']:
            print('Sending actual email...')
            backend = 'django.core.mail.backends.smtp.EmailBackend'

        if options['actualContent']:

            medlemmer = Medlem.objects.filter(~Q(epost=""), user__isnull=True)

            messages = {}

            for medlem in medlemmer:
                messages[medlem.epost] = \
f'''\
Hei {medlem.navn}!
Det er min ære å meddele at du nå kan opprette en bruker på MyTXS 2.0 her:

https://mytxs.samfundet.no/registrer/{medlem.pk}

Sangerhilsen
Jakob Lien'''

        print(f'Antall eposter: {len(messages)}')

        with mail.get_connection(backend=backend) as connection:
            for recipient, message in messages.items():
                send_mail(
                    "Registrering på MyTXS 2.0",
                    message,
                    "mytxs@samfundet.no",
                    [recipient],
                    fail_silently=False,
                    connection=connection
                )
        print('Done!')
