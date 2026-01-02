import datetime
import os
import certifi
import urllib3
import json

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db.utils import IntegrityError

from mytxs import consts
from mytxs.management.commands.updateField import objectsGenerator
from mytxs.models import Kor, Repertoar, Sang

# Så greia e at MyTXS 1.0 servern supporte ikkje ipv6, og samfundet har ipv6 som default.
# Dette lede til at dersom vi ikkje eksplisit spesifisere at vi må bruk ipv4 får vi en bug
# på servern som vi ikke får lokalt, og som e no har brukt 3 tima på å debug med itk. Ikke 
# gjør samme feilen igjen!
urllib3.util.connection.HAS_IPV6 = False


class Command(BaseCommand):
    help = 'Pull data from the old site, using key specified in .env'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear all database contents except loggs and django.users',
        )

    def handle(self, *args, **options):
        if options['clear']:
            Repertoar.objects.all().delete()
            Sang.objects.all().delete()
        
        transferNoterakiv()


def transferNoterakiv():
    http = urllib3.PoolManager(
        cert_reqs="CERT_REQUIRED",
        ca_certs=certifi.where()
    )

    path = os.environ.get('NOTEARKIV_DUMP_PATH')

    if not path:
        raise CommandError('SET NOTEARKIV_DUMP_PATH in .env')

    if not os.path.isfile(path):
        raise CommandError('Notearkiv file not found')

    columnOrder = [] # Rekkefølge av felt for currentTable
    currentTable = '' # navnet på tabellen
    entries = {} # Mappe fra navn på tabeller til dictionaries som har innholdet demmers. 

    with open(path, 'r') as f:
        # Les inn databasen til en dict (fra tablenavn) med lister med dicts
        while line := f.readline():
            line = line.rstrip()
            if not line:
                continue

            line = line.replace('NULL', 'null') # Sett inn json formatering på null

            if line.startswith('INSERT INTO'):
                currentTable = line.split()[2][1:-1] # Skaff table navn
                columnOrder = json.loads('[' + line.split('(')[1].split(')')[0].replace('`', '"') + ']')

                if currentTable not in entries.keys():
                    entries[currentTable] = []

                continue

            if not currentTable or not line.startswith('('):
                # Fjern currentTable, samme line kan vær en ny insert into
                currentTable = ''
                continue

            # Her har vi en klassisk line med verdia, komplisert fordi vi ønske å bevar escaped quotes
            values = json.loads('[' + line[1:-2].replace('\\\'', '@').replace('\'', '"').replace('@', "\'") + ']')

            entries[currentTable].append(dict(zip(columnOrder, values)))

    # print(getEntry(entries['Arkivtabell'], arkivid=11))
    # [{'arkivid': 11, 'arkivnr': 202, 'kortype': 'mannskor', 'tittel': 'Drikkevise', 'lengde': '3:18', 'antallstemmer': 4, 'sakral': 0, 'solist': 0, 'instrument': '', 'kommentar': 'MILJØSANG', 'oppdatert': '0000-00-00 00:00:00'}]


    # Fiks Miljøsangheftet for begge koran. 
    tssMSHsangIder, tksMSHsangIder = [], []
    for arkivId, notehefteId in [(d['arkivid'], d['notehefteid']) for d in entries['note_notehefte']]:
        if notehefteId == 106: # NotehefteID for TSS MSH
            tssMSHsangIder.append(arkivId)
        elif notehefteId == 107: # NotehefteID for TKS MSH
            tksMSHsangIder.append(arkivId)

    tssMSHRep, created = Repertoar.objects.get_or_create(
        navn='MSH', 
        kor=Kor.objects.get(navn='TSS'), 
        synlig=True
    )
    tksMSHRep, created = Repertoar.objects.get_or_create(
        navn='MSH', 
        kor=Kor.objects.get(navn='TKS'), 
        synlig=True
    )

    # Generer sangan
    for sangIndex, sangDict in enumerate(objectsGenerator(entries['Arkivtabell'], save=False)):
        if not sangDict['tittel'] or not sangDict['tittel'].strip():
            continue

        # Det e 7 forskjellige sanga i TXS som hette 'Våren'...
        # Heller enn å gi opp på at vi skal ha unikhet i sanger i notearkivet foretrekk e å gjør at det telle oppover
        # Så får folk heller gå over i ettertid og prøv å fiks det
        unikSangNr = 0
        while True:
            try:
                sang, created = Sang.objects.get_or_create(
                    kor=Kor.objects.filter(navn=consts.Kor.TXS).first(), 
                    navn=sangDict['tittel'] + (f'_{unikSangNr}' if unikSangNr else ''),
                    kortype=(sangDict['kortype'].title() if sangDict['kortype'] != 'like stemmer' else 'Begge') if sangDict['kortype'] else ''
                )
                break
            except IntegrityError as e:
                # print('Generation failed due to duplicate: ' + sangDict['tittel'])
                unikSangNr += 1

        if (kommentar := sangDict['kommentar']):
            # Filtrer ut kommentara vi ikkje bryr oss om
            kommentarLinjer = kommentar.split('\n')
            kommentarLinjer = [k for k in kommentarLinjer if k != 'MILJØSANG']
            kommentarLinjer = [k for k in kommentarLinjer if not k.startswith('TKS arkivnummer')]
            if kommentarLinjer:
                sang.notis = '\n'.join(kommentarLinjer) + '\n'

        # Generer inn kæm som har arrangert/komponert/forfattet sangen
        for notePersonDict in filterEntries(entries['note_person'], arkivid=sangDict['arkivid']):
            if notePersonDict['personid'] == 0:
                continue
            
            person = filterEntries(entries['Personer'], personid=notePersonDict['personid'])[0]
            sang.notis += f'{notePersonDict["funksjon"]}: {person["fornavn"]} {person["etternavn"]}\n'

        # Deserialiser øverige felt
        if antallStemmer := sangDict['antallstemmer']:
            sang.notis += f'Antall stemmer: {antallStemmer}\n'

        if sangDict['sakral']:
            sang.notis += f'Sakral sang\n'

        if sangDict['solist']:
            sang.notis += f'Solist sang\n'

        if instrument := sangDict['instrument']:
            sang.notis += f'Instrument: {instrument}\n'

        if lengde := sangDict['lengde']:
            sang.notis += f'Lengde: {lengde}\n'

        sang.save()

        # Iterer over sangfiler og last dem ned fra MyTSS. 
        for sangFilDict in filterEntries(entries['Filoversikt'], arkivid=sangDict['arkivid']):
            # print('fil', sangFilDict)
            # {'arkivid': 9271, 'navn': 'Norge_alle.mp3', 'meta': 'Opplastet av TSM, 24.04.17', 'status': 'vis'}

            # Følgende filtyper lå i notearkivet, ja det va regex for å finn ut av det. 
            # sib|pdf|mid|mp3|PDF|avi|wmv|sib|doc|MID|wma|mp4|m4v|m4a|zip|docx|midi|png|musx|mscz|xml|rtf|bin|dorico|mxl
            # 13 av filnavnan mangle en filtype, men ingen av dem 13 har punktum i seg, så dette bli ganske greit ja:)
            sangFil = sang.filer.create(navn=sangFilDict['navn'])

            if filKommentar := sangFilDict['meta']:
                sang.notis += f'Fil {sangFil.navn} har kommentar: {filKommentar.strip()}\n'
                sang.save()

            sangFil.skjul = sangFilDict['status'] == 'skjul'

            # DETTE FUNKA, men det tar selvfølgelig my nett å last ned alt, og i den faktiske overføringa kjem ta her te å ta laaang tid. 
            # print('Request sent')
            res = http.request("GET", f"https://mannskor.no/notearkiv/filer/{sangFilDict['navn']}")

            if res.status != 200:
                print(f"Request for sang {sang.navn} and fil {sangFil.navn} got code {res.status}")

            # print(res.headers)
            # #  HTTPHeaderDict({'Server': 'nginx/1.14.0 (Ubuntu)', 'Date': 'Thu, 08 Aug 2024 18:09:09 GMT', 'Content-Type': 'audio/mpeg', 'Content-Length': '4116479', 'Connection': 'keep-alive', 'Last-Modified': 'Mon, 06 May 2019 19:30:02 GMT', 'ETag': '"5cd08b3a-3ecfff"', 'Accept-Ranges': 'bytes'})

            sangFil.fil = ContentFile(res.data, name=sangFilDict['navn'])
            # sangFil.fil = ContentFile(bytes(), name=sangFilDict['navn']) # WIP VERSJON SOM LAGE EN TOM FIL
            sangFil.save()

        # Sett inn sangen i (semester) repertoaran den ska vær i
        for repertoarDict in filterEntries(entries['Repertoar'], NoteID=sangDict['arkivid']):
            repertoar, created = Repertoar.objects.get_or_create(kor=Kor.objects.filter(navn=repertoarDict['kor']).first(), navn=str(repertoarDict['årstall']) + ' ' + repertoarDict['semester'])

            if created:
                repertoar.dato = datetime.date(year=repertoarDict['årstall'], month=1 if repertoarDict['semester'] == 'Vår' else 8, day=1)
                repertoar.save()

            sang.repertoar.add(repertoar)

        # Sett inn i miljøsanghefte
        if sangDict['arkivid'] in tssMSHsangIder:
            tssMSHRep.sanger.add(sang)
        if sangDict['arkivid'] in tksMSHsangIder:
            tksMSHRep.sanger.add(sang)

        # if sangIndex > 1000:
        #     break


def filterEntries(entries, **query):
    'Tar en liste med dictionaries, og returne alle verdian som matche queryet, ligne på om queryset.filter'
    return list(filter(lambda e: all(map(lambda kv: e[kv[0]] == kv[1], query.items())), entries))
