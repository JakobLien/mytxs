# Fil for å definere constans som går igjen over hele siden

from django.apps import apps


bareKorKortTittel = ['TSS', 'TKS', 'Pirum', 'KK', 'Candiss']
alleKorKortTittel = ['TSS', 'TKS', 'Pirum', 'KK', 'Candiss', 'Sangern']
alleKorLangTittel = [
    'Trondhjems Studentersangforening',
    'Trondhjems Kvinnelige Studentersangforening',
    'Pirum',
    'Knauskoret',
    'Candiss',
    'Sangern bar'
]

bareKorKortTittelTKSRekkefølge = ['TKS', 'TSS', 'Candiss', 'KK', 'Pirum']

korTilStemmeFordeling = [0, 2, 0, 1, 2]
stemmeFordeling = ['TB', 'SATB', 'SA']

tilganger = ['dekorasjon', 'dekorasjonInnehavelse', 'verv', 'vervInnehavelse', 'tilgang', 'semesterplan', 'fravær', 'lenke']
tilgangBeskrivelser = [
    'For å opprette og slette dekorasjoner, samt endre på eksisterende dekorasjoner.',
    'For å opprette og slette dekorasjonInnehavelser, altså hvem som fikk hvilken dekorasjon når.',
    'For å opprette og slette verv, samt endre på eksisterende verv.',
    'For å opprette og slette vervInnehavelser, altså hvem som hadde hvilket verv når. Dette inkluderer stemmegrupper.',
    'For å opprette og slette tilganger, samt endre på hvilket verv som medfører disse tilgangene.',
    'For å endre på semesterplanen til koret.',
    'For å føre fravær i koret.',
    'For å endre på korets lenker.',
]

storkorTilganger = ['medlemsdata']
storkorTilgangBeskrivelser = [
    'For å kunne endre på medlemsdataene til de i ditt storkor.'
]

loggedModelNames = [
    'VervInnehavelse',
    'Verv',
    'DekorasjonInnehavelse',
    'Dekorasjon',
    'Medlem',
    'Tilgang',
    'Hendelse',
    'Oppmøte',
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

hovedStemmegrupper = ['1S', '2S', '1A', '2A', '1T', '2T', '1B', '2B']

defaultChoice = ('', '---------')
