from contextlib import contextmanager
import re

from django.db import connection, models, reset_queries
from django.test import TestCase

from mytxs.utils.modelCacheUtils import DbCacheModel, dbCache
from django.conf import settings
settings.DEBUG = True # Må til for å kunne logge queries

# Så ka e fasit for dbCache idag:
# - Kjøre **alltid** når objektet lagres, med mindre den ser på et lokalt felt som ikkje har endra seg. 
#   - Viktig forskjell her: Den kan forsatt lagres når et relatert objekt lagres, 
#     sjølv om den spesifiser remote feltet, fordi et anna felt vil kreve lagring. 
# - Kjøres også når objektet lagres, runOnNone=True, og vedien den hadd returna e None. 
# - Kjøres også når et relatert objekt lagres og:
#   - Path slutte med ".", altså den alltid skal lagres. 
#   - Path slutte med ".field", og field har endret seg for en FK. 
#   - Man har lagt til eller fjernet en knytning. 

# Nåværende implementasjonen håndterer FKs godt. Har ikke testet OneToOne fields, 
# men det burde ikke være problematisk siden OneToOne fields er subsets av FKer. 
# m2m relasjoner vil derimot kreve en stor redesign om vi skal støtte det. 
# Dette er fordi opprettelse og sletting av dem e bare tilgjengelig via signals, 
# og da måtta vi også lagra settet som e knytta før og etter, og sjekka om nå har endra seg. 
# E absolutt mulig, men e har ikkje behov for det, og det virke komplisert. 

'Legg inn en par ting som gjør det lettar å test dbCacheModel'
class TestDbCacheModel(DbCacheModel):
    saves = models.PositiveSmallIntegerField(default=0)

    def save(self, *args, **kwargs):
        self.saves += 1
        super().save(*args, **kwargs)

    class Meta:
        abstract = True 


class Single(TestDbCacheModel):
    @dbCache
    def simpleCache(self):
        return self.dbCacheField.get('simpleCache', 0) + 1

    @dbCache(runOnNone=True)
    def runOnNone(self):
        return self.dbCacheField.get('runOnNone', 0) + 1


class LocalField(TestDbCacheModel):
    navn = models.CharField()

    @dbCache(paths=['.navn'])
    def localField(self):
        return self.dbCacheField.get('localField', 0) + 1


class Author(TestDbCacheModel):
    navn = models.CharField()
    mellomnavn = models.CharField()

    @dbCache(paths=['books.'])
    def numberOfBooks(self):
        return self.dbCacheField.get('numberOfBooks', 0) + 1
   
    def __str__(self):
        return 'Author-' + self.navn 


class Book(TestDbCacheModel):
    title = models.CharField()
    stars = models.PositiveSmallIntegerField(default=3)

    author = models.ForeignKey(
        Author,
        on_delete=models.SET_NULL,
        null=True,
        related_name='books'
    )

    @dbCache(paths=['author.'])
    def hasAuthor(self):
        return self.dbCacheField.get('hasAuthor', 0) + 1

    def __str__(self):
        return 'Book-' + self.title


class AuthorSpecific(TestDbCacheModel):
    navn = models.CharField()
    mellomnavn = models.CharField()

    @dbCache(paths=['books.stars'])
    def bestBookTitle(self):
        return self.dbCacheField.get('bestBookTitle', 0) + 1

    def __str__(self):
        return 'AuthorSpecific-' + self.navn


class BookSpecific(TestDbCacheModel):
    title = models.CharField()
    stars = models.PositiveSmallIntegerField(default=3)

    author = models.ForeignKey(
        AuthorSpecific,
        on_delete=models.SET_NULL,
        null=True,
        related_name='books'
    )

    @dbCache(paths=['author.navn'])
    def authorName(self):
        return self.dbCacheField.get('authorName', 0) + 1

    def __str__(self):
        return 'BookSpecific-' + self.title


