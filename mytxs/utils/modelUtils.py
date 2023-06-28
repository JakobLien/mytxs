import datetime
import random
import re
from django.db.models import Q, Case, When

# Utils for modeller

def vervInnehavelseAktiv(pathToVervInnehavelse='vervInnehavelse', dato=None):
    '''
    Produsere et Q object som querye for aktive vervInnehavelser. Siden man 
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
    '''

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

stemmegruppeVervRegex = '^[12][12]?[SATB]$'
hovedStemmegruppeVervRegex = '^[12][SATB]$'

def stemmegruppeVerv(pathToStemmGruppeVerv='verv'):
    '''
    Produsere et Q objekt som querye for stemmegruppeverv
    
    Eksempel:
    - Verv.objects.filter(stemmegruppeVerv(''))
    - Medlem.objects.filter(stemmegruppeVerv('vervInnehavelse__verv'))
    - VervInnehavelse.objects.filter(stemmegruppeVerv())
    - Kor.objects.filter(vervInnehavelseAktiv())
    '''
    if not pathToStemmGruppeVerv:
        return Q(navn__regex=stemmegruppeVervRegex)
    else:
        return Q(**{f'{pathToStemmGruppeVerv}__navn__regex': stemmegruppeVervRegex})

def hovedStemmeGruppeVerv(pathToStemmGruppeVerv='verv'):
    'Produsere et Q objekt som querye for hoved stemmegruppeverv, se stemmegruppeVerv like over'
    if not pathToStemmGruppeVerv:
        return Q(navn__regex=hovedStemmegruppeVervRegex)
    else:
        return Q(**{f'{pathToStemmGruppeVerv}__navn__regex': hovedStemmegruppeVervRegex})

def isStemmegruppeVervNavn(navn):
    return re.match(stemmegruppeVervRegex, navn)

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

def groupBy(queryset, prop):
    '''
    Enkel metode for å konverter et queryset til en dict med liste-verdier,
    gruppert på en property. 

    TODO: Forbedre denne så den funke på remote felt
    '''
    groups = dict()
    for obj in queryset.all():
        groups.setdefault(str(getattr(obj, prop)), []).append(obj)
    return groups

def randomDistinct(queryset, n=1):
    '''
    Hjelpemetode for å skaffe en liste av tilfeldig sorterte subset av queryset argumentet. 
    Om n=1 (som er default), returne den objektet istedet for querysettet. 

    Denne hjelpefunksjonen finnes fordi:
    - Kan ikke order_by('?') og distinct samtidig: https://docs.djangoproject.com/en/4.2/ref/models/querysets/#distinct
    - Burda ikkje order_by('?') generelt: https://stackoverflow.com/a/6405601/6709450
    '''
    pks = list(set(queryset.values_list('pk', flat=True)))

    # Shuffle pks for at vi skal få n tilfeldige elementer
    random.shuffle(pks)
    pks = pks[:n]

    if n == 1:
        return queryset.model.objects.filter(pk__in=pks).first()
    else:
        qs = list(queryset.model.objects.filter(pk__in=pks).all())

        # Shuffle resultatet for at vi skal få tilfeldig sortering på elementan
        random.shuffle(qs)
        return qs
