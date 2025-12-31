from django.core.management.base import BaseCommand

from mytxs import consts
from mytxs.models import Dekorasjon, Medlem, DekorasjonInnehavelse

import datetime

class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            'dato',
            nargs='?',
            help='Datoen for ordenspromosjonen på ISO 8601. Om oppgitt, vil dekorasjonen tildeles som del av dette.'
        )

    def handle(self, *args, **options):
        medlem = Medlem.objects.filter(pk=int(input('Medlem PK: '))).first()
        while not medlem:
            print('Fant ikke medlem')
            medlem = Medlem.objects.filter(pk=int(input('Medlem PK: '))).first()

        valørIndex = int(input('Valør index (0-2): '))
        while valørIndex not in range(3):
            print('Ugyldig valør index')
            valørIndex = int(input('Valør index (0-2): '))

        if options['dato']:
            dekorasjonInnehavelse = DekorasjonInnehavelse.objects.create(
                medlem=medlem,
                dekorasjon=Dekorasjon.objects.filter(
                    navn=consts.vrangstrupeDekorasjoner[valørIndex],
                    bruktIKode=True,
                    kor__navn=consts.Kor.TSS
                ).first(),
                start=datetime.date.fromisoformat(options['dato'])
            )
            print('Opprettet DekorasjonInnehavelse')
        else:
            dekorasjonInnehavelse = DekorasjonInnehavelse.objects.filter(
                medlem=medlem,
                dekorasjon__navn=consts.vrangstrupeDekorasjoner[valørIndex],
                dekorasjon__bruktIKode=True,
                dekorasjon__kor__navn=consts.Kor.TSS
            ).first()
            if not dekorasjonInnehavelse:
                print('Fant ikke dekorasjonInnehavelse')
                return

        input(f'Setter deviice for {dekorasjonInnehavelse} (trykk enter): ')

        dekorasjonInnehavelse.vrangstrupeSpørsmål = input('Spørsmål: ').strip()
        dekorasjonInnehavelse.vrangstrupeSvar = input('Svar: ').strip()

        deviice = ''
        print('Deviice: (lim inn som fleire linjer)')
        while deviiceLinje := input().strip():
            deviice += deviiceLinje + '\n'

        dekorasjonInnehavelse.vrangstrupeDeviice = deviice.strip()
        dekorasjonInnehavelse.save()

        print('Lagret deviice. Då då då')