# Merk: For å definer models som skal brukes i testa hadd det vært mulig å ha en models.py i test mappa, 
# også legg til mytxs.tests i INSTALLED_APPS når 'test' in sys.argv, men det hadd vært så my kjipar 
# for colocation, så derfor gjør vi istedet dette. Det e ikkje så værst syns e. 
testModels = [v for k, v in locals().items() if isinstance(v, type) and issubclass(v, TestDbCacheModel) and v != TestDbCacheModel]
class DbCacheTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        with connection.schema_editor() as schema_editor:
            for testModel in testModels:
                schema_editor.create_model(testModel)

    @classmethod
    def tearDownClass(cls):
        with connection.schema_editor() as schema_editor:
            for testModel in testModels:
                schema_editor.delete_model(testModel)

    def testLocalAndRunOnNone(self):
        '''
        Test at standard dbCache gjør at det lagres når den lagres, ikke før, og at det 
        er tilgjengelig deretter. Test også at det automatisk lagres når man etterspør det.
        '''
        single1 = Single()
        self.assertEqual(single1.simpleCache(), None)
        self.assertEqual(single1.saves, 0)
        self.assertIsNone(single1.pk)

        # Dette vil lagre den, fordi runOnNone. 
        self.assertEqual(single1.runOnNone(), 1)
        self.assertIsNotNone(single1.pk)
        self.assertEqual(single1.saves, 1)
        self.assertEqual(single1.simpleCache(), 1)
        self.assertEqual(single1.runOnNone(), 1)
        self.assertEqual(single1.simpleCache(), 1)
        self.assertEqual(single1.saves, 1)

        # Sjekk at det faktisk hentes fra databasen også
        single1 = Single.objects.first()
        self.assertEqual(single1.simpleCache(), 1)
        self.assertEqual(single1.runOnNone(), 1)
        self.assertEqual(single1.saves, 1)
        single1.save()
        self.assertEqual(single1.simpleCache(), 2)
        self.assertEqual(single1.saves, 2)
        single1.delete()

        # Alternativt, sjekk at en vanlig lagring funke som forventet
        single2 = Single()
        self.assertEqual(single2.simpleCache(), None)
        self.assertEqual(single2.saves, 0)
        self.assertIsNone(single2.pk)

        single2.save()
        self.assertIsNotNone(single2.pk)
        self.assertEqual(single2.saves, 1)
        self.assertEqual(single2.simpleCache(), 1)
        self.assertEqual(single2.runOnNone(), 1)
        self.assertEqual(single2.saves, 1)
        single2.delete()

    def testLocalField(self):
        'Test at en dbCache som ser på et lokalt felt ikke kjøre før det feltet har endra seg.'
        local = LocalField(navn='Test')
        self.assertEqual(local.localField(), None)

        local.save()
        self.assertEqual(local.localField(), 1)
        local.save()
        self.assertEqual(local.localField(), 1)

        # Det må faktisk vær en endring, ikke bare reassignes til. 
        local.navn = 'Test'
        self.assertEqual(local.localField(), 1)
        local.save()
        self.assertEqual(local.localField(), 1)

        local.navn = 'Test2'
        self.assertEqual(local.localField(), 1)
        local.save()
        self.assertEqual(local.localField(), 2)
        local.delete()

    def assertInstance(self, instance, saves, *args):
        self.assertEqual(instance.saves, saves, str(instance) + (' is saved' if instance.saves > saves else ' is not saved'))
        args = [arg if arg != 0 else None for arg in args]
        if not args:
            if saves != 0:
                args = [saves]
            else:
                args = [None]
        if isinstance(instance, Author):
            self.assertEqual(instance.numberOfBooks(), args[0], instance)
        if isinstance(instance, AuthorSpecific):
            self.assertEqual(instance.bestBookTitle(), args[0], instance)
        if isinstance(instance, Book):
            self.assertEqual(instance.hasAuthor(), args[0], instance)
        if isinstance(instance, BookSpecific):
            self.assertEqual(instance.authorName(), args[0], instance)

    def doesSave(self, sourceOrfun=None, dos=[], donts=[], forceRefresh=False, logQueries=False):
        'Sjekk at når man kjøre funksjon eller lagre objekt, så lagres dem og dem.'
        targetSaves = [d.saves + 1 for d in dos] + [d.saves for d in donts]
        if callable(sourceOrfun):
            sourceOrfun()
        else:
            sourceSave = (sourceOrfun.saves or 0) + 1

            if logQueries:
                reset_queries()

            sourceOrfun.save()

            if logQueries:
                print()
                for i, q in enumerate(connection.queries):
                    print(f'{i}:', re.sub(r'SELECT .* FROM', 'SELECT ... FROM', q['sql']))

            self.assertInstance(sourceOrfun, sourceSave)

        for target, targetSave in zip(dos + donts, targetSaves):
            # Som regel vil funksjonen endre på noko, og vi ønske ikkje å refresh bort endringen. 
            if not callable(sourceOrfun) or forceRefresh:
                target.refresh_from_db()
            self.assertInstance(target, targetSave)

        return sourceOrfun

    def doesDelete(self, source, dos=[], donts=[], logQueries=False):
        self.doesSave(sourceOrfun=source.delete, dos=dos, donts=donts, forceRefresh=True, logQueries=logQueries)

    def getLitterature(self, specific=False, grouped=False):
        '''
        En test som bare opprette grunnleggende objekt og returne, basis for alle videre tester.
        specific e om vi skal bruk dbCacheFields som ser på spesifikke felt. 
        grouped e om mbob også ska pek på Ivar eller Andersen. 

        Verdensbildet vårt e altså:
        - Ivar skreiv Symra
        - Andersen skreiv mbob (åpenbart feil men jaja)
        '''
        if specific:
            AuthorModel = AuthorSpecific
            BookModel = BookSpecific
        else:
            AuthorModel = Author
            BookModel = Book

        ivar = self.doesSave(AuthorModel(navn='Ivar'))
        symra = self.doesSave(BookModel(title='Symra', stars=4), donts=[ivar])

        self.doesSave(lambda: setattr(symra, 'author', ivar), donts=[ivar, symra])
        self.doesSave(symra, dos=[ivar])

        andersen = self.doesSave(AuthorModel(navn='H.C. Andersen'), donts=[ivar, symra])
        mbob = self.doesSave(BookModel(title='Mellom bakkar og berg', stars=5), donts=[ivar, symra])

        if not grouped:
            self.doesSave(lambda: setattr(mbob, 'author', andersen), donts=[ivar, symra, andersen, mbob])
            self.doesSave(mbob, dos=[andersen], donts=[ivar, symra])
        if grouped:
            self.doesSave(lambda: setattr(mbob, 'author', ivar), donts=[ivar, symra, andersen, mbob])
            self.doesSave(mbob, dos=[ivar] if specific else [ivar, symra], donts=[symra, andersen] if specific else [andersen])

        return ivar, symra, andersen, mbob

    def testGetLitterature(self):
        '''
        Sjekk at funksjonen som generere utgangspunktet til resten av testan funke i alle variasjonan. 
        Denne funksjonen teste også dermed at vi kan opprett ting og knytt dem sammen. 
        '''
        for specific in [False, True]:
            for grouped in [False, True]:
                self.getLitterature(specific, grouped)

    @contextmanager
    def litterature(self, *, specific, grouped):
        'En hjelpefunksjon som lar oss skriv en oneliner with statement for å sett opp en test.'
        objs = self.getLitterature(specific=specific, grouped=grouped)
        try:
            yield objs
        finally:
            for obj in objs:
                if obj.pk:
                    obj.refresh_from_db()
                    obj.delete()

    def testSaveBook(self):
        # specific=False lagre knyttede ting bortover og rundt
        with self.litterature(specific=False, grouped=False) as (ivar, symra, andersen, mbob):
            self.doesSave(symra, dos=[ivar], donts=[andersen, mbob])
        with self.litterature(specific=False, grouped=True) as (ivar, symra, andersen, mbob):
            self.doesSave(symra, dos=[ivar, mbob], donts=[andersen])

        for grouped in [False, True]:
            with self.litterature(specific=True, grouped=grouped) as (ivar, symra, andersen, mbob):
                # Om specific e true skal lagring av Symra aldri lagre nå anna, grouped eller ei
                self.doesSave(symra, donts=[ivar, andersen, mbob])

                # Om noko har endra seg, skal vi lagre Ivar, men ikke mbob om den e knyttet videre rundt. 
                self.doesSave(lambda: setattr(symra, 'stars', 5), donts=[ivar, symra, andersen, mbob])
                self.doesSave(symra, dos=[ivar], donts=[andersen, mbob])

    def testSaveAuthor(self):
        with self.litterature(specific=False, grouped=False) as (ivar, symra, andersen, mbob):
            self.doesSave(ivar, dos=[symra], donts=[andersen, mbob])
        with self.litterature(specific=False, grouped=True) as (ivar, symra, andersen, mbob):
            self.doesSave(ivar, dos=[symra, mbob], donts=[andersen])
        
        # I denne testen er ikkje specific=False, grouped=True noe mer interessant enn casen under. 
        with self.litterature(specific=True, grouped=True) as (ivar, symra, andersen, mbob):
            # Om specific e true skal lagring av Ivar aldri lagre nå anna, grouped eller ei
            self.doesSave(ivar, donts=[symra, andersen, mbob])

            # Om noko har endra seg, skal vi lagre symra og mbob.
            self.doesSave(lambda: setattr(ivar, 'navn', 'Ivar Aasen'), donts=[ivar, symra, andersen, mbob])
            self.doesSave(ivar, dos=[symra, mbob], donts=[andersen])

    def testChangeAuthor(self):
        # Sett te None, sjekk at det trigge en save, med og uten specific
        # Grouped her komplisere bare eksempelet for da vil den med og uten specific bytt på å lagre rundt, 
        # så trur dette e greit for denne casen. 
        for specific in [False, True]:
            with self.litterature(specific=specific, grouped=False) as (ivar, symra, andersen, mbob):
                self.doesSave(lambda: setattr(symra, 'author', None), donts=[ivar, symra, andersen, mbob])
                self.doesSave(symra, dos=[ivar], donts=[andersen, mbob])

        # Sjekk å bytt te og fra author, og verifiser at det lagres rundt te den andre boka uansett
        with self.litterature(specific=False, grouped=False) as (ivar, symra, andersen, mbob):
            self.doesSave(lambda: setattr(mbob, 'author', ivar), donts=[ivar, symra, andersen, mbob])
            self.doesSave(mbob, dos=[ivar, andersen, symra])
        with self.litterature(specific=False, grouped=True) as (ivar, symra, andersen, mbob):
            self.doesSave(lambda: setattr(mbob, 'author', andersen), donts=[ivar, symra, andersen, mbob])
            self.doesSave(mbob, dos=[ivar, andersen, symra])

        # Samme som over, men lagres ikke rundt pga specific. 
        with self.litterature(specific=True, grouped=False) as (ivar, symra, andersen, mbob):
            self.doesSave(lambda: setattr(mbob, 'author', ivar), donts=[ivar, symra, andersen, mbob])
            self.doesSave(mbob, dos=[ivar, andersen], donts=[symra])
        with self.litterature(specific=True, grouped=True) as (ivar, symra, andersen, mbob):
            self.doesSave(lambda: setattr(mbob, 'author', andersen), donts=[ivar, symra, andersen, mbob])
            self.doesSave(mbob, dos=[ivar, andersen], donts=[symra])

    def testDeleteBooks(self):
        for specific in [False, True]:
            with self.litterature(specific=specific, grouped=False) as (ivar, symra, andersen, mbob):
                self.doesDelete(mbob, dos=[andersen], donts=[ivar, symra])
        with self.litterature(specific=False, grouped=True) as (ivar, symra, andersen, mbob):
            self.doesDelete(mbob, dos=[ivar, symra], donts=[andersen])
        with self.litterature(specific=True, grouped=True) as (ivar, symra, andersen, mbob):
            self.doesDelete(mbob, dos=[ivar], donts=[andersen, symra])

    def testDeleteAuthor(self):
        for specific in [False, True]:
            with self.litterature(specific=specific, grouped=False) as (ivar, symra, andersen, mbob):
                self.doesDelete(ivar, dos=[symra], donts=[andersen, mbob])
            with self.litterature(specific=specific, grouped=True) as (ivar, symra, andersen, mbob):
                self.doesDelete(ivar, dos=[symra, mbob], donts=[andersen])
