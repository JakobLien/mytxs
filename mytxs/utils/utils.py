import datetime
from io import BytesIO
from PIL import Image

from django.core.files import File
from django.db.models import Q, F

from mytxs.utils.viewUtils import downloadFile

# Alle generelle ting ellers

def generateVCard(medlemmer):
    'Returne et gyldig vcard innhold gitt et queryset av medlemmer'
    vCardContent = ''
    for medlem in medlemmer:
        vCardContent += f'''\
begin:vcard
version:4.0
fn:{medlem.navn}
tel;type=cell:{medlem.tlf.replace(' ', '')}
note:Generert av MyTXS 2.0 {datetime.date.today()}
end:vcard
'''
    return vCardContent


def downloadVCard(request):
    '''
    If request.GET.get('vcard'), bruk request.queryset (medlemmer), og returne et vCard downloadFile response. Bruk:
    ```
    if vCardRes := downloadVCard(request):
        return vCardRes
    ```'''
    if request.GET.get('vcard'):
        content = generateVCard(request.queryset.annotate(
            sjekkhefteSynligTlf=F('sjekkhefteSynlig').bitand(2**2)
        ).exclude(Q(tlf='') | Q(sjekkhefteSynligTlf=0)))
        print(content)
        return downloadFile('MyTXS.vcf', content)


def cropImage(imageFile, name, width, height):
    'Resize et bilde til width og height, og returne en (ulagret) file'
    bilde = Image.open(imageFile)

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
