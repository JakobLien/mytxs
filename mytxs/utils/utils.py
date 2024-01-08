from io import BytesIO
from PIL import Image

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
