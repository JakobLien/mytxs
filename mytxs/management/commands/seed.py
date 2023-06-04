from django.core.management.base import BaseCommand
from mytxs.models import *

from django.contrib.auth.models import User

import datetime

class Command(BaseCommand):
    help = 'seed database for testing and development.'

    def add_arguments(self, parser):
        # Positional arguments
        # parser.add_argument('poll_ids', nargs='+', type=int)

        # Named (optional) arguments
        parser.add_argument(
            '--createStorkorAdmin',
            action='store_true',
            help='Create [storkor]-admin og [storkor]-user',
        )

        parser.add_argument(
            '--createUserAdmin',
            action='store_true',
            help='Create user user and admin admin',
        )

        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear all database contents except Logg and django.users',
        )

        parser.add_argument(
            '--dont',
            action='store_true',
            help='Don\'t actually seed',
        )

    def handle(self, *args, **options):

        if options['clear']:
            print('Clearing Data...')
            clearData(self)
        
        if not options['dont']:
            print('Seeding Data...')
            runSeed(self)

        if options['createUserAdmin']:
            print('Seeding Data...')
            createUserAdmin(self)

        if options['createStorkorAdmin']:
            print('createStorkorAdmin...')
            createStorkorAdmin(self)

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

def createUserAdmin(self):
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
    
    b2 = Verv.objects.get(kor__kortTittel='TSS', navn='22B')
    s1 = Verv.objects.get(kor__kortTittel='TKS', navn='11S')

    VervInnehavelse.objects.get_or_create(
        verv=nettanvarlig,
        medlem=medlemmer[0],
        start=datetime.date.today()
    )

    VervInnehavelse.objects.get_or_create(
        verv=b2,
        medlem=medlemmer[0],
        start=datetime.date.today()
    )

    VervInnehavelse.objects.get_or_create(
        verv=s1,
        medlem=medlemmer[1],
        start=datetime.date.today()
    )

def createStorkorAdmin(self):
    for navn in ['TSS-admin', 'TSS-user', 'TKS-admin', 'TKS-user']: # 'admin', 'user', 
        user, created = User.objects.get_or_create(username=navn, defaults={'email':navn+'@example.com'})
        if created:
            user.set_password(navn)
            user.save()

        medlem, created = Medlem.objects.get_or_create(user=user, defaults={
            'fornavn': navn,
            'etternavn': navn+'sen'
        })

        kor = Kor.objects.get(kortTittel=navn.split("-")[0])

        # Legg på stemmegruppeverv på alle
        if not Verv.objects.filter(stemmeGruppeVerv(''), vervInnehavelse__medlem=medlem).exists():
            stemmegruppe = Verv.objects.filter(stemmeGruppeVerv(''), kor=kor).order_by("?").first()

            VervInnehavelse.objects.create(
                verv=stemmegruppe,
                medlem=medlem,
                start=datetime.date.today()
            )
        
        # Gi admin et admin verv
        if 'admin' in navn:
            if not Verv.objects.filter(vervInnehavelse__medlem=medlem).filter(navn=navn).exists():
                adminVerv, created = Verv.objects.get_or_create(
                    navn=navn,
                    kor=kor
                )

                adminVerv.tilganger.add(*Tilgang.objects.filter(kor=kor).exclude(navn='aktiv'))

                VervInnehavelse.objects.create(
                    verv=adminVerv,
                    medlem=medlem,
                    start=datetime.date.today()
                )

def runSeed(self):
    ''' Seed database based on mode'''

    kortTittel = ['TSS', 'Pirum', 'KK', 'Candiss', 'TKS']
    langTittel = [
		'Trondhjems Studentersangforening',
		'Pirum',
		'Knauskoret',
		'Candiss',
		'Trondhjems Kvinnelige Studentersangforening'
    ]

    korTilStemmeFordeling = [0, 0, 1, 2, 2]
    stemmeFordeling = ['TB', 'SATB', 'SA']

    tilganger = ['aktiv', 'dekorasjon', 'dekorasjonInnehavelse', 'verv', 'vervInnehavelse', 'tilgang', 'logg']
    tilgangBeskrivelser = [
        'Gitt til stemmegruppeverv og dirigent i koret. De som har tilgangen er altså de som er aktive i koret.',
        'For å opprette og slette dekorasjoner, samt endre på eksisterende dekorasjoner.',
        'For å opprette og slette dekorasjonInnehavelser, altså hvem som fikk hvilken dekorasjon når.',
        'For å opprette og slette verv, samt endre på eksisterende verv.',
        'For å opprette og slette vervInnehavelser, altså hvem som hadde hvilket verv når. Dette inkluderer stemmegrupper.',
        'For å opprette og slette tilganger, samt endre på hvilket verv som medfører disse tilgangene.',
        'For å kunne lese logger, altså endringer av verv, dekorasjoner, tilganger og deres innehavelser.'
    ]
    
    storkorTilganger = ['medlemsdata']
    storkorTilgangBeskrivelser = [
        'For å kunne endre på medlemsdataene til de i ditt storkor.'
    ]
	
    # For hvert kor
    for i in range(5):
        # Opprett koret
        kor, korCreated = Kor.objects.get_or_create(kortTittel=kortTittel[i], defaults={'langTittel':langTittel[i]})
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


        # For hver stemmegruppe i koret, opprett top-level stemmegruppeverv, og gi de aktiv tilgangen om de ikke har det alt. 
        aktivTilgang = Tilgang.objects.get(navn='aktiv', kor=kor)

        for stemmeGruppe in stemmeFordeling[korTilStemmeFordeling[i]]:
            for y in '12':
                # Opprett hovedstemmegruppeverv
                stemmeGruppeVerv, stemmeGruppeVervCreated = kor.verv.get_or_create(navn=y+stemmeGruppe)
                if(stemmeGruppeVervCreated):
                    self.stdout.write('Created verv ' + stemmeGruppeVerv.navn + ' for kor ' + kor.kortTittel + ' at id ' + str(stemmeGruppeVerv.pk))
                
                stemmeGruppeVerv.tilganger.add(aktivTilgang)

                for x in '12':
                    # Opprett understemmegruppeverv
                    underStemmeGruppeVerv, underStemmeGruppeVervCreated = kor.verv.get_or_create(navn=x+y+stemmeGruppe)
                    if(underStemmeGruppeVervCreated):
                        self.stdout.write('Created verv ' + underStemmeGruppeVerv.navn + ' for kor ' + kor.kortTittel + ' at id ' + str(underStemmeGruppeVerv.pk))

                    underStemmeGruppeVerv.tilganger.add(aktivTilgang)
        
        # Opprett dirrigent verv
        dirrVerv, dirrVervCreated = kor.verv.get_or_create(navn='dirigent')
        dirrVerv.tilganger.add(aktivTilgang)
        if(dirrVervCreated):
            self.stdout.write('Created verv ' + dirrVerv.navn + ' for kor ' + kor.kortTittel + ' at id ' + str(dirrVerv.pk))


        # Opprett dekorasjoner
        for dekorasjon in ['ridder', 'kommandør', 'kommandør med storkors']:
            # Opprett dekorasjon tilgangen
            dekorasjon, dekorasjonCreated = Dekorasjon.objects.get_or_create(navn=dekorasjon, kor=kor)
            if dekorasjonCreated:
                print('Created dekorasjon ' + dekorasjon.navn + ' for kor ' + kor.kortTittel)