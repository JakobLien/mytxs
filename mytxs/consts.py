# Fil for å definere constans som går igjen over hele siden

class Kor:
    TSS = 'TSS'
    TKS = 'TKS'
    Pirum = 'Pirum'
    Knauskoret = 'Knauskoret'
    Candiss = 'Candiss'
    Sangern = 'Sangern'
    TXS = 'TXS'

alleKorNavn = [Kor.TSS, Kor.TKS, Kor.Pirum, Kor.Knauskoret, Kor.Candiss, Kor.Sangern, Kor.TXS]
alleKorTittel = [
    'Trondhjems Studentersangforening',
    'Trondhjems Kvinnelige Studentersangforening',
    'Pirum',
    'Knauskoret',
    'Candiss',
    'Sangern bar',
    'Begge Trondhjems Studentersangforeninger'
]
alleKorStemmeFordeling = ['TB', 'SA', 'TB', 'SATB', 'SA', '', '']

# Subsets av alleKorNavn
bareTilgangKorNavn = alleKorNavn[:6]
bareKorNavn = alleKorNavn[:5]
bareStorkorNavn = alleKorNavn[:2]
bareSmåkorNavn = alleKorNavn[2:5]
småkorForStorkor = {
    Kor.TSS: [Kor.Pirum, Kor.Knauskoret],
    Kor.TKS: [Kor.Candiss, Kor.Knauskoret]
}

bareKorNavnTKSRekkefølge = [Kor.TKS, Kor.TSS, Kor.Candiss, Kor.Knauskoret, Kor.Pirum]

class Tilgang:
    medlemsdata = 'medlemsdata'
    dekorasjon = 'dekorasjon'
    dekorasjonInnehavelse = 'dekorasjonInnehavelse'
    verv = 'verv'
    vervInnehavelse = 'vervInnehavelse'
    tilgang = 'tilgang'
    semesterplan = 'semesterplan'
    fravær = 'fravær'
    lenke = 'lenke'
    turne = 'turne'
    tversAvKor = 'tversAvKor'
    eksport = 'eksport'
    sjekkhefteSynlig = 'sjekkhefteSynlig'
    notearkiv = 'notearkiv'

tilgangTilKorNavn = {
    Tilgang.medlemsdata: bareStorkorNavn,
    Tilgang.dekorasjon: bareTilgangKorNavn, 
    Tilgang.dekorasjonInnehavelse: bareTilgangKorNavn, 
    Tilgang.verv: bareTilgangKorNavn, 
    Tilgang.vervInnehavelse: bareTilgangKorNavn, 
    Tilgang.tilgang: bareTilgangKorNavn, 
    Tilgang.semesterplan: bareTilgangKorNavn, 
    Tilgang.fravær: bareTilgangKorNavn, 
    Tilgang.lenke: bareTilgangKorNavn, 
    Tilgang.turne: bareKorNavn, 
    Tilgang.tversAvKor: bareTilgangKorNavn, 
    Tilgang.eksport: bareKorNavn, 
    Tilgang.sjekkhefteSynlig: bareKorNavn, 
    Tilgang.notearkiv: bareKorNavn,
}
tilgangBeskrivelser = [
    'For å kunne endre på medlemsdataene til de i ditt storkor.',
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
    'For å kunne eksportere medlemsregisterdata.',
    'Gjør at all dataen i sjekkheftet er synlig for deg.',
    'Lar deg redigere notearkivet.'
]

alleTilganger = list(tilgangTilKorNavn.keys())

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
    'Lenke',
    'Repertoar',
    'Sang'
]
'Names of models that are being logged'

loggModelNames = ['Logg', 'LoggM2M']
'Names of models that contain loggs'

otherModels = ['Kor']

allModelNames = [*loggedModelNames, *loggModelNames, *otherModels]

TXSModelNames = ['Sang', 'SangFil']

modelTilTilgangNavn = {
    'VervInnehavelse': Tilgang.vervInnehavelse,
    'Verv': Tilgang.verv,
    'DekorasjonInnehavelse': Tilgang.dekorasjonInnehavelse,
    'Dekorasjon': Tilgang.dekorasjon,
    'Medlem': Tilgang.medlemsdata,
    'Tilgang': Tilgang.tilgang,
    'Turne': Tilgang.turne,
    'Oppmøte': Tilgang.fravær,
    'Hendelse': Tilgang.semesterplan,
    'Lenke': Tilgang.lenke,
    'Repertoar': Tilgang.notearkiv,
    'Sang': Tilgang.notearkiv,
    'SangFil': Tilgang.notearkiv
}
'Mappe fra model til navn på tilgang'

korAvhengerAv = {
    'VervInnehavelse': 'Verv',
    'DekorasjonInnehavelse': 'Dekorasjon',
    'Oppmøte': 'Hendelse',
    'SangFil': 'Sang'
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

vrangstrupeDekorasjoner = ['Ridder', 'Kommandør', 'Kommandør med storkors']

# Denne brukes blant annet på hendelse siden for fraværsføring, 
# bare hiv på en url på slutten så får du en qr kode som redirecte dit:)
qrCodeLinkPrefix = 'https://api.qrserver.com/v1/create-qr-code/?size=600x600&qzone=2&data='

# BITMAP FIELDS
# Følgende fields brukes med BitmapMultipleChoiceField, så ALDRI (!!!) endre på rekkefølgen 
# eller alternativene her. Dette fordi verdiene lagres som en bit på tilsvarende index.
# Er trygt å gi nye navn til de, bare det forblir den samme informasjonen. 
# Også trygt å legge til nye alternativ.
sjekkhefteSynligOptions = [
    'fødselsdato', 
    'epost',
    'tlf',
    'studieEllerJobb',
    'boAdresse',
    'foreldreAdresse'
]

matpreferanseOptions = [
    'Vegetar',
    'Vegan',
    'Pescetar',
    'Glutenfritt',
    'Laktoseintoleranse',
    'Nøtteallergi',
    'Eggallergi',
    'Fiskeallergi',
    'Løkallergi',
    'Steinfruktallergi'
]

epostOptions = [
    'Endring av eget fravær', 
    'Fraværepost før øvelse'
]

def constsContextProcessor(request):
    # Dette gjør at alt defintert i denne fila er tilgjengelig i templates, som consts.variabelnavn
    # Grunnen til at vi ikke formaterer hele filen som en stor dictionary, er at man i python får mer
    # hjelp til å skrive rett importnavn, sammenlignet med oppsalg i en dict. 
    # isinstance(v, type) e om det e en klasse, for å inkluder dem også, for klasser e callable. 
    return {'consts': {k: v for k, v in globals().items() if (not k.startswith('_') and (not callable(v) or isinstance(v, type)))}}
