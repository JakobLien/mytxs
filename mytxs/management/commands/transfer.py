import base64
import certifi
import datetime
import json
import os
import re
import urllib3

# Så greia e at MyTXS 1.0 servern supporte ikkje ipv6, og samfundet har ipv6 som default.
# Dette lede til at dersom vi ikkje eksplisit spesifisere at vi må bruk ipv4 får vi en bug
# på servern som vi ikke får lokalt, og som e no har brukt 3 tima på å debug med itk. Ikke 
# gjør samme feilen igjen!
urllib3.util.connection.HAS_IPV6 = False

from PIL import Image

from django.core.files import File
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError

from mytxs.models import Dekorasjon, DekorasjonInnehavelse, Kor, Medlem, Turne, Verv, VervInnehavelse
from mytxs.utils.modelUtils import stemmegruppeVerv

class Command(BaseCommand):
    help = 'Pull data from the old site, using key specified in .env'

    def handle(self, *args, **options):
        transferAll(self)

def transferAll(self):
    if 'API_KEY' not in os.environ:
        raise CommandError(f'API_KEY ikke not in env varables')

    http = urllib3.PoolManager(
        cert_reqs="CERT_REQUIRED",
        ca_certs=certifi.where()
    )

    tssResp = http.request("GET", "https://mytss.mannskor.no/api/medlem", headers={
        "Authorization": f"Bearer {os.environ['API_KEY']}"
    })

    tksResp = http.request("GET", "https://mitks.mannskor.no/api/medlem", headers={
        "Authorization": f"Bearer {os.environ['API_KEY']}"
    })

    medlemmerDict = [*tssResp.json(), *tksResp.json()]

    print(f'{len(medlemmerDict)} medlemmer')
    
    for i, medlemDict in enumerate(medlemmerDict):
        if i%20 == 0:
            print(i)
        insertMedlem(medlemDict)
        # Tar kanskje 10 min

    # f = open("temp.json", "w")
    # f.write(json.dumps(getDomainWithCountByKor(medlemmerDict, 'sluttet'), indent=4))
    # f.close()

    # Finn folk som har vervet i høst og vår samme år
    # for medlemDict in medlemmerDict:
    #     semesterVervsDict = [*filter(lambda v: v.get('semester'), parseVervSemester(medlemDict.get('verv', [])))]
    #     for i in range(len(semesterVervsDict)):
    #         for j in range(i+1, len(semesterVervsDict)):
    #             if semesterVervsDict[i]['aar'] == semesterVervsDict[j]['aar'] and semesterVervsDict[i]['verv'] == semesterVervsDict[j]['verv']:
    #                 print(medlemDict['medlemsnummer'])

    # python3 -m cProfile manage.py transfer > cProfile.txt

    # python3 manage.py seed --clear --clearLogs --userAdmin; python3 manage.py transfer


def transferByJWT(jwt):
    'Gitt en jwt fra MyTXS 1 importere denne metoden medlemsdataen fra MyTXS 1, og returne medlemmet som ble opprettet.'
    if 'API_KEY' not in os.environ:
        raise RuntimeError(f'API_KEY ikke not in env varables')

    http = urllib3.PoolManager(
        cert_reqs="CERT_REQUIRED",
        ca_certs=certifi.where()
    )

    medlemsnummer = json.loads(base64.b64decode(jwt.split('.')[1]+'==', altchars='-_'))['sub']

    if medlemsnummer.startswith('TSS'):
        medlemDict = http.request("GET", f"https://mytss.mannskor.no/api/medlem/{medlemsnummer[3:]}?jwt={jwt}", headers={
            "Authorization": f"Bearer {os.environ['API_KEY']}"
        }).json()
    elif medlemsnummer.startswith('TKS'):
        medlemDict = http.request("GET", f"https://mitks.mannskor.no/api/medlem/{medlemsnummer[3:]}?jwt={jwt}", headers={
            "Authorization": f"Bearer {os.environ['API_KEY']}"
        }).json()
    else:
        print('Faulty jwt:', jwt)
        return None

    # Her setter vi bare inn all data dersom medlemmet ikke allerede finnes. 
    # Dette løser problemet med innsetting av verv som har endret start dato på, med overlappende periode. 
    if Medlem.objects.filter(gammeltMedlemsnummer=medlemDict['medlemsnummer']).exists():
        return insertMedlemOptional(medlemDict)
    else:
        insertMedlem(medlemDict)
        return insertMedlemOptional(medlemDict)


