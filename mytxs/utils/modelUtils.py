import datetime
import random
import re

from django.apps import apps
from django.core.exceptions import FieldDoesNotExist
from django.db.models import Q, Case, When, ManyToManyField, ManyToManyRel, ForeignObjectRel
from django.db.models.fields.related import RelatedField
from django.forms import ValidationError
from django.utils.translation import gettext_lazy as _

# Utils for modeller

def vervInnehavelseAktiv(pathToVervInnehavelse='vervInnehavelser', dato=None, utvidetStart=datetime.timedelta(0)):
    '''
    Produsere et Q object som querye for aktive vervInnehavelser. Siden man 
    ikke kan si Tilganger.objects.filter(verv__vervInnehavelser=Q(...)) er dette en funksjon.

    Argumentet er query lookup pathen til vervInnehavelsene.
    - Om man gir ingen argument anntar den at vi filtrere på Medlem eller Verv (som vi som oftest gjør).
    - Om man gir en tom streng kan vi filterere direkte på VervInnehavelse tabellen
    - Alternativt kan man gi en full path, f.eks. i Tilgang.objects.filter(vervInnehavelseAktiv('verv__vervInnehavelse'))

    Eksempel:
    - Verv.objects.filter(vervInnehavelseAktiv(), vervInnehavelser__medlem__in=medlemmer)
    - Medlem.objects.filter(vervInnehavelseAktiv(), vervInnehavelser__verv__in=verv)
    - VervInnehavelse.objects.filter(vervInnehavelseAktiv(''))
    - Tilgang.objects.filter(vervInnehavelseAktiv('verv__vervInnehavelser'))
    '''

    # Må skriv dette fordi default parameters bare evalueres når funksjonen defineres. 
    # Altså om sørvern hadd kjørt meir enn en dag, og noen sende request, hadd de fått gårsdagens resultat.
    # I dette tilfellet kunne det vært merkbart. 
    if dato == None:
        dato = datetime.date.today()

    if pathToVervInnehavelse:
        pathToVervInnehavelse += '__'

    return (
        Q(**{f'{pathToVervInnehavelse}start__lte': dato + utvidetStart}) & 
        (
            Q(**{f'{pathToVervInnehavelse}slutt': None}) | 
            Q(**{f'{pathToVervInnehavelse}slutt__gte': dato})
        )
    )


stemmegruppeVervRegex = '^[12][12]?[SATB]$'

def stemmegruppeVerv(pathToVerv='verv', includeUkjentStemmegruppe=True, includeDirr=False):
    '''
    Produsere et Q objekt som querye for stemmegruppeverv
    
    Eksempel:
    - Verv.objects.filter(stemmegruppeVerv(''))
    - Medlem.objects.filter(stemmegruppeVerv('vervInnehavelser__verv'))
    - VervInnehavelse.objects.filter(stemmegruppeVerv())
    - Kor.objects.filter(stemmegruppeVerv())
    '''

    if pathToVerv:
        pathToVerv += '__'

    q = Q(**{f'{pathToVerv}navn__regex': stemmegruppeVervRegex})
    
    if includeUkjentStemmegruppe:
        q |= Q(**{f'{pathToVerv}navn': 'ukjentStemmegruppe'})
    
    if includeDirr:
        q |= Q(**{f'{pathToVerv}navn': 'Dirigent'})
    
    return q


def isStemmegruppeVervNavn(navn, includeUkjentStemmegruppe=True):
    return re.match(stemmegruppeVervRegex, navn) or (includeUkjentStemmegruppe and navn == 'ukjentStemmegruppe')


def stemmegruppeOrdering(fieldName='navn'):
    ordering = []
    count = 0

    for letter in 'SATB':
        for y in '12':
            ordering.append(When(**{fieldName:y+letter}, then=count))
            count += 1
            for x in '12':
                ordering.append(When(**{fieldName:x+y+letter}, then=count))
                count += 1
    
    ordering.append(When(**{fieldName:'ukjentStemmegruppe'}, then=count))
    return Case(*ordering, default=count+1)


