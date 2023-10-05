from django.core.management.base import BaseCommand

from django.contrib.auth.models import User

from mytxs.models import Kor, Medlem, Tilgang, Verv, VervInnehavelse
from mytxs import consts

from mytxs.utils.modelUtils import randomDistinct, stemmegruppeVerv

import datetime

class Command(BaseCommand):
    help = 'seed database for testing and development.'

    def add_arguments(self, parser):
        # Positional arguments
        # parser.add_argument('poll_ids', nargs='+', type=int)

        # Named (optional) arguments

        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear all database contents except loggs and django.users',
        )

        parser.add_argument(
            '--clearLogs',
            action='store_true',
            help='Clear Logg and LoggM2M models',
        )

        parser.add_argument(
            '--dont',
            action='store_true',
            help='Don\'t actually seed',
        )

        parser.add_argument(
            '--korAdmin',
            action='store_true',
            help='Create [storkor]-admin og [storkor]-user',
        )

        parser.add_argument(
            '--userAdmin',
            action='store_true',
            help='Create user user and admin admin',
        )

    def handle(self, *args, **options):
        if options['clear']:
            print('clear...')
            clearData(self)

        if options['clearLogs']:
            print('clearLogs...')
            clearLogs(self)
        
        if not options['dont']:
            print('Seeding Data...')
            runSeed(self)

        if options['userAdmin']:
            print('userAdmin...')
            userAdmin(self)

        if options['korAdmin']:
            print('korAdmin...')
            korAdmin(self)

        # run_seed(self)

def clearData(self):
    'Deletes all data from Models that are not the Logg models'
    for model in [m for m in consts.getAllModels() if m not in consts.getLoggModels()]:
        print(f'Deleting {model.__name__} instances')
        model.objects.all().delete()

def clearLogs(self):
    'Delete all data from logg models'
    for model in consts.getLoggModels():
        print(f'Deleting {model.__name__} instances')
        model.objects.all().delete()

def userAdmin(self):
    medlemmer = []
    for navn in ['admin', 'user']:
        user, created = User.objects.get_or_create(username=navn, defaults={'email':navn+'@example.com'})
        if created:
            user.set_password(navn)
            user.save()
        if user.username == 'admin' and not (user.is_superuser == True or user.is_staff == True):
            user.is_superuser = True
            user.is_staff = True
            user.save()

        medlem, created = Medlem.objects.get_or_create(user=user, defaults={
            'fornavn': navn,
            'etternavn': navn+'sen'
        })

        medlemmer.append(medlem)

    nettanvarlig, created = Verv.objects.get_or_create(
        navn='nettansvarlig',
        kor=Kor.objects.get(kortTittel='TSS')
    )
    nettanvarlig.tilganger.add(*Tilgang.objects.filter(kor__kortTittel='TSS'))
    
    VervInnehavelse.objects.get_or_create(
        verv=nettanvarlig,
        medlem=medlemmer[0],
        defaults={'start': datetime.date.today()}
    )

    if not medlemmer[0].storkor:
        tssStemmegruppe= randomDistinct(Verv.objects.filter(stemmegruppeVerv(''), kor__kortTittel='TSS'))
        VervInnehavelse.objects.create(
            verv=tssStemmegruppe,
            medlem=medlemmer[0],
            start=datetime.date.today()
        )

    if not medlemmer[1].storkor:
        tksStemmegruppe = randomDistinct(Verv.objects.filter(stemmegruppeVerv(''), kor__kortTittel='TKS'))
        VervInnehavelse.objects.create(
            verv=tksStemmegruppe,
            medlem=medlemmer[1],
            start=datetime.date.today()
        )

def korAdmin(self):
    'Opprett medlemmer for alle korlederne, med ish realistiske stemmegruppeverv'

    korledere = ['Frode', 'Ingeborg', 'Sivert', 'Anine', 'Hedda', 'Adrian']
    storkor = ['TSS', 'TKS', 'TSS', 'TKS', 'TKS', 'TSS']
    korlederVerv = ['Formann', 'Leder', 'Pirumsjef', 'Knausleder', 'Toppcandisse', 'Barsjef']

    for i in range(len(consts.alleKorKortTittel)):
        kor = Kor.objects.get(kortTittel=consts.alleKorKortTittel[i])
        
        # Opprett medlememr for hver av de
        korleder, created = Medlem.objects.get_or_create(fornavn=korledere[i], defaults={
            'etternavn': korledere[i]+'sen'
        })

        # Opprett admin vervet
        adminVerv, created = Verv.objects.get_or_create(
            navn=korlederVerv[i],
            kor=kor
        )
        adminVerv.tilganger.add(*Tilgang.objects.filter(kor=kor))

        # Gi korleder adminVervet
        adminVervInnehavelse, created = VervInnehavelse.objects.get_or_create(
            medlem=korleder,
            verv=adminVerv,
            defaults={'start': datetime.date.today()}
        )

        # Gi korleder stemmegruppeverv i koret sitt, om koret har stemmegruppeverv, og de mangle stemmegruppeverv fra det koret
        if Verv.objects.filter(stemmegruppeVerv(''), kor=kor).exists():
            if not VervInnehavelse.objects.filter(stemmegruppeVerv(), medlem=korleder, verv__kor=kor).exists():
                stemmegruppeVervInnehavelse, created = VervInnehavelse.objects.get_or_create(
                    medlem=korleder,
                    start=datetime.date.today(),
                    verv=randomDistinct(Verv.objects.filter(stemmegruppeVerv(''), kor=kor))
                )

        # Gi korleder stemmegruppeverv i storkoret sitt, om dem ikkje har det allerede
        if not VervInnehavelse.objects.filter(stemmegruppeVerv(), medlem=korleder, verv__kor=Kor.objects.get(kortTittel=storkor[i])).exists():
            stemmegruppeVervInnehavelse, created = VervInnehavelse.objects.get_or_create(
                medlem=korleder,
                verv=randomDistinct(Verv.objects.filter(stemmegruppeVerv(''), kor=Kor.objects.get(kortTittel=storkor[i]))),
                defaults={'start': datetime.date.today()}
            )

