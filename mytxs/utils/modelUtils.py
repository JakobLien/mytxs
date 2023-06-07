import datetime
from itertools import chain
from django.db.models import Q, Case, When

def vervInnehavelseAktiv(pathToVervInnehavelse='vervInnehavelse', dato=None):
    """Produsere et Q object som querye for aktive vervInnehavelser. Siden man 
    ikke kan si Tilganger.objects.filter(verv__vervInnehavelse=Q(...)) er dette en funksjon.

    Argumentet er query lookup pathen til vervInnehavelsene.
    - Om man gir ingen argument anntar den at vi filtrere på Medlem eller Verv (som vi som oftest gjør).
    - Om man gir en tom streng kan vi filterere direkte på VervInnehavelse tabellen
    - Alternativt kan man gi en full path, f.eks. i Tilgang.objects.filter(vervInnehavelseAktiv('verv__vervInnehavelse'))

    Eksempel:
    - Verv.objects.filter(vervInnehavelseAktiv(), vervInnehavelse__medlem__in=medlemmer)
    - Medlem.objects.filter(vervInnehavelseAktiv(), vervInnehavelse__verv__in=verv)
    - VervInnehavelse.objects.filter(vervInnehavelseAktiv(''))
    - Tilgang.objects.filter(vervInnehavelseAktiv('verv__vervInnehavelse'))
    """
    

    # Må skriv dette fordi default parameters bare evalueres når funksjonen defineres. 
    # Altså om sørvern hadd kjørt meir enn en dag, og noen sende request, hadd de fått gårsdagens resultat.
    # I dette tilfellet kunne det vært merkbart. 
    if dato == None:
        dato = datetime.date.today()

    if not pathToVervInnehavelse:
        return (Q(slutt=None) | Q(slutt__gte=dato)) & Q(start__lte=dato)
    else:
        return ((Q(**{f'{pathToVervInnehavelse}__slutt':None}) |
                 Q(**{f'{pathToVervInnehavelse}__slutt__gte':dato})) &
                 Q(**{f'{pathToVervInnehavelse}__start__lte':dato}))

stemmeGruppeVervRegex = '^[12][12]?[SATB]$'
hovedStemmegruppeVervRegex = '^[12][SATB]$'

def stemmeGruppeVerv(pathToStemmGruppeVerv='verv'):
    """Produsere et Q objekt som querye for stemmegruppeverv
    
    Eksempel:
    - Verv.objects.filter(stemmeGruppeVerv(''))
    - Medlem.objects.filter(stemmeGruppeVerv('vervInnehavelse__verv'))
    - VervInnehavelse.objects.filter(stemmeGruppeVerv())
    - Kor.objects.filter(vervInnehavelseAktiv())
    """
    if not pathToStemmGruppeVerv:
        return Q(navn__regex=stemmeGruppeVervRegex)
    else:
        return Q(**{f'{pathToStemmGruppeVerv}__navn__regex': stemmeGruppeVervRegex})

def hovedStemmeGruppeVerv(pathToStemmGruppeVerv='verv'):
    """Produsere et Q objekt som querye for hoved stemmegruppeverv, se stemmeGruppeVerv like over"""
    if not pathToStemmGruppeVerv:
        return Q(navn__regex=hovedStemmegruppeVervRegex)
    else:
        return Q(**{f'{pathToStemmGruppeVerv}__navn__regex': hovedStemmegruppeVervRegex})

def orderStemmegruppeVerv():
    ordering = []
    count = 0

    for letter in 'SATB':
        for y in '12':
            ordering.append(When(navn=y+letter, then=count))
            count += 1
            for x in '12':
                ordering.append(When(navn=x+y+letter, then=count))
                count += 1
        
    return Case(*ordering, default=count)

def toolTip(helpText):
    return f'<span title="{helpText}">(?)</span>'
