
from django.db import models
from django.db.models import Manager

from mytxs.utils.modelUtils import getAllRelatedModelsWithFieldName

class ModelWithStrRep(models.Model):
    '''
    En abstract modell (altså ikke en faktisk modell) som gir strRep feltet til modeller som arver fra denne. 
    strRep feltet skal være mellomlagring av __str__ og oppdateres hver gang objektet og relaterte objekt 
    som påvirker denne modellen sin strRep lagres. 
    
    Vi har affectedByStrRep, for å si at denne modellen sin __str__ bruker den relaterte modellen sin __str__, og
    affectedBy for å si at denne modellen sin __str__ blir påvirket av lagring av den relaterte modellen. 
    (Dette er tilfellet for Medlem og VervInnehavelse, da det påvirker hvilket kor man er i)
    '''

    strRep = models.CharField(max_length=200, editable=False, default='')
    'Field som lagrer strRep'

    affectedByStrRep = []
    'Liste av navn av modeller som endrer strRep av at vi endrer strRep'

    affectedBy = []
    'Liste av navn av modeller som endrer strRep av at vi endrer noe annet'

    def updateDependant(self, dependantFields):
        '''
        Denne metoden calle ModelWithStrRep.save på hver av dependantModels. De kan derfra 
        kalle det videre på sine modeller. dependantFields er en liste av feltNavn på denne modellen. 
        '''

        # For hver relaterte instance
        for related in map(lambda related: getattr(self, related), dependantFields):
            # Om det e mange instances, oppdater alle sin str. Om det e en, call save på den. 
            if isinstance(related, Manager):
                for instance in related.all():
                    ModelWithStrRep.save(instance)
            else:
                ModelWithStrRep.save(related)

    def save(self, *args, **kwargs):
        oldStrRep = self.strRep
        strRep = self.__str__(skipDecorator=True)
        if strRep != oldStrRep:
            self.strRep = strRep

        super().save(*args, **kwargs)

        # Tanken her er at via getAllRelatedModelsWithFieldName(type(self)) skaffer vi alle relaterte modeller. 
        # Vi ser så på deres affectedBy og affectedByStrRep, for å se om vi skal oppdatere de relaterte instansene. 
        # Deretter gir vi fieldNavnet videre til updateDependant. Siden alt dette skjer utenfor databasen tror jeg det er 
        # ganske billig å sjekke den relaterte modellen, selv om det er mer komplisert enn å bare på hver modell spesifisere
        # hvilken __str__ den vil påvirke. Koden blir VELDIG mye mer leselig av å bare kunne se "Ja, denne __str__ metoden
        # bruker medlemmet sin sin strRep, så da hiver vi inn Medlem i listen affectedByStrRep like over." C O L O C A T I O N

        fieldModelsToUpdate = list(filter(lambda touple: 
            # Sjekk om vi burde oppdatere realterte instanser for feltet pga affectedBy
            (hasattr(touple[1], 'affectedBy') and type(self).__name__ in touple[1].affectedBy) or
            # Sjekk om vi burde oppdatere realterte instanser for feltet pga affectedByStrRep
            (oldStrRep != strRep and hasattr(touple[1], 'affectedByStrRep') and type(self).__name__ in touple[1].affectedByStrRep) # For 
        , getAllRelatedModelsWithFieldName(type(self))))

        self.updateDependant(list(map(lambda fieldModel: fieldModel[0], fieldModelsToUpdate)))

    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)

        # Grunnen til at man har med affectedByStrRep er fordi det relaterte objektets strRep 
        # er en del av dette objektets strRep. I alle tilfeller så langt (og jeg misstenker alle 
        # tilfeller punktum), har man ikke lov til å slette slike relaterte objekter uansett, så
        # i delete ser vi derfor bare på affectedBy, som allerede nå med vervInnehavelse påvirker 
        # medlem sin strRep ved sletting. 

        fieldModelsToUpdate = list(filter(lambda touple: 
            hasattr(touple[1], 'affectedBy') and type(self).__name__ in touple[1].affectedBy
        , getAllRelatedModelsWithFieldName(type(self))))

        self.updateDependant(list(map(lambda fieldModel: fieldModel[0], fieldModelsToUpdate)))

    class Meta:
        abstract = True


def strDecorator(__str__):
    'En decorator som håndterer logikk for strRep, sett før __str__ i modeller som arver fra ModelWithStrRep'
    def _decorator(self, skipDecorator=False):
        if skipDecorator:
            return __str__(self)

        # Return strRep om den finnes
        if strRep := self.strRep:
            return strRep
        
        # Om ikke, sett den og return den
        self.strRep = __str__(self)
        ModelWithStrRep.save(self)
        return self.strRep
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
    '''
    # Populate queryset cachen om den ikkje alt e populated
    qs._fetch_all()

    def customFilter(actualFilter):
        def _decorator(*args, **kwargs):
            # Fortsatt gjør actual filter, slik at ting funke som forventa
            # Filter i seg sjølv hitte ikke databasen, så bare vi populate _result_cache e vi good
            narrowed_queryset = actualFilter(*args, **kwargs)

            # Bare sett _result_cache dersom vi faktisk kan oppfyll queriet
            if all(map(lambda k: (k.removesuffix('__in') in props), kwargs.keys())):
                narrowed_queryset.filter = customFilter(narrowed_queryset.filter)

                narrowed_queryset._result_cache = qs._result_cache

                for key, value in kwargs.items():
                    inKey = key.endswith('__in')
                    if not inKey:
                        narrowed_queryset._result_cache = list(filter(lambda r: getattr(r, key) == value, narrowed_queryset._result_cache))
                    else:
                        narrowed_queryset._result_cache = list(filter(lambda r: getattr(r, key[:-4]) in value, narrowed_queryset._result_cache))
            else:
                print(f'Queryset not cached with kwargs {str(kwargs)}')
            
            return narrowed_queryset
        
        return _decorator

    qs.filter = customFilter(qs.filter)
    return qs