def runSeed(self):
    'Seed database based on mode'
	
    # For hvert kor
    for i in range(len(consts.alleKorKortTittel)):
        # Opprett koret
        kor, korCreated = Kor.objects.get_or_create(kortTittel=consts.alleKorKortTittel[i], defaults={
            'langTittel': consts.alleKorLangTittel[i], 
            'stemmefordeling': consts.alleKorStemmeFordeling[i]
        })
        if(korCreated):
            self.stdout.write('Created kor ' + kor.kortTittel + ' at id ' + str(kor.pk))

        # Opprett generelle tilganger
        for t in range(len(consts.tilganger)):
            tilgang, tilgangCreated = kor.tilganger.get_or_create(navn=consts.tilganger[t], defaults={
                'bruktIKode': True, 
                'beskrivelse': consts.tilgangBeskrivelser[t]
            })
            if tilgangCreated:
                print(f'Created tilgang {tilgang}')

        # Opprett storkor-tilganger
        if kor.kortTittel in consts.bareStorkorKortTittel:
            for t in range(len(consts.storkorTilganger)):
                tilgang, tilgangCreated = kor.tilganger.get_or_create(navn=consts.storkorTilganger[t], defaults={
                    'bruktIKode': True, 
                    'beskrivelse': consts.storkorTilgangBeskrivelser[t]
                })
                if tilgangCreated:
                    print(f'Created tilgang {tilgang}')

        # Om det e et kor (ikke Sangern)
        if kor.kortTittel in consts.bareKorKortTittel:

            # Opprett dirrigent verv
            dirrVerv, dirrVervCreated = kor.verv.get_or_create(navn='Dirigent', bruktIKode=True)
            if(dirrVervCreated):
                self.stdout.write('Created verv ' + dirrVerv.navn + ' for kor ' + kor.kortTittel + ' at id ' + str(dirrVerv.pk))

            # Opprett permisjon vervet
            permisjonVerv, permisjonVervCreated = kor.verv.get_or_create(navn='Permisjon', bruktIKode=True)
            if permisjonVervCreated:
                self.stdout.write('Created verv ' + permisjonVerv.navn + ' for kor ' + kor.kortTittel + ' at id ' + str(permisjonVerv.pk))

            # Opprett ukjentStemmegruppe vervet
            ukjentStemmegruppeVerv, ukjentStemmegruppeVervCreated = kor.verv.get_or_create(navn='ukjentStemmegruppe', bruktIKode=True)
            if ukjentStemmegruppeVervCreated:
                self.stdout.write('Created verv ' + ukjentStemmegruppeVerv.navn + ' for kor ' + kor.kortTittel + ' at id ' + str(ukjentStemmegruppeVerv.pk))

            # Opprett stemmegrupper
            for stemmegruppe in kor.stemmefordeling:
                # For hver stemmegruppe i koret
                for y in '12':
                    # Opprett hovedstemmegruppeverv
                    stemmegruppeVerv, stemmegruppeVervCreated = kor.verv.get_or_create(navn=y+stemmegruppe, bruktIKode=True)
                    if stemmegruppeVervCreated:
                        self.stdout.write('Created verv ' + stemmegruppeVerv.navn + ' for kor ' + kor.kortTittel + ' at id ' + str(stemmegruppeVerv.pk))
                    
                    if kor.stemmefordeling != 'SATB':
                        # Dropp understemmegrupper for blandakor (altså Knauskoret)
                        for x in '12':
                            # Opprett understemmegruppeverv
                            underStemmegruppeVerv, underStemmegruppeVervCreated = kor.verv.get_or_create(navn=x+y+stemmegruppe, bruktIKode=True)
                            if underStemmegruppeVervCreated:
                                self.stdout.write('Created verv ' + underStemmegruppeVerv.navn + ' for kor ' + kor.kortTittel + ' at id ' + str(underStemmegruppeVerv.pk))
