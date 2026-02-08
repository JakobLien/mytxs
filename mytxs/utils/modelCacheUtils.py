from django.db import models

from mytxs.utils.modelUtils import getAllRelatedModelsWithFieldNameAndReverse
from mytxs.utils.threadUtils import thread

class DbCacheModel(models.Model):
    '''
    En abstract modell (altså ikke direkte i databasen) som gir dbCacheField feltet til modeller som arver fra denne. 
    dbCacheField feltet skal være mellomlagring av blant annet __str__ og oppdateres hver gang den og potensielt relaterte 
    instanser lagres. Dette brukes i arvende modeller via @dbCache decoratoren. Altså bare hiv på @dbCache decoratoren, 
    så vil methoden bare kjør ved lagring, evt av relaterte modeller. 
    '''

    dbCacheField = models.JSONField(editable=False, default=dict)

    def saveRelated(self, oldSelf=None, caller=None, delete=False):
        'Lagre relaterte objekt basert på dbCache sin path.'
        for relation, reverseRelation, model in getAllRelatedModelsWithFieldNameAndReverse(type(self)):
            dbCacheFields = []

            for dbCacheFieldName in getDbCachedFields(model):
                fields = [p.split('.')[1] for p in getattr(model, dbCacheFieldName).paths if p.split('.')[0] == reverseRelation]
                if (delete and fields) or any([f == '' or getAttrAndCall(self, f) != getAttrAndCall(oldSelf, f) for f in fields]):
                    dbCacheFields.append(dbCacheFieldName)

            if not dbCacheFields:
                continue

            # Bare lagre felt som ikkje lagres hver save
            dbCacheFields = [f for f in dbCacheFields if any(
                [p.split('.')[0] == '' and p.split(".")[1] != '' for p in getattr(model, f).paths]
            )]

            relatedList = [getattr(self, relation)]
            if hasattr(relatedList[0], 'all'):
                if delete:
                    # Slettede ting har ikkje RelatedManager, altså .all() raise exception. 
                    relatedList = []
                else:
                    relatedList = relatedList[0].all()

            for related in relatedList:
                if caller == f'{relation}#{related.pk}':
                    continue

                for field in dbCacheFields:
                    getattr(related, field)(run=True)
                DbCacheModel.save(related, caller=f'{reverseRelation}#{self.pk}')

    def save(self, *args, caller=None, **kwargs):
        'Save som vedlikeheld dbCache fields og relaterte avhengige dbCache fields.'
        # Slett ting i dbCache vi ikkje har metoda for
        for key in [k for k in self.dbCacheField.keys() if k not in getDbCachedFields(type(self))]:
            del self.dbCacheField[key]

        oldSelf = type(self).objects.filter(pk=self.pk).first()

        for dbCacheFieldName in getDbCachedFields(type(self)):
            fields = [p[1:] for p in getattr(type(self), dbCacheFieldName).paths if p.split(".")[0] == '' and p.split(".")[1] != '']

            if len(fields) == 0 or any([getAttrAndCall(self, field) != getAttrAndCall(oldSelf, field) for field in fields]):
                getattr(self, dbCacheFieldName)(run=True)

        super().save(*args, **kwargs)

        if caller == None:
            thread(self.saveRelated)(oldSelf, caller)
        else:
            self.saveRelated(oldSelf, caller)

    def delete(self, *args, **kwargs):
        'Delete som vedlikeheld dbCache fields og relaterte avhengige dbCache fields.'
        super().delete(*args, **kwargs)

        thread(self.saveRelated)(delete=True)

    class Meta:
        abstract = True


def getAttrAndCall(self, field):
    'Hjelpemetode som calle etter getattr dersom det e callable'
    res = getattr(self, field, None)
    if callable(res):
        return res()
    return res


def getDbCachedFields(model):
    'Returne liste av navn på methods som er dbCached'
    return [f for f in dir(model) if getattr(getattr(model, f, None), 'dbCached', False)]


