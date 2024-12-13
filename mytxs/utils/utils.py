import datetime
from io import BytesIO
from PIL import Image
import certifi
import urllib3
urllib3.util.connection.HAS_IPV6 = False

from django.core.files import File

# Alle generelle ting ellers

def cropImage(imageFile, name, width, height):
    'Resize et bilde til width og height, og returne en (ulagret) file'
    bilde = Image.open(imageFile)

    # Fjern transparency
    bilde = bilde.convert('RGB')

    if bilde.width * height > bilde.height * width:
        # Height e den begrensende størrelsen
        relativeHeight = bilde.height
        relativeWidth = bilde.height * width / height
    else:
        # Width e den begrensende størrelsen
        relativeWidth = bilde.width
        relativeHeight = bilde.width * height / width

    # Klipp ut midta av bildet med rett proposjoner
    bilde = bilde.crop((
        bilde.width/2 - relativeWidth/2, 
        bilde.height/2 - relativeHeight/2, 
        bilde.width/2 + relativeWidth/2, 
        bilde.height/2 + relativeHeight/2
    ))

    # Om nødvendig, nedskaler til faktisk width og height
    if bilde.height > height:
        bilde = bilde.resize((width, height))

    bilde.verify()
    bildeBytes = BytesIO()
    bilde.save(bildeBytes, 'JPEG')
    return File(bildeBytes, name=name)


def getHalvårStart():
    halvårStart = datetime.date.today()
    return halvårStart.replace(month=(halvårStart.month // 7) * 6 + 1, day=1)


def getStemmegrupper(stemmefordeling, lengde=2, ekstraDybde=0):
    '''
    Stemmefordeling er 'SA', 'TB' eller 'SATB'. 
    Lengde er lengden av strengene vi skal ha. Dybde hiver på dypere lengder i tillegg.
    Alt kommer uansett i rett rekkefølge, f.eks. ['1S', '11S', '21S', '2S'] osv. 
    '''
    stemmegrupper = ','.join(stemmefordeling)

    for l in range(1, lengde+ekstraDybde):
        if l < lengde:
            # Bare øk lengden av alt
            stemmegrupper = ','.join([f'1{s},2{s}' for s in stemmegrupper.split(',')])
        else:
            # Øk og dupliser de lengste strengene
            stemmegrupper = ','.join([(f'{s},1{s},2{s}' if len(s) == l else s) for s in stemmegrupper.split(',')])
    
    return stemmegrupper.split(',')


def getCord(adresse):
    try:
        http = urllib3.PoolManager(
            cert_reqs="CERT_REQUIRED",
            ca_certs=certifi.where(),
            timeout=urllib3.Timeout(5)
        )

        cord = http.request("GET", 'https://ws.geonorge.no/adresser/v1/sok?sok='+adresse).json()
        if len(cord['adresser']) > 0:
            cord = cord['adresser'][0]['representasjonspunkt']
            del cord['epsg']

            return cord
    except:
        pass
