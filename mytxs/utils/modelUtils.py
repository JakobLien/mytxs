import datetime
import random
import re

from django.db import models
from django.db.models import Q, Case, When, ManyToManyField, ManyToManyRel
from django.db.models.fields.related import RelatedField
from django.forms import ValidationError
from django.utils.translation import gettext_lazy as _

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

    if pathToVervInnehavelse:
        pathToVervInnehavelse += '__'

    return (
        Q(**{f'{pathToVervInnehavelse}start__lte': dato}) & 
        (
            Q(**{f'{pathToVervInnehavelse}slutt': None}) | 
            Q(**{f'{pathToVervInnehavelse}slutt__gte': dato})
        )
    )


stemmegruppeVervRegex = '^[12][12]?[SATB]$'

def stemmegruppeVerv(pathToStemmGruppeVerv='verv', includeUkjentStemmegruppe=True, includeDirr=False):
    '''
    Produsere et Q objekt som querye for stemmegruppeverv
    
    Eksempel:
    - Verv.objects.filter(stemmegruppeVerv(''))
    - Medlem.objects.filter(stemmegruppeVerv('vervInnehavelse__verv'))
    - VervInnehavelse.objects.filter(stemmegruppeVerv())
    - Kor.objects.filter(vervInnehavelseAktiv())
    '''

    if pathToStemmGruppeVerv:
        pathToStemmGruppeVerv += '__'

    q = Q(**{f'{pathToStemmGruppeVerv}navn__regex': stemmegruppeVervRegex})
    
    if includeUkjentStemmegruppe:
        q |= Q(**{f'{pathToStemmGruppeVerv}navn': 'ukjentStemmegruppe'})
    
    if includeDirr:
        q |= Q(**{f'{pathToStemmGruppeVerv}navn': 'Dirigent'})
    
    return q


def isStemmegruppeVervNavn(navn, includeUkjentStemmegruppe=True):
    return re.match(stemmegruppeVervRegex, navn) or (includeUkjentStemmegruppe and navn == 'ukjentStemmegruppe')


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
    
    ordering.append(When(navn='ukjentStemmegruppe', then=count))
    return Case(*ordering, default=count+1)


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


def getAllRelatedModels(model):
    # Returne en liste av alle (forwards og backwards) relaterte modeller 
    return [
        *list(map(lambda f: f.related_model, filter(lambda f: isinstance(f, RelatedField), model._meta.get_fields()))),
        *list(map(lambda f: f.related_model, list(filter(lambda f: isinstance(f, models.ForeignObjectRel), model._meta.get_fields()))))
    ]


def getAllRelatedModelsWithFieldName(model):
    # Returne samme som over, men istedet touples med (fieldNavn, model)
    return [
        *list(map(lambda f: (f.name, f.related_model), filter(lambda f: isinstance(f, RelatedField), model._meta.get_fields()))),
        *list(map(lambda f: (f.related_name, f.related_model), list(filter(lambda f: isinstance(f, models.ForeignObjectRel), model._meta.get_fields()))))
    ]


def getPathToKor(model):
    'Returne lookup path til kor for denne modellen (funke ikkje på medlem)'
    if model.__name__ == 'VervInnehavelse':
        return 'verv__kor'
    if model.__name__ == 'DekorasjonInnehavelse':
        return 'dekorasjon__kor'
    if model.__name__ == 'Oppmøte':
        return 'hendelse__kor'
    
    # Alle andre modeller kan anntas å ha en direkte relasjon til kor
    return 'kor'


def getInstancesForKor(model, kor):
    'Returne alle instanser av modellen for et queryset med kor'
    if model.__name__ == 'Medlem':
        return model.objects.filter(
            stemmegruppeVerv('vervInnehavelse__verv', includeDirr=True), 
            Q(vervInnehavelse__verv__kor__in=kor)
        )
    
    if model.__name__ == 'Kor':
        return kor
    
    return model.objects.filter(
        **{f'{getPathToKor(model)}__in': kor}
    )


def validateStartSlutt(instance, canEqual=True):
    '''
    Validere rekkefølgen på start og slutt, raiser ValidationError om ikke. 
    Skriver hjelpefunksjon fordi dette trengs i clean på tvers av flere modeller. 
    Gjør ingenting om instance.slutt ikke er satt. 
    '''
    if instance.slutt:
        if canEqual:
            if instance.start >= instance.slutt:
                raise ValidationError(
                    _('Slutt må være etter eller lik start'),
                    code='invalidDateOrder'
                )
        else:
            if instance.start > instance.slutt:
                raise ValidationError(
                    _('Slutt må være etter start'),
                    code='invalidDateOrder'
                )


qTrue = ~Q(pk__in=[])
qFalse = Q(pk__in=[])

def getQBool(value, trueOption=qTrue, falseOption=qFalse):
    return trueOption if value else falseOption


def getSourceM2MModel(model, fieldName):
    'Gitt en av modellene og et fieldName skaffer denne modellen som m2m feltet står på'
    modelFieldOrRel = model._meta.get_field(fieldName)
    if isinstance(modelFieldOrRel, ManyToManyField):
        return model
    elif isinstance(modelFieldOrRel, ManyToManyRel):
        return modelFieldOrRel.related_model
    
    raise Exception("M2M Field not found")
