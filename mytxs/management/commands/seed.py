import datetime
import random

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

from mytxs import consts
from mytxs.models import *
from mytxs.utils.modelUtils import randomDistinct, stemmegruppeVerv, strToModels, vervInnehavelseAktiv

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
            '--adminAdmin',
            action='store_true',
            help='Create admin admin user',
        )

        parser.add_argument(
            '--testData',
            action='store_true',
            help='Create some testing data for development',
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

        if options['adminAdmin']:
            print('adminAdmin...')
            adminAdmin(self)

        if options['testData']:
            print('testData...')
            testData(self)


def clearData(self):
    'Deletes all data from Models that are not the Logg models'
    for model in [m for m in strToModels(consts.allModelNames) if m not in strToModels(consts.loggModelNames)]:
        print(f'Deleting {model.__name__} instances')
        model.objects.all().delete()


def clearLogs(self):
    'Delete all data from logg models'
    for model in strToModels(consts.loggModelNames):
        print(f'Deleting {model.__name__} instances')
        model.objects.all().delete()


def adminAdmin(self):
    user, created = User.objects.get_or_create(username='admin', defaults={'email': 'admin@example.com'})
    if created:
        user.set_password('admin')
        user.save()
    user.is_superuser = True
    user.is_staff = True
    user.save()

    medlem, created = Medlem.objects.get_or_create(user=user, defaults={'fornavn': 'admin', 'etternavn': 'adminsen'})

    if created:
        medlem.innstillinger = {
            'adminTilganger': consts.alleTilganger,
            'adminTilgangerKor': [consts.Kor.TSS, consts.Kor.Knauskoret]
        }
        medlem.save()

        medlem.vervInnehavelser.create(
            verv=randomDistinct(Verv.objects.filter(stemmegruppeVerv('', includeUkjentStemmegruppe=False), kor__navn=consts.Kor.TSS)),
            start=datetime.date.today()
        )

        medlem.vervInnehavelser.create(
            verv=randomDistinct(Verv.objects.filter(stemmegruppeVerv('', includeUkjentStemmegruppe=False), kor__navn=consts.Kor.Knauskoret)),
            start=datetime.date.today()
        )


def testData(self):
    'Opprett masse medlemmer, korledere, dirigenter og hendelser'
    random.seed('SeedMedlemsRegister!')

    guttenavn, jentenavn, etternavn = [], [], []
    with open('mytxs/management/commands/seedNames.csv', 'r') as f:
        while line := f.readline():
            line=line[:-1].split(',')
            guttenavn.append(line[0])
            jentenavn.append(line[1])
            etternavn.append(line[2])

    def makeMedlem(kor=None, start=None, slutt=None, stemmegruppe=None):
        medlem = Medlem.objects.create(
            fornavn=random.choice(guttenavn) if getattr(kor, 'navn', '') == consts.Kor.TSS else random.choice(jentenavn) if getattr(kor, 'navn', '') == consts.Kor.TKS else random.choice([*guttenavn, *jentenavn]),
            mellomnavn='Test',
            etternavn=random.choice(etternavn)
        )
        if kor:
            medlem.vervInnehavelser.get_or_create(
                start=start,
                slutt=slutt,
                verv=stemmegruppe
            )
        
        return medlem
    
    totalNumber = 500
    startYear = 2010
    korlederVervNavn = ['Formann', 'Leder', 'Pirumsjef', 'Knausleder', 'Toppcandisse', 'Barsjef'] # Rekkefølgen tilsvarer consts.alleKorNavn
    øvingsdag = [1, 1, 3, 2, 0] # Rekkefølgen tilsvarer consts.alleKorNavn

    # Lag stor og småkorista, og gi dem testVerv og testDekorasjona
    for i in range(totalNumber):
        kor = Kor.objects.get(navn=consts.Kor.TSS if i <= totalNumber / 2 else consts.Kor.TKS)
        
        start = datetime.date.fromisoformat(str(random.randrange((startYear), datetime.date.today().year+1)) + '-09-01')
        medlem = makeMedlem(
            kor=kor, 
            start=start,
            slutt=start + datetime.timedelta(weeks=random.randrange(52/4, 52*4)),
            stemmegruppe=Verv.objects.get(navn=random.choice(kor.stemmegrupper(lengde=2 + random.getrandbits(1))), kor=kor)
        )

        # Gi noen av de stemmmegrupper i småkor
        if (småkorTall := random.randrange(8)) < 3:
            if småkorTall < 2:
                småkor = Kor.objects.get(navn=consts.Kor.Pirum if kor.navn==consts.Kor.TSS else consts.Kor.Candiss)
            else:
                småkor = Kor.objects.get(navn=consts.Kor.Knauskoret)

            # Dette kan generere folk som e aktiv i småkor lenger enn dem e aktiv i storkor, som ikkje virke krise for koden sin del
            stemmegruppe = Verv.objects.get(navn=random.choice(kor.stemmegrupper(lengde=2)), kor=småkor)
            medlem.vervInnehavelser.get_or_create(
                start=datetime.date.fromisoformat(str(start.year+1)+'-01-01'),
                slutt=datetime.date.fromisoformat(str(start.year+3)+'-01-01'),
                verv=stemmegruppe
            )
        else:
            # Om ikke småkor, gi noen av de permisjon andre året sitt, dersom de er aktive heile andre året
            stemmegruppe = medlem.vervInnehavelser.first()
            if random.getrandbits(1) == 1 and stemmegruppe.slutt > datetime.date.fromisoformat(f'{start.year+1}-12-31'):
                medlem.vervInnehavelser.get_or_create(
                    start=datetime.date.fromisoformat(f'{start.year+1}-01-01'),
                    slutt=datetime.date.fromisoformat(f'{start.year+1}-12-31'),
                    verv=Verv.objects.get(navn='Permisjon', kor=kor)
                )

        # Gi noen av de testVerv
        if (testVervTall := random.randrange(8)) < 3:
            testVerv, created = Verv.objects.get_or_create(navn=f'testVerv_{testVervTall}', kor=kor)
            medlem.vervInnehavelser.get_or_create(
                start=datetime.date.fromisoformat(str(start.year+1)+'-01-01'),
                slutt=datetime.date.fromisoformat(str(start.year+2)+'-12-31'),
                verv=testVerv
            )
        
        # Gi noen få av de testDekorasjoner
        if (testDekorasjonTall := random.randrange(20)) < 3:
            testDekorasjon, created = Dekorasjon.objects.get_or_create(navn=f'testDekorasjon_{testDekorasjonTall}', kor=kor)
            medlem.dekorasjonInnehavelser.get_or_create(
                start=datetime.date.fromisoformat(str(start.year+random.randrange(1, 4))+'-01-01'),
                dekorasjon=testDekorasjon
            )

    # Lag korledera og dirigenta
    for i in range(6):
        kor = Kor.objects.get(navn=consts.alleKorNavn[i])
        for year in range(startYear, datetime.date.today().year+1):
            korleder = randomDistinct(Medlem.objects.filter(
                vervInnehavelseAktiv(dato=datetime.date.fromisoformat(f'{year}-01-01')),
                stemmegruppeVerv('vervInnehavelser__verv'),
                vervInnehavelser__verv__kor=kor
            ).exclude(
                vervInnehavelser__verv__navn__in=korlederVervNavn + ['Dirigent']
            ), random=random)

            if not korleder:
                # Om det e ingen i koret, skip dette året
                continue
        
            korlederVerv, created = Verv.objects.get_or_create(navn=korlederVervNavn[i], kor=kor)
            korleder.vervInnehavelser.get_or_create(
                start=datetime.date.fromisoformat(f'{year}-01-01'),
                slutt=datetime.date.fromisoformat(f'{year}-12-31'),
                verv=korlederVerv
            )

            if kor.navn == consts.Kor.Sangern:
                # Sangern har ikke dirigenter
                continue

            dirigent = None
            dirigentVerv = Verv.objects.get(navn='Dirigent', kor=kor)

            lastDirigent = Medlem.objects.filter(
                vervInnehavelser__slutt=datetime.date.fromisoformat(f'{year-1}-12-31'),
                vervInnehavelser__verv=dirigentVerv
            ).first()

            if lastDirigent and random.getrandbits(1) == 1:
                # Om fjorårets dirigent fortsette
                dirigentVervInnehavelse = lastDirigent.vervInnehavelser.filter(
                    slutt=datetime.date.fromisoformat(f'{year-1}-12-31'),
                    verv=dirigentVerv
                ).first()

                dirigentVervInnehavelse.slutt = dirigentVervInnehavelse.slutt.replace(year=year)
                dirigentVervInnehavelse.save()

                continue
        
            if random.getrandbits(1) == 1:
                # Gammel korist
                dirigent = randomDistinct(Medlem.objects.filter(
                    vervInnehavelseAktiv(dato=datetime.date.fromisoformat(f'{year-5}-01-01')),
                    stemmegruppeVerv('vervInnehavelser__verv')
                ).exclude(
                    vervInnehavelser__verv__navn__in=korlederVervNavn + ['Dirigent']
                ), random=random)

            if not dirigent and kor.navn in consts.bareSmåkorNavn:
                # Aktiv storkorist e ofte dirigent for småkor
                dirigent = randomDistinct(Medlem.objects.filter(
                    vervInnehavelseAktiv(dato=datetime.date.fromisoformat(f'{year}-01-01')),
                    stemmegruppeVerv('vervInnehavelser__verv'),
                    vervInnehavelser__verv__kor__navn__in=consts.bareStorkorNavn
                ).exclude(
                    vervInnehavelseAktiv(dato=datetime.date.fromisoformat(f'{year}-01-01')),
                    stemmegruppeVerv('vervInnehavelser__verv'),
                    vervInnehavelser__verv__kor__navn__in=consts.bareSmåkorNavn
                ).exclude(
                    vervInnehavelser__verv__navn__in=korlederVervNavn + ['Dirigent']
                ), random=random)

            if not dirigent:
                # Ekstern dirigent
                dirigent = makeMedlem()

            dirigent.vervInnehavelser.get_or_create(
                start=datetime.date.fromisoformat(f'{year}-01-01'),
                slutt=datetime.date.fromisoformat(f'{year}-12-31'),
                verv=dirigentVerv
            )
    
    # Lag dem neste 3 øvelsan for alle koran
    for i in range(5):
        kor = Kor.objects.get(navn=consts.alleKorNavn[i])
        nesteØvelseDate = datetime.date.today() + datetime.timedelta(days=(øvingsdag[i] - datetime.date.today().weekday()) % 7)

        for i in range(3):
            Hendelse.objects.get_or_create(
                navn=f'{kor.navn} øvelse {i+1}',
                kor=kor,
                startDate=nesteØvelseDate,
                startTime=datetime.time.fromisoformat('18:30:00'),
                sluttTime=datetime.time.fromisoformat('21:30:00'),
            )

            nesteØvelseDate += datetime.timedelta(weeks=1)


def runSeed(self):
    'Seed database based on mode'
	
    # For hvert kor
    for i in range(len(consts.alleKorNavn)):
        # Opprett koret
        kor, korCreated = Kor.objects.get_or_create(navn=consts.alleKorNavn[i], defaults={
            'tittel': consts.alleKorTittel[i], 
            'stemmefordeling': consts.alleKorStemmeFordeling[i]
        })
        if korCreated:
            self.stdout.write('Created kor ' + kor.navn + ' at id ' + str(kor.pk))

        tilgangerForKor = [t[0] for t in consts.tilgangTilKorNavn.items() if kor.navn in t[1]]

        # Opprett tilganger
        for tilgangNavn in tilgangerForKor:
            tilgang, tilgangCreated = kor.tilganger.get_or_create(
                navn=tilgangNavn, 
                bruktIKode=True, 
                defaults={
                    'beskrivelse': consts.tilgangBeskrivelser[list(consts.tilgangTilKorNavn.keys()).index(tilgangNavn)]
                }
            )
            if tilgangCreated:
                print(f'Created tilgang {tilgang}')

        # Slett tilganger i kor som ikkje har de. 
        for tilgang in kor.tilganger.filter(~Q(navn__in=tilgangerForKor), bruktIKode=True):
            tilgang.verv.clear()
            tilgang.delete()
            print(f'Slettet tilgang {tilgang}')

        # Under her e om det e et kor (ikke Sangern)
        if kor.navn not in consts.bareKorNavn:
            continue

        # Opprett dirrigent verv
        dirrVerv, dirrVervCreated = kor.verv.get_or_create(navn='Dirigent', bruktIKode=True)
        if dirrVervCreated:
            self.stdout.write('Created verv ' + dirrVerv.navn + ' for kor ' + kor.navn + ' at id ' + str(dirrVerv.pk))

        # Opprett permisjon vervet
        permisjonVerv, permisjonVervCreated = kor.verv.get_or_create(navn='Permisjon', bruktIKode=True)
        if permisjonVervCreated:
            self.stdout.write('Created verv ' + permisjonVerv.navn + ' for kor ' + kor.navn + ' at id ' + str(permisjonVerv.pk))

        # Opprett ukjentStemmegruppe vervet
        ukjentStemmegruppeVerv, ukjentStemmegruppeVervCreated = kor.verv.get_or_create(navn='ukjentStemmegruppe', bruktIKode=True)
        if ukjentStemmegruppeVervCreated:
            self.stdout.write('Created verv ' + ukjentStemmegruppeVerv.navn + ' for kor ' + kor.navn + ' at id ' + str(ukjentStemmegruppeVerv.pk))

        # Opprett stemmegrupper
        for stemmegruppe in kor.stemmegrupper(ekstraDybde=0 if kor.navn == consts.Kor.Knauskoret else 1):
            stemmegruppeVerv, stemmegruppeVervCreated = kor.verv.get_or_create(navn=stemmegruppe, bruktIKode=True)
            if stemmegruppeVervCreated:
                self.stdout.write('Created verv ' + stemmegruppeVerv.navn + ' for kor ' + kor.navn + ' at id ' + str(stemmegruppeVerv.pk))
