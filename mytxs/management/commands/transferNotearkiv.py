import datetime
import os
import certifi
import urllib3
import json

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError

from mytxs import consts
from mytxs.management.commands.updateField import objectsGenerator
from mytxs.models import Kor, Repertoar, Sang, SangFil

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
    
    tableStructure = [] # Hvilket felt som e kor for currentTable
    currentTable = '' # navnet på tabellen
    entries = {} # Mappe fra navn på tabeller til dictionaries som har innholdet demmers. 

    stemmegrupper = {'sopran': 'S', 'alt': 'A', 'tenor': 'T', 'bass': 'B'}
    for k, v in dict(**stemmegrupper).items():
        stemmegrupper[k[:3]] = v
        stemmegrupper[k[:1]] = v

    with open(path, 'r') as f:
        # Les inn databasen til en dict (fra tablenavn) med lister med dicts
        while line := f.readline():
            line = line[:-1] # Fjern newline på slutten av hver line

            line = line.replace('\\r\\n', '\\n')

            line = line.replace('NULL', 'null') # Sett inn json formatering på null

            if line.startswith('INSERT INTO'):
                # Sett table og struktur
                currentTable = line.split()[2][1:-1]
                tableStructure = json.loads('[' + line.split('(')[1].split(')')[0].replace('`', '"') + ']')

                if currentTable not in entries.keys():
                    entries[currentTable] = []

                continue

            if not currentTable or not line.startswith('('):
                # Fjern currentTable, samme line kan vær en ny insert into
                currentTable = ''
                continue

            # Her har vi en klassisk line med verdia, komplisert fordi vi ønske å bevar escaped quotes
            values = json.loads('[' + line[1:-2].replace('\\\'', '@').replace('\'', '"').replace('@', "\'") + ']')

            entries[currentTable].append(dict(zip(tableStructure, values)))

        # print(getEntry(entries['Arkivtabell'], arkivid=11))
        # [{'arkivid': 11, 'arkivnr': 202, 'kortype': 'mannskor', 'tittel': 'Drikkevise', 'lengde': '3:18', 'antallstemmer': 4, 'sakral': 0, 'solist': 0, 'instrument': '', 'kommentar': 'MILJØSANG', 'oppdatert': '0000-00-00 00:00:00'}]

        # Generer sangan
        for sangDict in objectsGenerator(entries['Arkivtabell'], save=False):
            if not sangDict['tittel']:
                continue

            # TODO: Håndter kortype og si hvilket kor sangen skal tilhøre
            sang, created = Sang.objects.get_or_create(kor=Kor.objects.filter(navn=consts.Kor.TXS).first(), navn=sangDict['tittel'])

            if (kommentar := sangDict['kommentar']):
                # Filtrer ut kommentara vi ikkje bryr oss om
                kommentar = kommentar.split('\n')
                kommentar = [k for k in kommentar if k != 'MILJØSANG']
                kommentar = [k for k in kommentar if not k.startswith('TKS arkivnummer')]
                if kommentar:
                    sang.notis = '\n'.join(kommentar) + '\n'

            # Generer inn kæm som har skreve sangen
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

                sangFil, created = sang.filer.get_or_create(navn=sangFilDict['navn'])

                if kommentar := sangFilDict['meta']:
                    sang.notis += f'Fil {sangFil.navn} har kommentar: {kommentar}\n'
                    sang.save()

                sangFil.skjul = sangFilDict['status'] == 'skjul'

                # Gjett på stemmegruppe
                filNavnUtenSangNavn = splitAlphaNumeric(sangFilDict['navn'].lower().replace(sangDict['tittel'].lower(), ''))
                for i, aplhaNumeric in enumerate(filNavnUtenSangNavn):
                    if aplhaNumeric not in stemmegrupper.keys():
                        continue
                
                    stemmegruppe = stemmegrupper[aplhaNumeric]
                    # Flipp delen av navnet som e før stemmegruppa 
                    filNavnUtenSangNavn = [*filNavnUtenSangNavn[i::-1][1:], *filNavnUtenSangNavn[i+1:]]
                    for part in filNavnUtenSangNavn:
                        if part.isnumeric() and 1 <= int(part) <= 2:
                            stemmegruppe += part
                            if len(stemmegruppe) >= 3:
                                break
                    
                    sangFil.stemmegruppe = stemmegruppe[::-1]
                    break

                # TODO: DETTE FUNKA, men det tar selvfølgelig my nett å last ned alt, og i den faktiske overføringa kjem ta her te å ta laaang tid. 
                # # print('Request sent')
                # res = http.request("GET", f"https://mannskor.no/notearkiv/filer/{sangFil.navn}")

                # # print(res.headers)
                # # #  HTTPHeaderDict({'Server': 'nginx/1.14.0 (Ubuntu)', 'Date': 'Thu, 08 Aug 2024 18:09:09 GMT', 'Content-Type': 'audio/mpeg', 'Content-Length': '4116479', 'Connection': 'keep-alive', 'Last-Modified': 'Mon, 06 May 2019 19:30:02 GMT', 'ETag': '"5cd08b3a-3ecfff"', 'Accept-Ranges': 'bytes'})

                # sangFil.fil = ContentFile(res.data, name=sangFil.navn)
                sangFil.fil = ContentFile(bytes(), name=sangFil.navn) # TODO: MIDLERTIDIG VERSJON SOM LAGE EN TOM FIL
                sangFil.save()

            # Sett inn sangen i (semester) repertoaran den ska vær i
            for repertoarDict in filterEntries(entries['Repertoar'], NoteID=sangDict['arkivid']):
                repertoar, created = Repertoar.objects.get_or_create(kor=Kor.objects.filter(navn=repertoarDict['kor']).first(), navn=str(repertoarDict['årstall']) + ' ' + repertoarDict['semester'])

                if created:
                    repertoar.dato = datetime.date(year=repertoarDict['årstall'], month=1 if repertoarDict['semester'] == 'Vår' else 7, day=1)
                    repertoar.save()

                sang.repertoar.add(repertoar)

            # break


def filterEntries(entries, **query):
    'Tar en liste med dictionaries, og returne alle verdian som matche queryet, ligne på om queryset.filter'
    return list(filter(lambda e: all(map(lambda kv: e[kv[0]] == kv[1], query.items())), entries))


def splitAlphaNumeric(string):
    l = ['']
    for c in string:
        if not l[-1] and (c.isnumeric() or c.isalpha()):
            l[-1] += c
        elif l[-1].isnumeric() and c.isnumeric():
            l.append(c)
        elif l[-1].isalpha() and c.isalpha():
            l[-1] += c
        elif c.isnumeric() or c.isalpha():
            l.append(c)
        elif l[-1] != '':
            l.append('')
    return l
