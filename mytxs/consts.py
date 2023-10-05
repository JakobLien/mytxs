# Fil for å definere constans som går igjen over hele siden

from django.apps import apps

alleKorKortTittel = ['TSS', 'TKS', 'Pirum', 'Knauskoret', 'Candiss', 'Sangern']
alleKorLangTittel = [
    'Trondhjems Studentersangforening',
    'Trondhjems Kvinnelige Studentersangforening',
    'Pirum',
    'Knauskoret',
    'Candiss',
    'Sangern bar'
]
alleKorStemmeFordeling = ['TB', 'SA', 'TB', 'SATB', 'SA', '']

# Subsets av alleKorKortTittel
bareKorKortTittel = ['TSS', 'TKS', 'Pirum', 'Knauskoret', 'Candiss']
bareStorkorKortTittel = ['TSS', 'TKS']

bareKorKortTittelTKSRekkefølge = ['TKS', 'TSS', 'Candiss', 'Knauskoret', 'Pirum']

tilganger = ['dekorasjon', 'dekorasjonInnehavelse', 'verv', 'vervInnehavelse', 'tilgang', 'semesterplan', 'fravær', 'lenke', 'turne', 'tversAvKor']
tilgangBeskrivelser = [
    'For å opprette og slette dekorasjoner, samt endre på eksisterende dekorasjoner.',
    'For å opprette og slette dekorasjonInnehavelser, altså hvem som fikk hvilken dekorasjon når.',
    'For å opprette og slette verv, samt endre på eksisterende verv.',
    'For å opprette og slette vervInnehavelser, altså hvem som hadde hvilket verv når. Dette inkluderer stemmegrupper.',
    'For å opprette og slette tilganger, samt endre på hvilket verv som medfører disse tilgangene.',
    'For å endre på semesterplanen til koret.',
    'For å føre fravær i koret.',
    'For å endre på korets lenker.',
    'For å administrere turnerer, samt endre hvem som deltok.',
    'For å kunne sette relasjoner til objekter i andre kor.',
]

storkorTilganger = ['medlemsdata']
storkorTilgangBeskrivelser = [
    'For å kunne endre på medlemsdataene til de i ditt storkor.'
]

alleTilganger = tilganger + storkorTilganger

# Hold denne lista i en rekkefølge vi ønske å slett de i, for seed --clear sin del:)
loggedModelNames = [
    'VervInnehavelse',
    'Verv',
    'DekorasjonInnehavelse',
    'Dekorasjon',
    'Medlem',
    'Tilgang',
    'Turne',
    'Oppmøte',
    'Hendelse',
    'Lenke'
]
'Names of models that are being logged'

def getLoggedModels():
    return list(map(lambda model: apps.get_model('mytxs', model), loggedModelNames))

loggModelNames = ['Logg', 'LoggM2M']
'Names of models that contain loggs'

def getLoggModels():
    return list(map(lambda model: apps.get_model('mytxs', model), loggModelNames))

otherModels = ['Kor']

allModelNames = [*loggedModelNames, *loggModelNames, *otherModels]

def getAllModels():
    return list(map(lambda model: apps.get_model('mytxs', model), allModelNames))

modelTilTilgangNavn = {
    'VervInnehavelse': 'vervInnehavelse',
    'Verv': 'verv',
    'DekorasjonInnehavelse': 'dekorasjonInnehavelse',
    'Dekorasjon': 'dekorasjon',
    'Medlem': 'medlemsdata',
    'Tilgang': 'tilgang',
    'Turne': 'turne',
    'Oppmøte': 'fravær',
    'Hendelse': 'semesterplan',
    'Lenke': 'lenke'
}
'Mappe fra model til navn på tilgang'

korAvhengerAv = {
    'VervInnehavelse': 'Verv',
    'DekorasjonInnehavelse': 'Dekorasjon',
    'Oppmøte': 'Hendelse',
}
'Modeller med hvilken model som koret til instanser avhenger av'

modelWithRelated = {
    'Medlem': ['VervInnehavelse', 'DekorasjonInnehavelse', 'Turne'],
    'Verv': ['VervInnehavelse', 'Tilgang'],
    'Dekorasjon': ['DekorasjonInnehavelse'],
    'Hendelse': ['Oppmøte']
}
'Modeller med hvilke relaterte modeller som gir lesetilgang på instans siden'

hovedStemmegrupper = ['1S', '2S', '1A', '2A', '1T', '2T', '1B', '2B']

# Denne brukes med BitmapMultipleChoiceField, så ALDRI (!!!) endre på rekkefølgen 
# eller alternativene her. Dette fordi verdiene lagres som en bit på tilsavrende index.
# Er trygt å gi nye navn til de, bare det forblir den samme informasjonen. 
sjekkhefteSynligOptions = [
    'fødselsdato', 
    'epost',
    'tlf',
    'studieEllerJobb',
    'boAdresse',
    'foreldreAdresse'
]

# Denne brukes blant annet på hendelse siden for fraværsføring, 
# bare hiv på en url på slutten så får du en qr kode som redirecte dit:)
qrCodeLinkPrefix = 'https://zxing.org/w/chart?cht=qr&chs=350x350&chld=L&choe=UTF-8&chl='
