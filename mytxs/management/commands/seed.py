from django.core.management.base import BaseCommand

from django.contrib.auth.models import User

from mytxs.models import Dekorasjon, DekorasjonInnehavelse, Kor, Logg, LoggM2M, Medlem, Tilgang, Verv, VervInnehavelse
from mytxs.consts import alleKorKortTittel, alleKorLangTittel, korTilStemmeFordeling, stemmeFordeling, tilganger, tilgangBeskrivelser, storkorTilganger, storkorTilgangBeskrivelser
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
    '''Deletes all the table data'''
    
    print('Delete DekorasjonInnehavelse instances')
    DekorasjonInnehavelse.objects.all().delete()
    print('Delete Dekorasjon instances')
    Dekorasjon.objects.all().delete()

    print('Delete VervInnehavelse instances')
    VervInnehavelse.objects.all().delete()
    print('Delete Tilgang instances')
    Tilgang.objects.all().delete()
    print('Delete Verv instances')
    Verv.objects.all().delete()

    print('Delete Kor instances')
    Kor.objects.all().delete()
    print('Delete Medlem instances')
    Medlem.objects.all().delete()

def clearLogs(self):
    print('Delete Logg instances')
    Logg.objects.all().delete()
    print('Delete LoggM2M instances')
    LoggM2M.objects.all().delete()

def userAdmin(self):
    medlemmer = []
    for navn in ['admin', 'user']:
        user, created = User.objects.get_or_create(username=navn, defaults={'email':navn+'@example.com'})
        if created:
            user.set_password(navn)
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
    
    tssStemmegruppe= randomDistinct(Verv.objects.filter(stemmegruppeVerv(''), kor__kortTittel='TSS'))
    tksStemmegruppe = randomDistinct(Verv.objects.filter(stemmegruppeVerv(''), kor__kortTittel='TKS'))

    VervInnehavelse.objects.get_or_create(
        verv=nettanvarlig,
        medlem=medlemmer[0],
        start=datetime.date.today()
    )

    VervInnehavelse.objects.get_or_create(
        verv=tssStemmegruppe,
        medlem=medlemmer[0],
        start=datetime.date.today()
    )

    VervInnehavelse.objects.get_or_create(
        verv=tksStemmegruppe,
        medlem=medlemmer[1],
        start=datetime.date.today()
    )

def korAdmin(self):
    "Opprett medlemmer for alle korlederne, med ish realistiske stemmegruppeverv"

    korledere = ['Frode', 'Sivert', 'Anine', 'Hedda', 'Ingeborg', 'Adrian']
    storkor = ['TSS', 'TSS', 'TKS', 'TKS', 'TKS', 'TSS']
    korlederVerv = ['formann', 'pirumsjef', 'knausleder', 'toppcandisse', 'leder', 'barsjef']

    for i in range(len(alleKorKortTittel)):
        kor = Kor.objects.get(kortTittel=alleKorKortTittel[i])
        
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
    ''' Seed database based on mode'''
	
    # For hvert kor
    for i in range(len(alleKorKortTittel)):
        # Opprett koret
        kor, korCreated = Kor.objects.get_or_create(kortTittel=alleKorKortTittel[i], defaults={'langTittel':alleKorLangTittel[i]})
        if(korCreated):
            self.stdout.write('Created kor ' + kor.kortTittel + ' at id ' + str(kor.pk))

        # Opprett generelle tilganger
        for t in range(len(tilganger)):
            tilgang, tilgangCreated = Tilgang.objects.get_or_create(navn=tilganger[t], kor=kor, brukt=True, beskrivelse=tilgangBeskrivelser[t])
            if tilgangCreated:
                print(f'Created tilgang {tilgang}')

        # Opprett storkor-tilganger
        if kor.kortTittel in ['TSS', 'TKS']:
            for t in range(len(storkorTilganger)):
                tilgang, tilgangCreated = Tilgang.objects.get_or_create(navn=storkorTilganger[t], kor=kor, brukt=True, beskrivelse=storkorTilgangBeskrivelser[t])
                if tilgangCreated:
                    print(f'Created tilgang {tilgang}')


        # For hver stemmegruppe i koret, opprett top-level stemmegruppeverv
        if i < len(korTilStemmeFordeling):
            for stemmegruppe in stemmeFordeling[korTilStemmeFordeling[i]]:
                for y in '12':
                    # Opprett hovedstemmegruppeverv
                    stemmegruppeVerv, stemmegruppeVervCreated = kor.verv.get_or_create(navn=y+stemmegruppe)
                    if stemmegruppeVervCreated:
                        self.stdout.write('Created verv ' + stemmegruppeVerv.navn + ' for kor ' + kor.kortTittel + ' at id ' + str(stemmegruppeVerv.pk))
                    
                    for x in '12':
                        # Opprett understemmegruppeverv
                        underStemmegruppeVerv, underStemmegruppeVervCreated = kor.verv.get_or_create(navn=x+y+stemmegruppe)
                        if underStemmegruppeVervCreated:
                            self.stdout.write('Created verv ' + underStemmegruppeVerv.navn + ' for kor ' + kor.kortTittel + ' at id ' + str(underStemmegruppeVerv.pk))

            # Opprett dirrigent verv
            dirrVerv, dirrVervCreated = kor.verv.get_or_create(navn='dirigent')
            if(dirrVervCreated):
                self.stdout.write('Created verv ' + dirrVerv.navn + ' for kor ' + kor.kortTittel + ' at id ' + str(dirrVerv.pk))


        # Opprett dekorasjoner
        for dekorasjon in ['ridder', 'kommandør', 'kommandør med storkors']:
            # Opprett dekorasjon tilgangen
            dekorasjon, dekorasjonCreated = Dekorasjon.objects.get_or_create(navn=dekorasjon, kor=kor)
            if dekorasjonCreated:
                print('Created dekorasjon ' + dekorasjon.navn + ' for kor ' + kor.kortTittel)