def insertMedlemOptional(medlemDict):
    '''
    Gitt en medlemDict fra MyTXS 1 sett denne funksjonen inn all optional overføringsdata. 
    Er trygg å bruke flere ganger, vil i såfall ikke overskrive dataen som alt finnes på MyTXS 2.0. 
    '''
    medlem = Medlem.objects.filter(gammeltMedlemsnummer=medlemDict['medlemsnummer']).first()

    if not medlem:
        print('Medlem not found at insertMedlemOptional:', medlemDict['medlemsnummer'])
        return None

    # Sett inn medlemsdata som varierer om vi mottar pga avkrysning. Tanken er at om noen trykker på 
    # registeringslenken flere ganger med ulik avkrysning skal ikke siden slette data pga det.
    if not medlem.fødselsdato and (fødselsdato := medlemDict.get('fodselsdag')):
        medlem.fødselsdato = fødselsdato
    if not medlem.epost and (epost := medlemDict.get('email', '')):
        medlem.epost = epost
    if not medlem.tlf and (tlf := medlemDict.get('mobiltlf', '')):
        medlem.tlf = tlf
    if not medlem.studieEllerJobb and (studieEllerJobb := joinMaybeFalsy(' ved ', medlemDict.get('yrke'), medlemDict.get('arbeidssted'))):
        medlem.studieEllerJobb = studieEllerJobb
    if not medlem.boAdresse and (boAdresse := joinMaybeFalsy(', ', medlemDict.get('boligadresse'), medlemDict.get('boligpost'))):
        medlem.boAdresse = boAdresse
    if not medlem.foreldreAdresse and (foreldreAdresse := joinMaybeFalsy(', ', medlemDict.get('hjemadresse'), medlemDict.get('hjempost'))):
        medlem.foreldreAdresse = foreldreAdresse
    if not medlem.notis and (notis := medlemDict.get('anmerkninger', '')):
        medlem.notis = notis + '\n'

    # Lagre bildet
    if not medlem.bilde and (imgData := medlemDict.get('passfoto')):
        medlem.bilde = File(ContentFile(base64.b64decode(imgData)), name=f'uploads/sjekkhefteBilder/{medlem.pk}.jpg')
    
    medlem.save()

    return medlem