def dbCache(actualMethod=None, paths=[], runOnNone=False):
    '''
    Kan brukes på modeller som arver fra dbCacheModel, gjør at resultatet av methoden lagres i dbCacheField ved lagring. 

    path er en liste av ting denne skal oppdateres på, format "relasjon.felt"
    - I utgangspunktet kjøre metoden ved hver lagring. Bruk ".felt" for å avgrens til bare når felt har endra seg. 
    - Om en relasjon spesifiseres, "relasjon.", skal vi også kjør hver gong den lagres. 
    - "relasjon.felt" fungere slik man sku forvent, på det relaterte objektet må det feltet ha endra seg. 

    runOnNone gjør at dataen hentes og lagres dersom dbCacheField mangle eller er None for denne. 
    Kun bruk det der denne metoden aldri kjem te å return None, og du vil at det skal caches med ein gong. 
    '''
    if not actualMethod:
        # Om vi calle decoratoren, return resten av funksjonen wrapped i en lambda
        return lambda actualMethod: dbCache(actualMethod, paths=paths, runOnNone=runOnNone)

    def _decorator(self, run=False):
        if run:
            self.dbCacheField[actualMethod.__name__] = actualMethod(self)
        elif runOnNone and self.dbCacheField.get(actualMethod.__name__, None) == None:
            self.save()

        return self.dbCacheField.get(actualMethod.__name__, 'UNSAVED_OBJ_STR' if actualMethod.__name__ == '__str__' else None)

    _decorator.dbCached = True
    _decorator.paths = paths
    return _decorator


def clearCachedProperty(instance, *props):
    'Utility funksjon som cleare en @cached_property, om den e satt, uten å call den.'
    for prop in props:
        if prop in vars(instance).keys():
            delattr(instance, prop)


def cachedMethod(method):
    '''
    cached_property for methods
    
    I motsetning til cached_property implementasjonen som faktisk oppretter en property som gjør at dens __get__
    aldri mer kalles, vil denne decoratorn alltid kalles, for å hente ut resultatet fra dicten. 
    '''
    def _decorator(self, *args, **kwargs):
        cacheName = f'{method.__name__}Cache'
        cacheDict = getattr(self, cacheName, None)
        if cacheDict == None:
            setattr(self, cacheName, {})
            cacheDict = getattr(self, cacheName)
        # Ja, å ha dette som key åpner for kollisjoner, men e sie at det går fint for no. 
        key = (*args, *kwargs.values())
        if not key in cacheDict:
            cacheDict[key] = method(self, *args, **kwargs)
        return cacheDict[key]
    return _decorator


def cacheQS(qs, props=['navn']):
    '''
    Cache et queryset slik at man kan bruk filter og exists uten ytterligere db oppslag.
    Primært tiltenkt brukt med medlem sine tilganger, siden vi filterer navn og exists på det querysettet ofte,
    men kan også brukes til andre ting ved å endre props argumentet. En fremtidig utvikling er å utvide til å også 
    håndtere exclude, men da igjen er det mye vanligere å bruke filter exists enn exclude exists. 

    For å bruk cacheQS på relaterte fields, se eksempelet på medlem.tilganger:
    `return cacheQS(tilganger.select_related('kor'), props=['navn', 'kor', 'kor__navn'])`
    '''
    # Populate queryset cachen om den ikkje alt e populated
    qs._fetch_all()

    def cacheDecorator(actualFunction, cacheFunction):
        def _decorator(*args, **kwargs):
            # resultCacheFunction transformere _result_cache. Om den returne False 
            # skal vi dropp å sett result cache, tolk det som at den cacheFunksjon 
            # ikkje kunna garanter rett resultat. 
            result = actualFunction(*args, **kwargs)
            resultCache = cacheFunction(*args, **kwargs)
            if resultCache == False:
                print('cacheQS failed for cacheFunction:', cacheFunction.__name__, props, args, kwargs, qs.model)
                return result
            result._result_cache = resultCache
            return cacheQS(result, props=props)
        return _decorator

    def filterFunction(*args, **kwargs):
        if not all(map(lambda k: (k.removesuffix('__in') in props), kwargs.keys())):
            return False
        resultCache = qs._result_cache

        def getByLookup(o, *keys):
            return getByLookup(getattr(o, keys[0]), *keys[1:]) if keys else o

        for key, value in kwargs.items():
            if key.endswith('__in'):
                resultCache = list(filter(lambda r: getByLookup(r, *key[:-4].split('__')) in value, resultCache))
            else:
                resultCache = list(filter(lambda r: getByLookup(r, *key.split('__')) == value, resultCache))
        return resultCache
    
    def flatValuesListFunction(*args, **kwargs):
        if kwargs.get('flat') == False or args[0] not in props:
            return False
        return list(map(lambda r: getattr(r, args[0]), qs._result_cache))

    qs.filter = cacheDecorator(qs.filter, filterFunction)
    qs.values_list = cacheDecorator(qs.values_list, flatValuesListFunction)
    return qs
