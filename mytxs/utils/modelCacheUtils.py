
from django.db import models

from mytxs.utils.modelUtils import dbCacheChanged, getAllRelatedModelsWithFieldNameAndReverse, hasChanged

class DbCacheModel(models.Model):
    '''
    En abstract modell (altså ikke direkte i databasen) som gir dbCacheField feltet til modeller som arver fra denne. 
    dbCacheField feltet skal være mellomlagring av blant annet __str__ og oppdateres hver gang den og potensielt relaterte 
    instanser lagres. Dette brukes i arvende modeller via @dbCache decoratoren. Altså bare hiv på @dbCache decoratoren, 
    så vil methoden bare kjør ved lagring, evt av relaterte modeller. 
    '''

    dbCacheField = models.JSONField(editable=False, default=dict)

    def updateRelated(self, changed, cacheChanged):
        if not (changed or cacheChanged):
            return
        
        for relName in getRelatedFieldsToUpdate(type(self), changed=changed, cacheChanged=cacheChanged):
            related = getattr(self, relName)
            if hasattr(related, 'all'):
                if self.pk: 
                    # Om vi ikke har self.pk, har vi heller ikke forward relations. 
                    for related in related.all():
                        DbCacheModel.save(related)
            else:
                DbCacheModel.save(related)

    def save(self, *args, **kwargs):
        for key in [k for k in self.dbCacheField.keys() if k not in getDbCachedFields(type(self))]:
            del self.dbCacheField[key]

        for methodName in getDbCachedFields(type(self)):
            if getattr(self, methodName).onChange:
                oldSelf = type(self).objects.filter(pk=self.pk).first()
                if all([getattr(oldSelf, f) == getattr(self, f) for f in getattr(self, methodName).onChange]) and self.dbCacheField.get(methodName):
                    continue

            self.dbCacheField[methodName] = getattr(self, methodName)(skipDecorator=True)

        changed = hasChanged(self)
        cacheChanged = dbCacheChanged(self)
        super().save(*args, **kwargs)
        self.updateRelated(changed, cacheChanged)

    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        self.updateRelated(changed=True, cacheChanged=True)

    class Meta:
        abstract = True


def getDbCachedFields(model):
    'Returne liste av navn på methods som er dbCached'
    return [f for f in dir(model) if getattr(getattr(model, f, None), 'dbCached', False)]


def getRelatedFieldsToUpdate(model, changed, cacheChanged):
    'Returne navnet på relasjonene fra denne modellen som må oppdateres'
    modelsToUpdate = set()
    for relName, reverseRelName, relModel in getAllRelatedModelsWithFieldNameAndReverse(model):
        for dbCachedMethodName in getDbCachedFields(relModel):
            if changed and reverseRelName in getattr(relModel, dbCachedMethodName).affectedByFields:
                modelsToUpdate.add(relName)
            if cacheChanged and reverseRelName in getattr(relModel, dbCachedMethodName).affectedByCache:
                modelsToUpdate.add(relName)
    return list(modelsToUpdate)


def dbCache(actualMethod=None, onChange=[], affectedByFields=[], affectedByCache=[]):
    '''
    Kan brukes på modeller som arver fra dbCacheModel, gjør at resultatet av methoden lagres i dbCacheField ved lagring. 

    onChange er en liste av fields på denne modellen, der metoden kun skal kjøres når disse endrer seg. Når dette er satt kjører vi
    heller ikkje metoden når metoden kalles og vi har en falsy verdi i cachen. 

    affectedByFields tar en liste av field navn på denne modellen som er relations til andre modeller, og gjør at når relaterte
    instances av de modellene lagres, og et felt endrer verdi, vil denne instansen også lagres. affectedByCache er det samme, 
    men oppdaterer bare når cachen av relaterte modeller endrer seg. Altså kan affectedByCache intreffe uten affectedByFields. 

    Dette lar oss spare arbeid f.eks. om et verv bytte navn, og relaterte vervInnehavelser følgelig endre navn, 
    men ikkje oppdatere relaterte medlemmer fordi medlem ikke er avhengig av vervInnehavelser sin cache, bare av fields. 
    '''
    if not actualMethod:
        # Om vi calle decoratoren, return resten av funksjonen wrapped i en lambda (her må vi passe videre ALLE harTilgang parametersa)
        return lambda actualMethod: dbCache(actualMethod, onChange=onChange, affectedByFields=affectedByFields, affectedByCache=affectedByCache)

    def _decorator(self, skipDecorator=False):
        if skipDecorator:
            return actualMethod(self)

        # Return verdien om den finnes
        if self.dbCacheField.get(actualMethod.__name__) or onChange:
            return self.dbCacheField.get(actualMethod.__name__)

        # Om ikke, sett den og return den
        if self.pk:
            # Om dbCache calles via str av objektet i modellens save metode, før save calles videre oppover,
            # vil den neste kodelinjen lage et nytt objekt, og den faktiske saven vil faile med error
            # "django.db.utils.IntegrityError: duplicate key value violates unique constraint", 
            # hvilket ser veldig ut som et databaseproblem uten at det er det. Derfor "if self.pk:" over
            DbCacheModel.save(self, update_fields=['dbCacheField'])
        else:
            self.dbCacheField[actualMethod.__name__] = actualMethod(self)
        return self.dbCacheField[actualMethod.__name__]
    
    _decorator.dbCached = True
    _decorator.onChange = onChange
    _decorator.affectedByFields = affectedByFields
    _decorator.affectedByCache = affectedByCache
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