def insertMedlem(medlemDict):
    '''
    Gitt en medlemDict fra MyTXS 1 sett denne funksjonen inn all obligatosik overføringsdata. 
    Er ikke trygg å bruke flere ganger, for dersom et verv har blitt endret startdato 
    på, vil det bli forsøkt satt inn, og valideringen vil raise ValidationException. 
    '''
    kor = Kor.objects.get(
        kortTittel=medlemDict['medlemsnummer'][:3]
    )

    # Opprett medlemmet
    medlem, created = Medlem.objects.get_or_create(
        gammeltMedlemsnummer=medlemDict['medlemsnummer'],
        defaults={
            'fornavn': medlemDict['fornavn'],
            'mellomnavn': medlemDict.get('mellomnavn', ''),
            'etternavn': medlemDict['etternavn'],
            'ønskerVårbrev': medlemDict.get('status') == 'Sluttet (skal ha vårbrev)' or medlemDict.get('status') == 'Støttemedlem',
            'død': medlemDict.get('status') == 'Død'
        }
    )

    # Stemmegrupper (i storkor)
    # Om noen har byttet stemmegruppe kan vi finne ut av dette ved å se på de to siste tallene av medlemsnummeret,
    # men siden det er umulig å vite når de byttet foretrekker jeg å bare si at de alltid var den stemmegruppen de
    # ble til slutt.
    # Alle som har Dirigent stemmegruppen har et tilsvarende dirrigent verv, så denne informasjonen ser vi bort fra her 
    stemmeGruppeMapping = {
        '1. Sopran': '1S',
        '2. Sopran': '2S',
        '1. Alt': '1A',
        '2. Alt': '2A',
        '1.tenor': '1T',
        '2.tenor': '2T',
        '1.bass': '1B',
        '2.bass': '2B',
    }

    stemmegruppe = None

    if medlemDict.get('stemmegruppe') in stemmeGruppeMapping.keys():
        # Om de har en stemmegruppe, velg den tilsvarende
        stemmegruppe = Verv.objects.get(
            kor=kor,
            navn=stemmeGruppeMapping[medlemDict['stemmegruppe']]
        )
    elif (stemmeGruppeInt := int(medlemDict['medlemsnummer'][7:9]) // 20) < 4 and not feilMedlemsnummer(medlemDict):
        # Ellers, gjett på stemmegruppen deres basert på medlemsnummer, om medlemsnummeret ikke er før korets grunneggelse
        if kor.kortTittel == 'TSS':
            stemmeGruppeInt += 4
        
        stemmegruppe = Verv.objects.get(
            kor=kor,
            navn=[*stemmeGruppeMapping.values()][stemmeGruppeInt]
        )
    elif ('Sluttet' in medlemDict.get('status', '') or medlemDict.get('sluttet')):
        # Ellers, gi de ukjentStemmegruppe dersom de enten har status sluttet eller noe på sluttet feltet
        stemmegruppe = Verv.objects.get(
            kor=kor,
            navn='ukjentStemmegruppe'
        )
    
    # Dette er så mye vi fornuftig kan annta om folk var aktive. Om folk har en stemmegruppe bruker vi det. 
    # Om ikkje ser vi på medlemsnummeret, dersom det er gyldig. Om ikke det heller sjekker vi om de har status 
    # sluttet, eller noe skrevet på sluttet feltet, og da får de ukjentStemmegruppe. 

    if stemmegruppe:
        if feilMedlemsnummer(medlemDict):
            if stemmegruppe.navn != 'ukjentStemmegruppe':
                medlem.notis += f'Ukjent start, sang antageligvis {stemmegruppe.navn}\n'
            else:
                medlem.notis += f'Ukjent start og stemmegruppe\n'
        else:
            # Om vi har et stemmegruppeverv
            start = datetime.date(int(medlemDict['medlemsnummer'][3:7]), 9, 1)

            slutt = parseSluttet(medlemDict.get('sluttet'))

            if slutt and slutt < start:
                # Dersom vi tror de sluttet før start, gjett at de bare va med ett semester
                slutt = datetime.date(start.year, 12, 31)
                medlem.notis += f'Sluttet før start: "{medlemDict.get("sluttet")}", gjetter sluttet samme semester som start\n'
            elif not slutt and medlemDict.get('status') not in ['Aktiv', 'Permittert']:
                # Alle som ikke e aktiv eller permitert har sluttet, så gjett ett år seinar
                slutt = datetime.date(start.year + 1, 5, 17)
                medlem.notis += f'Ukjent sluttet: "{medlemDict.get("sluttet")}", gjetter etter ett år\n'
            
            VervInnehavelse.objects.get_or_create(
                medlem=medlem,
                verv=stemmegruppe,
                start=start,
                slutt=slutt
            )
    

    # Dekorasjoner
    if dekorasjonerDict := medlemDict.get('dekorasjoner'):
        for dekorasjonDict in dekorasjonerDict:
            dekorasjon, created = Dekorasjon.objects.get_or_create(
                navn=dekorasjonDict['beskrivelse'],
                kor=kor
            )

            # Det er 5 dekorasjonDict som har aar = 0 ...
            if dekorasjonDict['aar'] == 0:
                medlem.notis += f'Usikker dekorasjonstart for "{dekorasjonDict["beskrivelse"]}"\n'
                

            DekorasjonInnehavelse.objects.get_or_create(
                medlem=medlem,
                dekorasjon=dekorasjon,
                start=datetime.date(dekorasjonDict['aar'] or getSluttetÅr(medlemDict, medlem), 1, 1)
            )


    # Turneer
    if turneerDict := medlemDict.get('turne'):
        for turneDict in turneerDict:
            turne, created = Turne.objects.get_or_create(
                navn=turneDict['turne'],
                kor=kor,
                start=datetime.date(turneDict['aar'], 1, 1)
            )

            turne.medlemmer.add(medlem)


    # Verv
    # Utfordringen med verv er at om man har et verv over flere år er det i det gamle systemet
    # representert som flere urelaterte "vervInnehavelser", mens jeg ønsker å representere det som
    # en vervInnehavelse med start og slutt som kan vare flere år. Derfor slår følgende kode
    # sammen samme vervInnehavelse over flere år, og hånterer også om vervet var bare våren eller 
    # høsten, ved å lese navnet og kommentaren. Tar også hånd om småkor/sangern verv. 
    if vervsDict := medlemDict.get('verv'):
        # Sorter så vervene kommer kronologisk
        vervsDict.sort(key=lambda v: v['aar'])
        # Tolk om vervet var bare høst eller vår basert på tittel og kommentar
        # Dette lagres på vervet som semster: 'høst' eller semester: 'vår'
        vervsDict = parseVervSemester(vervsDict)
        # Slå sammen om samme verv var både høst og vår
        vervsDict = mergeVervSemester(vervsDict)

        # For hvert verv
        while vervsDict and (vervDict := vervsDict.pop(0)):
            # Håndter semester for vervet
            start = datetime.date(vervDict['aar'], 1, 1)
            slutt = datetime.date(vervDict['aar'], 12, 31)
            semester = vervDict.get('semester')
            if semester == 'vår':
                slutt = datetime.date(vervDict['aar'], 5, 17)
            elif semester == 'høst':
                start = datetime.date(vervDict['aar'], 8, 15)
            
            # Håndter sammenslåing av påfølgende verv, dersom vervet vare til nyttår
            if semester != 'vår':
                # Må loop over en kopi for å få den te å håndter fjerning av elementer underveis skikkelig
                for nesteVervDict in vervsDict[:]:
                    if nesteVervDict['aar'] < slutt.year + 1:
                        # No e vi før året av interesse, som skjer like etter vi øke slutt
                        continue
                    elif nesteVervDict['aar'] > slutt.year + 1:
                        # Om vi har gått forbi det neste året, heng ikke vervDict sammen med noen flere verv
                        break
                    elif nesteVervDict['verv'] == vervDict['verv'] and nesteVervDict.get('semester') != 'høst':
                        # Samme verv neste år, så fjern fra vervsDict og øk varigheten
                        vervsDict.remove(nesteVervDict)

                        if nesteVervDict.get('semester') == 'vår':
                            # Om vervet bare e på våren, vil det sammenslås videre
                            slutt = datetime.date(nesteVervDict['aar'], 5, 17)
                            break
                        else:
                            slutt = datetime.date(nesteVervDict['aar'], 12, 31)

            verv = None

            # disse keysa dekker (såvidt jeg ser) alle verv som åpenbart hører til et av småkorene. 
            # Dette dekker ikke PC(TKS) og Kruser(TSS/TKS), men disse vil jeg sterkt råde korlederne om
            # at vi sletter, siden å være ferdig i et småkor ikke er et verv, det er bare dataduplisering. 
            småkorKeywordToKor = {
                'pirum': 'Pirum',
                'knaus': 'Knauskoret',
                'candiss': 'Candiss'
            }

            # Sjekk om det e et småkorverv
            for keyword, småkor in småkorKeywordToKor.items():
                if keyword in vervDict['verv'].lower():
                    # Dersom det e medlemskapsvervet, gi de ukjentStemmegruppe vervet
                    if vervDict['verv'] in ['Pirum', 'Knauskoret', 'Candiss']:
                        vervDict['verv'] = 'ukjentStemmegruppe'

                    # Dersom det e dirigentvervet, gi de dirigent vervet
                    if vervDict['verv'] in ['Pirumdirigent', 'Knausdirigent', 'Candiss-dirigent']:
                        vervDict['verv'] = 'Dirigent'

                    verv, created = Verv.objects.get_or_create(
                        navn=vervDict['verv'],
                        kor=Kor.objects.get(kortTittel=småkor)
                    )
                    
                    break

            # Sjekk om det er et sangernVerv
            if vervDict['verv'] in ['Barens økonomisjef', 'Hybelansvarlig', 'Barrevisor', 'Bardeputy', 'Barsjef']:
                verv, created = Verv.objects.get_or_create(
                    navn=vervDict['verv'],
                    kor=Kor.objects.get(kortTittel='Sangern')
                )

            # Opprett vervet som vanlig i medlemmets kor ellers
            if not verv:
                verv, created = Verv.objects.get_or_create(
                    navn=vervDict['verv'],
                    kor=kor
                )

            VervInnehavelse.objects.get_or_create(
                medlem=medlem,
                verv=verv,
                start=start,
                slutt=slutt
            )
    

    # Spesielle statuser
    if (innbudtVervInnehavelse := VervInnehavelse.objects.filter(
        medlem=medlem,
        verv__navn='Innbudt medlem',
        verv__kor=kor
    ).first()) or medlemDict.get('status') == 'Innbudt':
        # Gi de med "Innbudt medlem" status eller vervInnehavelse den tilsvarende dekorasjonen på året de sluttet
        # Som del av dette bytter vi innbudt medlem fra å være et verv til å være en dekorasjon, fordi det gir 
        # vesentlig my meir meining. Etter overføring kan vi da bare slett vervet som ingen har, så e vi good:)
        innbudtDekorasjon, created = Dekorasjon.objects.get_or_create(
            navn='Innbudt medlem',
            kor=kor
        )

        if innbudtVervInnehavelse:
            DekorasjonInnehavelse.objects.get_or_create(
                medlem=medlem,
                dekorasjon=innbudtDekorasjon,
                start=datetime.date(innbudtVervInnehavelse.start.year, 1, 1)
            )
            innbudtVervInnehavelse.delete()
        else:
            DekorasjonInnehavelse.objects.get_or_create(
                medlem=medlem,
                dekorasjon=innbudtDekorasjon,
                start=datetime.date(getSluttetÅr(medlemDict, medlem), 1, 1)
            )
    elif medlemDict.get('status') == 'Støttemedlem':
        # Bare noter dette på medlemmet, det er snakk om 4 medlemmer og ingen tilsvarende verv/dekorasjoner som jeg finner. 
        medlem.notis += f'Medlemmet har status Støttemedlem\n'

    # Dersom de er Dirigent og mangler vervet
    if medlemDict.get('stemmegruppe') == 'Dirigent' and not VervInnehavelse.objects.filter(
        medlem=medlem,
        verv__navn='Dirigent',
        verv__kor=kor
    ).exists():
        medlem.notis += f'Medlemmet er Dirigent med ukjent periode\n'

    medlem.save()

    return medlem


def feilMedlemsnummer(medlemDict):
    '''
    Det er hundrevis av TKSere med "feil medlemsnummer", som har år før 1930. Se bort fra disse
    Er også en par TSSere med "feil medlemsnummer", som har år før 1910. 
    '''
    return (medlemDict['medlemsnummer'][:3] == 'TKS' and int(medlemDict['medlemsnummer'][3:7]) < 1930) or \
           (medlemDict['medlemsnummer'][:3] == 'TSS' and int(medlemDict['medlemsnummer'][3:7]) < 1910)


def parseSluttet(sluttet):
    'Returne date tilsvarende et godt gjett på når medlemmet sluttet eller None'
    if sluttet:
        year = int(''.join([s for s in sluttet if s.isdigit()] or '0'))

        if str(year) not in sluttet:
            # Dersom sluttet inneholder tall som er separerte, ikke prøv å tolk det. 
            # Fra datasettet har vi her: 10.02 og h81v93, og begge disse vil måtte gås over manuelt.
            return None

        if year < 100:
            if year < 30:
                year += 2000
            else:
                year += 1900
        elif not 1900 < year < 2030:
            return None

        if 'h' in sluttet.lower():
            # De sluttet på høsten av dette året
            return datetime.date(year, 12, 31)
        else:
            # Ellers annta at de sluttet på våren, siden det er vanligst
            return datetime.date(year, 5, 17)

    return None


def getSluttetÅr(medlemDict, medlem):
    'Skaffe et gjett på året medlemmet sluttet, nyttig for dekorasjoner fra år 0, og å gjette når de ble innbudt medlem:)'
    if sisteSGVerv := VervInnehavelse.objects.filter(
        stemmegruppeVerv(includeDirr=True),
        medlem=medlem
    ).order_by('slutt').last():
        return sisteSGVerv.slutt.year
    
    # Dette hjelper om de ikke har et stemmegruppe/dirr verv, men har satt sluttet
    if sluttet := parseSluttet(medlemDict.get('sluttet')):
        return sluttet.year

    return int(medlemDict['medlemsnummer'][3:7])


def parseVervSemester(vervsDict):
    '''
    Dersom vervet slutter med tegn og ordene høst eller vår, fjern det fra navnet, 
    og hiv på semester = høst eller semester = vår på dicten. 
    Parser og fjerner også kommentarer på verv som nevner høst og vår
    '''
    for vervDict in vervsDict:
        # Om det nevner vår eller høst i tittelen
        if match := re.search(r'[^\w]((høst)|(vår))([^\w]|$)', vervDict['verv']):
            # Fjern høst/vår og ka enn ikke boksava på slutten av navnet
            vervDict['verv'] = vervDict['verv'].replace(match[1], '')
            while not vervDict['verv'][-1].isalpha():
                vervDict['verv'] = vervDict['verv'][:-1]
            
            if match[1] == 'høst':
                vervDict['semester'] = 'høst'
            elif match[1] == 'vår':
                vervDict['semester'] = 'vår'
            else:
                raise Exception(f'Somethings wrong in parseVervSemester {vervsDict}')
        if kommentar := vervDict.get('kommentar'):
            # E har sett over kommentaran og det e fair å si at om dem nevne vår eller høst, e det det vervet er. 
            if 'høst' in kommentar.lower() or 'haust' in kommentar.lower():
                vervDict['semester'] = 'høst'
                del vervDict['kommentar']
            elif 'vår' in kommentar.lower():
                vervDict['semester'] = 'vår'
                del vervDict['kommentar']
    return vervsDict


def mergeVervSemester(vervsDict):
    '''
    Slår sammen verv høst og vår til ett verv hele året. 
    Håndtere også duplicates uansett semester-helårs kombinasjon.
    Trenger å få vervene i kronologisk rekkefølge for år (ikke semester). 
    '''
    for i, vervDict1 in enumerate(vervsDict):
        # Om vervet har semester
        for vervDict2 in vervsDict[i+1:]:
            if vervDict1['aar'] != vervDict2['aar']:
                # Om det e et anna år har denne vervInnehavelsen ingen duplicates
                break
            if vervDict1['verv'] != vervDict2['verv']:
                # Om det e et anna verv, leit videre
                continue

            # Om det e samme år og samme verv
            if vervDict1.get('semester') == vervDict2.get('semester'):
                # Begge vervene har samme semester (eller ingen semester), fjern en av de
                vervsDict.remove(vervDict2)
                continue
            if not vervDict2.get('semester'):
                # Bare vervDict2 e heilårs, fjern vervDict1
                vervsDict.remove(vervDict1)
                # Med vervDict1 fjernet kan vi trygt gå videre til neste vervDict
                break
            if not vervDict1.get('semester'):
                # Bare vervDict1 e heilårs, fjern vervDict2
                vervsDict.remove(vervDict2)
                # Leit videre etter fleire duplicates av dette vervet
                continue

            # Om vi har kommet hit har vi to verv, som har vår og høst.
            # Da endre vi så vervDict1 vare heile året, og slette vervDict2
            del vervDict1['semester']
            vervsDict.remove(vervDict2)
    
    return vervsDict


def joinMaybeFalsy(separator, *args):
    'Utility metode som slår sammen args som kan være falsy med separator dersom de ikke er det'
    returnValue = ''
    for arg in args:
        if arg:
            if returnValue:
                returnValue += separator
            returnValue += arg
    return returnValue


# Følgende funksjoner brukes ikkje av resten av koden, er bare for å analysere domenet av felt,
# for å kunne vite hva vi må ta høyde for. 

def getDomain(dictOrList, currProp, *path, includeNone=True):
    'Rekursiv metode som skaffer alle verdier for feltet'
    if isinstance(dictOrList, list):
        returnList = set()
        for subDictOrList in dictOrList:
            returnList.update(getDomain(subDictOrList, currProp, *path, includeNone=includeNone))
        return [*returnList]
    currValue = dictOrList.get(currProp)
    if not currValue:
        if includeNone:
            return [None]
        return []
    if not path:
        return [currValue]
    else:
        return getDomain(currValue, *path, includeNone=includeNone)


def getDomainWithCount(dictOrList, currProp, *path, includeNone=True):
    'Rekursiv metode som skaffer alle verdier for feltet med count'
    if isinstance(dictOrList, list):
        returnDict = {}
        for subDictOrList in dictOrList:
            for value, count in getDomainWithCount(subDictOrList, currProp, *path, includeNone=includeNone).items():
                returnDict.setdefault(value, 0)
                returnDict[value] += count
        return returnDict
    currValue = dictOrList.get(currProp)
    if not currValue:
        if includeNone:
            return {None: 1}
        return {}
    if not path:
        return {currValue: 1}
    else:
        return getDomainWithCount(currValue, *path, includeNone=includeNone)


def getDomainWithCountByKor(dictOrList, currProp, *path, includeNone=True, kor=None):
    'Rekursiv metode som skaffer alle verdier for feltet med count, og returne antall separert på kor'
    if isinstance(dictOrList, list):
        returnDict = {}
        for subDictOrList in dictOrList:
            for navn, korDict in getDomainWithCountByKor(subDictOrList, currProp, *path, includeNone=includeNone, kor=kor).items():
                returnDict.setdefault(navn, {})
                for korNavn, count in korDict.items():
                    returnDict[navn].setdefault(korNavn, 0)
                    returnDict[navn][korNavn] += count
        return returnDict
    
    if medlemsnummer := dictOrList.get('medlemsnummer'):
        kor = medlemsnummer[:3]

    currValue = dictOrList.get(currProp)
    if not currValue:
        if includeNone:
            return {None: {kor: 1}}
        return {}
    if not path:
        return {currValue: {kor: 1}}
    else:
        return getDomainWithCountByKor(currValue, *path, includeNone=includeNone, kor=kor)