def inneværendeSemester(pathToDate):
    'Produsere et Q objekt som sjekke om en date e innafor inneværende semester'
    today = datetime.date.today()
    return Q(**{f'{pathToDate}__year': today.year}) & qBool(
        today.month >= 7,
        trueOption=Q(**{f'{pathToDate}__month__gte': 7}),
        falseOption=Q(**{f'{pathToDate}__month__lt': 7})
    )

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


def randomDistinct(queryset, n=1, random=random):
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


def strToModels(modelNames):
    return list(map(lambda m: apps.get_model('mytxs', m), modelNames))


def getAllRelatedModels(model):
    # Returne en liste av alle (forwards og backwards) relaterte modeller 
    return list(map(lambda f: f.related_model, filter(lambda f: isinstance(f, RelatedField) or isinstance(f, ForeignObjectRel), model._meta.get_fields())))


def getAllRelatedModelsWithFieldName(model):
    # Returne samme som over, men istedet touples med (fieldNavn, model)
    return [
        *list(map(lambda f: (f.name, f.related_model), filter(lambda f: isinstance(f, RelatedField), model._meta.get_fields()))),
        *list(map(lambda f: (f.related_name, f.related_model), filter(lambda f: isinstance(f, ForeignObjectRel), model._meta.get_fields())))
    ]


def getAllRelatedModelsWithFieldNameAndReverse(model):
    # Returne samme som over, men med relatedFieldNavn, altså (fieldNavn, relatedFieldNavn, model)
    return [
        *list(map(lambda f: (f.name, f._related_name, f.related_model), filter(lambda f: isinstance(f, RelatedField), model._meta.get_fields()))),
        *list(map(lambda f: (f.related_name, f.field.name, f.related_model), filter(lambda f: isinstance(f, ForeignObjectRel), model._meta.get_fields())))
    ]


def getPathToKor(model):
    'Returne lookup path til kor for denne modellen (funke ikkje på medlem)'
    if model.__name__ == 'VervInnehavelse':
        return 'verv__kor'
    if model.__name__ == 'DekorasjonInnehavelse':
        return 'dekorasjon__kor'
    if model.__name__ == 'Oppmøte':
        return 'hendelse__kor'
    if model.__name__ == 'Medlem':
        return None
    
    # Alle andre modeller kan anntas å ha en direkte relasjon til kor
    return 'kor'


