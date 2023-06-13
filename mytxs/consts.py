# Fil for å definere constans som går igjen over hele siden

bareKorKortTittel = ['TSS', 'Pirum', 'KK', 'Candiss', 'TKS']
alleKorKortTittel = ['TSS', 'Pirum', 'KK', 'Candiss', 'TKS', 'Sangern']
alleKorLangTittel = [
    'Trondhjems Studentersangforening',
    'Pirum',
    'Knauskoret',
    'Candiss',
    'Trondhjems Kvinnelige Studentersangforening',
    'Sangern bar'
]

korTilStemmeFordeling = [0, 0, 1, 2, 2]
stemmeFordeling = ['TB', 'SATB', 'SA']

tilganger = ['dekorasjon', 'dekorasjonInnehavelse', 'verv', 'vervInnehavelse', 'tilgang']
tilgangBeskrivelser = [
    'For å opprette og slette dekorasjoner, samt endre på eksisterende dekorasjoner.',
    'For å opprette og slette dekorasjonInnehavelser, altså hvem som fikk hvilken dekorasjon når.',
    'For å opprette og slette verv, samt endre på eksisterende verv.',
    'For å opprette og slette vervInnehavelser, altså hvem som hadde hvilket verv når. Dette inkluderer stemmegrupper.',
    'For å opprette og slette tilganger, samt endre på hvilket verv som medfører disse tilgangene.',
]

storkorTilganger = ['medlemsdata']
storkorTilgangBeskrivelser = [
    'For å kunne endre på medlemsdataene til de i ditt storkor.'
]

allModelNames = [
    'VervInnehavelse', 
    'Verv', 
    'DekorasjonInnehavelse', 
    'Dekorasjon', 
    'Tilgang', 
    'Logg',
    'Kor'
]

loggModelNames = [*(allModelNames[:5])]
'Models that are being logged'

hovedStemmegrupper = ["1S", "2S", "1A", "2A", "1T", "2T", "1B", "2B"]

defaultChoice = ('', '---------')