def getInstancesForKor(model, kor):
    'Returne alle instanser av modellen for et queryset med kor'
    if model.__name__ == 'Medlem':
        return model.objects.filter(
            stemmegruppeVerv('vervInnehavelser__verv', includeDirr=True), 
            vervInnehavelser__verv__kor__in=kor
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


def validateM2MFieldEmpty(instance, *fieldNames):
    '''
    Gitt en liste av M2M fields sjekke denne om noen har relaterte instances, og raise isåfall ValidationError
    Tiltenkt å settes inn i delete override der vi har M2M fields vi skulle likt å si on_delete=models.PROTECT
    '''
    for fieldName in fieldNames:
        if getattr(instance, fieldName).exists():
            raise ValidationError(
                _('For å slette denne instansen må du fjerne alle M2M relasjoner.'),
                code='nonEmptyM2M'
            )


def validateBruktIKode(instance):
    '''
    Sjekke om lagringen hadde krasjet med instanser som er bruktIKode. 
    Denne sjekker bruktIKode intensjonelt uavhengig av kor, slik at småkor ikke kan opprette en medlemsdata
    tilgang, for selv om vi kunne lagt inn en special case for det er det mye enklere å si at de bare ikke får lov. 
    '''
    if not instance.bruktIKode and type(instance).objects.filter(bruktIKode=True, navn=instance.navn).exists():
        raise ValidationError(
            _('Kan ikke opprette eller endre navn til noe som er brukt i kode'),
            code='bruktIKodeError',
        )


qTrue = ~Q(pk__in=[])
qFalse = Q(pk__in=[])

def qBool(value, trueOption=qTrue, falseOption=qFalse):
    'Return et Q objekt som tilsvare True eller False, til bruk i sammensatte filters'
    return trueOption if value else falseOption


def joinQ(*Qs, joinOp='|'):
    '''
    Slår sammen en liste av Q objekt med operator
    
    Default joinOp er OR fordi om man treng AND kan man bare spre Q objektan inn i filteret. 
    '''
    if len(Qs) == 1:
        return Qs[0]
    
    resQ = Qs.pop()

    while len(resQ) > 0:
        if joinOp == '|':
            resQ |= Qs.pop()
        else:
            resQ |= Qs.pop()
    
    return resQ


def getSourceM2MModel(model, fieldName):
    'Gitt en av modellene og et fieldName skaffer denne modellen som m2m feltet står på'
    try:
        modelFieldOrRel = model._meta.get_field(fieldName)
        if isinstance(modelFieldOrRel, ManyToManyField):
            return model
        elif isinstance(modelFieldOrRel, ManyToManyRel):
            return modelFieldOrRel.related_model
    except FieldDoesNotExist:
        # Dette inntreffer bare om feltet er satt på manuelt, og ikke har et tilsvarende model m2m field. 
        # F.eks. med hendelseForm sitt medlemmer field for undergruppe hendelser. 
        return None


def bareAktiveDecorator(func):
    'Legges før sideTilgangQueryset og redigerTilgangQueryset for å implementere bareAktive innstillingen'
    def _decorator(self, *args, **kwargs):
        qs = func(self, *args, **kwargs)

        if qs.model.__name__ == 'Medlem' and self.innstillinger.get('bareAktive', False):
            qs = qs.filter(vervInnehavelseAktiv(), stemmegruppeVerv('vervInnehavelser__verv', includeDirr=True))
        return qs

    return _decorator


def korLookup(kor, path=''):
    'Returne et Q lookup for å spør om kor=kor, der vi omformer til kor__navn=kor dersom kor er en string'
    if isinstance(kor, str):
        return Q(**{path+'__navn': kor})
    return Q(**{path: kor})


def annotateInstance(instance, annotateFunction, *args, **kwargs):
    '''
    Annotater en instance gitt en annotateFunction, som kan være en Manager/QuerySet funksjon, eller
    en lambda funksjon. Må uansett være en funksjon som kjører på samme modellen og returne et annotated 
    queryset. *args og **kwargs e passed direkte videre til annotateFunction. 

    Om instansen ikkje finnes i databasen vil den annotate None istedet, slik at det e trygt å gjør oppslag 
    på annotation navnet. 
    '''
    annotatedQS = annotateFunction(type(instance).objects.filter(pk=instance.pk), *args, **kwargs)
    annotatedInstance = annotatedQS.first()

    for name in annotatedQS.query.annotations.keys():
        setattr(instance, name, getattr(annotatedInstance, name, None))


def refreshQueryset(queryset):
    # Om man treng å filter basert på noe som allerede er filtrert bort, så må man
    # refresh querysettet ved å si pk__in=values_list('pk', flat=True)
    return queryset.model.objects.filter(pk__in=queryset.values_list('pk', flat=True))


def hasChanged(instance, skipDbCache=True):
    'Sjekke om en instance er annerledes fra det som er i databasen'
    dbInstance = type(instance).objects.filter(pk=instance.pk).first()
    if not dbInstance:
        return True
    for field in instance._meta.fields:
        if skipDbCache and field.name == 'dbCacheField':
            continue
        if getattr(instance, field.name) != getattr(dbInstance, field.name):
            return True
    return False


def dbCacheChanged(instance):
    'Sjekke om dbCacheField er annerledes fra det som er i databasen'
    dbInstance = type(instance).objects.filter(pk=instance.pk).first()
    return not dbInstance or instance.dbCacheField != dbInstance.dbCacheField
