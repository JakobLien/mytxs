import datetime
import os
import json

from django import forms
from django.apps import apps
from django.conf import settings as djangoSettings
from django.core import mail
from django.db import models
from django.db.models import Value as V, Q, Case, When, Max, Sum, ExpressionWrapper, F, OuterRef, Subquery, Prefetch, Exists
from django.db.models.functions import Concat, ExtractMinute, ExtractHour, Right, Coalesce, Cast
from django.forms import ValidationError
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.utils.safestring import mark_safe
from django.utils.functional import cached_property

from mytxs import consts
from mytxs import settings as mytxsSettings
from mytxs.fields import BitmapMultipleChoiceField, MyDateField, MyManyToManyField, MyTimeField
from mytxs.utils.formUtils import toolTip
from mytxs.utils.googleCalendar import updateGoogleCalendar
from mytxs.utils.modelCacheUtils import DbCacheModel, cacheQS, dbCache
from mytxs.utils.modelUtils import NoReuseMin, annotateInstance, bareAktiveDecorator, qBool, groupBy, getInstancesForKor, isStemmegruppeVervNavn, korLookup, stemmegruppeOrdering, strToModels, validateBruktIKode, validateM2MFieldEmpty, validateStartSlutt, vervInnehavelseAktiv, stemmegruppeVerv
from mytxs.utils.navBar import navBarNode
from mytxs.utils.utils import cropImage


class LoggQuerySet(models.QuerySet):
    def getLoggForModelPK(self, model, pk):
        'Gets the most recent logg given a model (which may be a string or an actual model) and a pk'
        if type(model) == str:
            model = apps.get_model('mytxs', model)
        return Logg.objects.filter(model=model.__name__, instancePK=pk).order_by('-timeStamp').first()
    
    def getLoggFor(self, instance):
        'Gets the most recent logg corresponding to the instance'
        return self.getLoggForModelPK(type(instance), instance.pk)

    def getLoggLinkFor(self, instance):
        'get_absolute_url for the most recent logg correpsonding to the instance'
        if logg := self.getLoggFor(instance):
            return logg.get_absolute_url()


class Logg(models.Model):
    objects = LoggQuerySet.as_manager()
    timeStamp = models.DateTimeField(auto_now_add=True)

    kor = models.ForeignKey(
        'Kor',
        related_name='logger',
        on_delete=models.SET_NULL,
        null=True
    )

    author = models.ForeignKey(
        'Medlem',
        on_delete=models.SET_NULL,
        null=True,
        related_name='logger'
    )

    CREATE, UPDATE, DELETE = 1, 0, -1
    CHANGE_CHOICES = ((CREATE, 'Create'), (UPDATE, 'Update'), (DELETE, 'Delete'))
    change = models.SmallIntegerField(choices=CHANGE_CHOICES, null=False)
    
    model = models.CharField(
        max_length=50
    )
    'Dette er model.__name__'

    instancePK = models.PositiveIntegerField(
        null=False
    )

    value = models.JSONField(null=False)
    'Se to_dict i mytxs/signals/logSignals.py'

    strRep = models.CharField(null=False, max_length=255)
    'String representasjon av objektet loggen anngår, altså resultatet av str(obj)'

    def getModel(self):
        return apps.get_model('mytxs', self.model)

    def formatValue(self):
        '''
        Returne oversiktlig json representasjon av objektet, med <a> lenker
        satt inn der det e foreign keys til andre Logg objekt, slik at dette
        fint kan settes direkte inn i en <pre> tag.
        '''
        jsonRepresentation = json.dumps(self.value, indent=4)

        foreignKeyFields = list(filter(lambda field: isinstance(field, models.ForeignKey), self.getModel()._meta.get_fields()))

        lines = jsonRepresentation.split('\n')

        def getLineKey(line):
            return line.split(':')[0].strip().replace('"', '')

        for l in range(len(lines)):
            for foreignKeyField in foreignKeyFields:
                if foreignKeyField.name == getLineKey(lines[l]) and type(self.value[foreignKeyField.name]) == int:
                    relatedLogg = Logg.objects.filter(pk=self.value[foreignKeyField.name]).first()

                    lines[l] = lines[l].replace(f'{self.value[foreignKeyField.name]}', 
                        f'<a href={relatedLogg.get_absolute_url()}>{relatedLogg.strRep}</a>')

        jsonRepresentation = '\n'.join(lines)

        return mark_safe(jsonRepresentation)

    def getReverseRelated(self):
        'Returne en liste av logger som referere (1:1 eller n:1) til denne loggen'
        reverseForeignKeyRels = list(filter(lambda field: isinstance(field, models.ManyToOneRel), self.getModel()._meta.get_fields()))
        foreignKeyFields = list(map(lambda rel: rel.remote_field, reverseForeignKeyRels))
        
        qs = Logg.objects.none()

        for foreignKeyField in foreignKeyFields:
            qs |= Logg.objects.filter(
                Q(**{f'value__{foreignKeyField.name}': self.pk}),
                model=foreignKeyField.model.__name__,
            )

        return qs
    
    def getM2MRelated(self):
        'Skaffe alle m2m logger for denne loggen'
        return groupBy(self.forwardM2Ms.all() | self.backwardM2Ms.all(), 'm2mName')

    def getActual(self):
        'Get the object this Logg is a log of, if it exists'
        return self.getModel().objects.filter(pk=self.instancePK).first()
    
    def getActualUrl(self):
        'get_absolute_url for the object this Logg is a log of, if it exists'
        if actual := self.getActual():
            if hasattr(actual, 'get_absolute_url'):
                return actual.get_absolute_url()

    def nextLogg(self):
        return Logg.objects.filter(
            model=self.model,
            instancePK=self.instancePK,
            timeStamp__gt=self.timeStamp
        ).order_by('timeStamp').first()
    
    def lastLogg(self):
        return Logg.objects.filter(
            model=self.model,
            instancePK=self.instancePK,
            timeStamp__lt=self.timeStamp
        ).order_by('-timeStamp').first()

    def get_absolute_url(self):
        return reverse('logg', args=[self.pk])

    def __str__(self):
        return f'{self.model}{"-*+"[self.change+1]} {self.strRep}'

    class Meta:
        ordering = ['-timeStamp', '-pk']
        verbose_name_plural = 'logger'


class LoggM2M(models.Model):
    timeStamp = models.DateTimeField(auto_now_add=True)

    m2mName = models.CharField(
        max_length=50
    )
    'A string containing the m2m source model name and the m2m field name separated by an underscore'

    author = models.ForeignKey(
        'Medlem',
        on_delete=models.SET_NULL,
        null=True,
        related_name='M2Mlogger'
    )

    fromLogg = models.ForeignKey(
        Logg,
        on_delete=models.CASCADE,
        null=False,
        related_name='forwardM2Ms'
    )

    toLogg = models.ForeignKey(
        Logg,
        on_delete=models.CASCADE,
        null=False,
        related_name='backwardM2Ms'
    )

    CREATE, DELETE = 1, -1
    CHANGE_CHOICES = ((CREATE, 'Create'), (DELETE, 'Delete'))
    change = models.SmallIntegerField(choices=CHANGE_CHOICES, null=False)

    def correspondingM2M(self, forward=True):
        'Gets the corresponding create or delete M2M'
        if self.change == LoggM2M.CREATE:
            return LoggM2M.objects.filter(
                fromLogg__instancePK=self.fromLogg.instancePK,
                toLogg__instancePK=self.toLogg.instancePK,
                m2mName=self.m2mName,
                change=LoggM2M.DELETE,
                timeStamp__gt=self.timeStamp
            ).order_by(
                'timeStamp'
            ).first()
        else:
            return LoggM2M.objects.filter(
                fromLogg__instancePK=self.fromLogg.instancePK,
                toLogg__instancePK=self.toLogg.instancePK,
                m2mName=self.m2mName,
                change=LoggM2M.CREATE,
                timeStamp__lt=self.timeStamp
            ).order_by(
                '-timeStamp'
            ).first()

    def __str__(self):
        return f'{self.m2mName}{"-_+"[self.change+1]} {self.fromLogg.strRep} <-> {self.toLogg.strRep}'

    class Meta:
        ordering = ['-timeStamp', '-pk']


class MedlemQuerySet(models.QuerySet):
    def annotateFulltNavn(self):
        'Annotate deres navn med korrekt mellomrom som "fulltNavn", viktig for søk på medlemmer'
        return self.annotate(
            fulltNavn=Case(
                When(
                    mellomnavn='',
                    then=Concat('fornavn', V(' '), 'etternavn')
                ),
                default=Concat('fornavn', V(' '), 'mellomnavn', V(' '), 'etternavn')
            )
        )

    def annotateKarantenekor(self, kor=None, storkor=False):
        '''
        Annotate året de hadde sitt første stemmegruppe eller dirr verv. 
        Gi kor argumentet for å spesifiser kor, eller gi storkor for å bruk storkor. 
        Merk at man kanskje må refresh querysettet dersom man allerede har filtrert på stemmegruppeverv. 
        '''
        return self.annotate(
            karantenekor=NoReuseMin(
                'vervInnehavelser__start__year',
                filter=
                    stemmegruppeVerv('vervInnehavelser__verv', includeDirr=True) &
                    (korLookup(kor, 'vervInnehavelser__verv__kor') if kor else qBool(True)) &
                    (Q(vervInnehavelser__verv__kor__navn__in=consts.bareStorkorNavn) if storkor else qBool(True))
            )
        )
    
    def annotateKor(self, annotationNavn='korNavn', korAlternativ=consts.bareStorkorNavn, aktiv=False):
        '''
        Annotater korNavn som det tidligste koret av korAlternativ, bare aktive kor dersom aktiv=True.
        I utgangspunktet annotater dette storkoret til vedkommende. 
        '''
        return self.annotate(
            **{annotationNavn: Subquery(
                VervInnehavelse.objects.filter(
                    stemmegruppeVerv(includeDirr=True),
                    vervInnehavelseAktiv('') if aktiv else qBool(True),
                    verv__kor__navn__in=korAlternativ,
                    medlem=OuterRef('pk')
                ).order_by('start').values('verv__kor__navn')[:1]
            )}
        )

    def annotateStemmegruppe(self, kor=None, includeUkjent=False, understemmegruppe=False, includeDirr=False, pkPath='pk'):
        '''
        Annotate navnet på stemmegruppen medlemmet har i koret. 
        Om includeDirr er False og querysettet inneholder dirra, annotates None på dirrigenten. 
        '''
        return self.annotate(
            stemmegruppe=Subquery(
                VervInnehavelse.objects.filter(
                    vervInnehavelseAktiv(''),
                    stemmegruppeVerv(includeUkjentStemmegruppe=includeUkjent, includeDirr=includeDirr),
                    korLookup(kor, 'verv__kor') if kor else qBool(True),
                    medlem=OuterRef(pkPath)
                ).values('verv__navn')[:1]
            )
        ).annotate(
            stemmegruppe=Case(
                When(
                    stemmegruppe__in=[None, 'ukjentStemmegruppe', 'Dirigent'],
                    then='stemmegruppe'
                ),
                default=Right('stemmegruppe', 3 if understemmegruppe else 2)
            )
        )

    def annotatePublic(self, overrideVisible=False):
        'Annotate public__[personinfo], og fylle det inn basert på ka som e sjekkheftesynlig'
        conditionDict = {}
        valueDict = {}
        for i, option in enumerate(consts.sjekkhefteSynligOptions):
            conditionDict[f'public__{option}'] = Cast(F('innstillinger__sjekkhefteSynlig'), models.IntegerField()).bitand(2**i)

            valueDict[f'public__{option}'] = Case(
                When(
                    Q(**{f'public__{option}__gt': 0}) | qBool(overrideVisible),
                    then=F(option)
                ),
                default=V(None)
            )
        
        return self.annotate(**conditionDict).annotate(**valueDict)

    def sjekkheftePrefetch(self, kor):
        'Prefetch all dataen vi skal ha i det koret. Om Kor er None prefetches ingenting.'
        return self.prefetch_related(
            Prefetch('vervInnehavelser', queryset=VervInnehavelse.objects.none() if kor == None else VervInnehavelse.objects.filter(
                vervInnehavelseAktiv(''),
                ~stemmegruppeVerv(includeDirr=True),
                verv__kor__navn__in=[kor.navn, 'Sangern'] if kor.navn in consts.bareStorkorNavn else [kor.navn]
            ).prefetch_related('verv__kor')),
            Prefetch('dekorasjonInnehavelser', queryset=DekorasjonInnehavelse.objects.none() if kor == None else DekorasjonInnehavelse.objects.filter(
                dekorasjon__kor__navn__in=[kor.navn, 'Sanger'] if kor.navn in consts.bareStorkorNavn else [kor.navn]
            ).exclude(
                dekorasjon__overvalør__dekorasjonInnehavelser__medlem__id=F('medlem__id')
            ).prefetch_related('dekorasjon__kor')),
        )

    def annotatePermisjon(self, kor, dato=None):
        return self.annotate(
            permisjon=Exists(VervInnehavelse.objects.filter(
                vervInnehavelseAktiv('', dato=dato),
                korLookup(kor, 'verv__kor'),
                verv__navn='Permisjon',
                medlem=OuterRef('pk')
            ))
        )

    def annotateFravær(self, kor, heleSemesteret=False):
        'Annotater gyldigFravær, ugyldigFravær og hendelseVarighet'
        def getDateTime(fieldName, backupDateFieldName=None):
            'Kombinere og returne separate Date og Time felt til ett DateTime felt'
            return ExpressionWrapper(
                (Coalesce(f'{fieldName}Date', f'{backupDateFieldName}Date') if backupDateFieldName else F(f'{fieldName}Date')) + 
                F(f'{fieldName}Time'),
                output_field=models.DateTimeField()
            )

        hendelseVarighet = ExpressionWrapper(
            ExtractMinute(getDateTime('oppmøter__hendelse__slutt', backupDateFieldName='oppmøter__hendelse__start') - getDateTime('oppmøter__hendelse__start')) + 
            ExtractHour(getDateTime('oppmøter__hendelse__slutt', backupDateFieldName='oppmøter__hendelse__start') - getDateTime('oppmøter__hendelse__start')) * 60,
            output_field=models.IntegerField()
        )

        today = datetime.date.today()

        filterQ = Q(
            Q(oppmøter__hendelse__startDate__month__gte=7) if today.month >= 7 else Q(oppmøter__hendelse__startDate__month__lt=7),
            korLookup(kor, 'oppmøter__hendelse__kor'),
            oppmøter__hendelse__startDate__year=today.year,
            oppmøter__hendelse__kategori=Hendelse.OBLIG
        )

        filterQWithPast = Q(filterQ, oppmøter__hendelse__startDate__lt=datetime.date.today())

        return self.annotate(
            gyldigFravær = Sum('oppmøter__fravær', default=0, filter=Q(filterQWithPast, oppmøter__gyldig=Oppmøte.GYLDIG)) + 
                Sum(hendelseVarighet, default=0, filter=Q(filterQWithPast, oppmøter__gyldig=Oppmøte.GYLDIG, oppmøter__fravær=None)),
            ugyldigFravær = Sum('oppmøter__fravær', default=0, filter=Q(filterQWithPast, ~Q(oppmøter__gyldig=Oppmøte.GYLDIG))) + 
                Sum(hendelseVarighet, default=0, filter=Q(filterQWithPast, ~Q(oppmøter__gyldig=Oppmøte.GYLDIG),oppmøter__fravær=None)),
            hendelseVarighet = Sum(hendelseVarighet, default=0, filter=filterQ if heleSemesteret else filterQWithPast)
        )


class Medlem(DbCacheModel):
    objects = MedlemQuerySet.as_manager()

    user = models.OneToOneField(
        djangoSettings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='medlem',
        blank=True
    )

    fornavn = models.CharField(max_length = 50, default='Autogenerert')
    mellomnavn = models.CharField(max_length = 50, default='', blank=True)
    etternavn = models.CharField(max_length = 50, default='Testbruker')

    @property
    def navn(self):
        'Returne navnet med korrekt mellomrom'
        if self.mellomnavn:
            return f'{self.fornavn} {self.mellomnavn} {self.etternavn}'
        else:
            return f'{self.fornavn} {self.etternavn}'

    gammeltMedlemsnummer = models.CharField(max_length=9, default='', blank=True, verbose_name='Gammelt medlemsnummer')
    'Formatet for dette er "TSS123456" eller "TKS123456"'

    # Følgende fields er bundet av GDPR, vi må ha godkjennelse fra medlemmet for å lagre de. 
    fødselsdato = MyDateField(null=True, blank=True)
    epost = models.EmailField(max_length=100, blank=True)
    tlf = models.CharField(max_length=20, default='', blank=True)
    studieEllerJobb = models.CharField(max_length=100, blank=True, verbose_name='Studie eller jobb')
    boAdresse = models.CharField(max_length=100, blank=True, verbose_name='Bo adresse')
    foreldreAdresse = models.CharField(max_length=100, blank=True, verbose_name='Foreldre adresse')

    sjekkhefteSynlig = BitmapMultipleChoiceField(choicesList=consts.sjekkhefteSynligOptions, verbose_name='Synlig i sjekkheftet', editable=False)
    matpreferanse = BitmapMultipleChoiceField(choicesList=consts.matpreferanseOptions)

    def generateUploadTo(instance, fileName):
        path = 'sjekkhefteBilder/'
        format = f'{instance.pk}.{fileName.split(".")[-1]}'
        fullPath = os.path.join(path, format)
        return fullPath

    bilde = models.ImageField(upload_to=generateUploadTo, null=True, blank=True)

    ønskerVårbrev = models.BooleanField(default=False, verbose_name='Ønsker vårbrev')
    død = models.BooleanField(default=False)
    notis = models.TextField(blank=True)

    innstillinger = models.JSONField(null=False, default=dict, editable=False)
    'For å lagre ting som endrer hvordan brukeren ser siden, f.eks. tversAvKor, disableTilganger osv'

    overførtData = models.BooleanField(default=False, editable=False)

    @dbCache(affectedByFields=['vervInnehavelser'])
    def storkorNavn(self):
        annotateInstance(self, lambda qs: qs.annotateKor())
        return self.korNavn

    @cached_property
    def aktiveKor(self):
        'Returne kor medlemmet er aktiv i, sortert med storkor først. Ignorerer permisjon.'
        return cacheQS(Kor.objects.filter(
            stemmegruppeVerv(includeDirr=True),
            vervInnehavelseAktiv('verv__vervInnehavelser'),
            verv__vervInnehavelser__medlem=self
        ).orderKor(), props=['navn'])

    def getHendelser(self, korNavn):
        'Returne et queryset av hendelsan dette medlemmet har i den kor-kalenderen (Sangern hendelser havner i storkor kalender)'
        korStart = self.vervInnehavelser.filter(
            stemmegruppeVerv(includeDirr=True),
            verv__kor__navn=korNavn
        ).order_by('start').first().start

        return Hendelse.objects.filter(
            # For storkor skaffe vi hendelsa for dem og Sangern, for småkor skaffe vi bare det korets hendelsa. 
            qBool(korNavn in consts.bareStorkorNavn, trueOption=Q(kor__navn__in=[korNavn, 'Sangern']), falseOption=Q(kor__navn=korNavn)),
            # For undergruppe hendelsa må man vær invitert for å få det opp
            ~Q(kategori=Hendelse.UNDERGRUPPE) | Q(oppmøter__medlem=self),
            startDate__gte=korStart
        ).distinct()

    @property
    def faktiskeTilganger(self):
        'Returne aktive bruktIKode tilganger, til bruk i addOptionForm som trenger å vite hvilke tilganger du har før innstillinger filtrering'
        return Tilgang.objects.filter(vervInnehavelseAktiv('verv__vervInnehavelser', utvidetStart=datetime.timedelta(days=60)), verv__vervInnehavelser__medlem=self, bruktIKode=True).distinct()

    @cached_property
    def tilganger(self):
        'Returne aktive tilganger etter å ha filtrert på innstillinger'
        if self.innstillinger.get('disableTilganger', False):
            return Tilgang.objects.none()
        
        if self.user.is_superuser:
            tilganger = Tilgang.objects.filter(
                Q(navn__in=self.innstillinger.get('adminTilganger', [])),
                Q(kor__navn__in=self.innstillinger.get('adminTilgangerKor', []))
            )
        else:
            tilganger = self.faktiskeTilganger
        
        if not self.innstillinger.get('tversAvKor', False):
            tilganger = tilganger.exclude(navn='tversAvKor')
        return cacheQS(tilganger.select_related('kor'), props=['navn', 'kor', 'kor__navn'])
    
    @cached_property
    def navBar(self):
        '''
        Dette returne en dict som rekursivt inneheld flere dicts eller True basert på tilganger. Dette ugjør dermed
        hvilke sider i navbar medlemmet får opp, samt hvilke undersider medlemmet får opp. 

        For å sjekke om brukeren har tilgang til en side bruker vi medlem.navBar.[sidenavn] i template eller 
        medlem.navBar.get(sidenavn) i python. Løvnodene er True slik at tilgang til siden skal funke likt med og uten 
        subpages. Om det er ryddigere kan en løvnode settes til False. Den filtreres da bort før vi returne. 
        
        Veldig viktig at dette ikke returne noko som inneheld querysets, for da vil vi hitte databasen veldig mange ganger!
        Dette e også en av få deler av kodebasen som faktisk kjører på alle sider, så fint å optimaliser denne koden 
        så my som mulig mtp databaseoppslag. 
        '''
        sider = navBarNode(inURL=False, isPage=False)

        # Sjekkheftet
        sjekkheftet = navBarNode(sider, 'sjekkheftet', isPage=False)
        if self.storkorNavn() == 'TKS':
            sjekkhefteRekkefølge = consts.bareKorNavnTKSRekkefølge
        else:
            sjekkhefteRekkefølge = consts.bareKorNavn
        sjekkheftet.addChildren(*sjekkhefteRekkefølge[:2])

        # Alle tiders småkorist skal få opp småkoret i sjekkheftet
        if småkor := Kor.objects.filter(
            stemmegruppeVerv(includeDirr=True),
            verv__vervInnehavelser__medlem=self,
            navn__in=consts.alleKorNavn[2:5]
        ).values_list('navn', flat=True):
            sjekkheftet.addChildren(*småkor)
        sjekkheftet.addChildren('Sangern', isPage=False)

        # Sjekkheftet undergrupper
        for sjekkhefteSide in Tilgang.objects.filter(
            sjekkheftetSynlig=True, 
            kor__navn__in=sjekkheftet.children.keys()
        ).values('navn', 'kor__navn'):
            navBarNode(sider['sjekkheftet', sjekkhefteSide['kor__navn']], sjekkhefteSide['navn'])
        sjekkheftet.addChildren('søk', 'kart', 'jubileum', 'sjekkhefTest')

        # Semesterplan
        navBarNode(sider, 'semesterplan', isPage=False)
        for kor in self.aktiveKor.values_list('navn', flat=True):
            navBarNode(sider['semesterplan'], kor)
        
        #Lenker
        if self.aktiveKor.exists() or self.tilganger.filter(navn__in=['tversAvKor', 'lenke']).exists():
            navBarNode(sider, 'lenker')

        # Herunder er admin sidene
        admin = navBarNode(sider, 'admin', inURL=False, isPage=False)

        if self.tilganger.filter(navn__in=['tversAvKor', 'medlemsdata', 'vervInnehavelse', 'dekorasjonInnehavelse', 'turne']).exists():
            navBarNode(admin, 'medlem')

        if self.tilganger.filter(navn__in=['tversAvKor', 'semesterplan', 'fravær']).exists():
            navBarNode(admin, 'hendelse', defaultParameters=f'?start={datetime.date.today()}')

        if self.tilganger.filter(navn__in=['tversAvKor', 'fravær']).exists():
            fravær = navBarNode(admin, 'fravær', isPage=False)
            navBarNode(fravær, 'søknader', defaultParameters='?gyldig=None&harMelding=on')

            fraværOversikt = navBarNode(fravær, 'oversikt', isPage=False)
            if korMedFraværTilgang := Kor.objects.filter(tilganger__in=self.tilganger.filter(navn='fravær')).values_list('navn', flat=True):
                fraværOversikt.addChildren(*korMedFraværTilgang)

            fraværStatistikk = navBarNode(fravær, 'statistikk', isPage=False)
            if korMedFraværTilgang := Kor.objects.filter(tilganger__in=self.tilganger.filter(navn='fravær')).values_list('navn', flat=True):
                fraværStatistikk.addChildren(*korMedFraværTilgang)

        if self.tilganger.filter(navn__in=['tversAvKor', 'vervInnehavelse', 'verv', 'tilganger']).exists():
            navBarNode(admin, 'verv', defaultParameters='?sistAktiv=1')

        if self.tilganger.filter(navn__in=['tversAvKor', 'dekorasjonInnehavelse', 'dekorasjon']).exists():
            navBarNode(admin, 'dekorasjon')

        if self.tilganger.filter(navn__in=['tversAvKor', 'tilgang']).exists():
            navBarNode(admin, 'tilgang')
            navBarNode(admin['tilgang'], 'oversikt')

        if self.tilganger.filter(navn__in=['tversAvKor', 'turne']).exists():
            navBarNode(admin, 'turne')

        if self.tilganger.exists():
            navBarNode(admin, 'logg')
        
        if self.tilganger.filter(navn__in=['eksport']).exists():
            navBarNode(admin, 'eksport', isPage=False)
            for tilgang in self.tilganger.filter(navn__in=['eksport']):
                navBarNode(admin['eksport'], tilgang.kor.navn)
        
        sider.generateURLs()

        return sider

    def harRedigerTilgang(self, instance):
        '''
        Returne om medlemmet har tilgang til å redigere instansen, både for instances i databasen og ikkje.
        Ikke i databasen e f.eks. når vi har et inlineformset som allerede har satt kor på objektet vi kan create. 
        '''
        if instance.pk:
            # Dersom instansen finnes i databasen
            return self.redigerTilgangQueryset(type(instance)).contains(instance)
        
        if kor := instance.kor:
            # Dersom den ikke finnes, men den vet hvilket kor den havner i
            return Kor.objects.filter(tilganger__in=self.tilganger.filter(navn=consts.modelTilTilgangNavn[type(instance).__name__])).contains(kor)

        # Ellers, return om vi har noen tilgang til den typen objekt
        return self.tilganger.filter(navn=consts.modelTilTilgangNavn[type(instance).__name__]).exists()

    @bareAktiveDecorator
    def redigerTilgangQueryset(self, model, resModel=None, fieldType=None):
        '''
        Returne et queryset av objekter vi har tilgang til å redigere. 
        
        resModel brukes for å si at vi ønske å få instances fra resModel istedet, fortsatt for kor 
        som vi har tilgang til å endre på model. Brukes for å sjekke hvilke relaterte objekter vi kan 
        velge i ModelChoiceField.

        FieldType e enten ModelChoiceField eller ModelMultipleChoiceField, og brukes for å håndter at vi har
        tilgang til ting på tvers av kor når model og resModel stemme. Uten tversAvKor endrer dette ingenting. 
        '''

        # Sett resModel om ikke satt
        if not resModel:
            resModel = model
        
        # Dersom vi prøve å skaff relatert queryset, håndter tversAvKor
        elif self.tilganger.filter(navn='tversAvKor').exists() and model != resModel and (
            # For ModelChoiceField: Sjekk at resModel ikke er modellen som model.kor avhenger av
            # Tenk vervInnehavelse: Med tversAvKor tilgangen skal vi få tilgang til alle medlememr, men ikke alle verv.
            # F.eks. i newForm vil vi få mulighet til å opprette ting på alle kor dersom vi ikke har med default get 'Kor'
            (fieldType == forms.ModelChoiceField and consts.korAvhengerAv.get(model.__name__, 'Kor') != resModel.__name__) or 
            # For ModelMultipleChoiceField: Bare sjekk at det e et ModelMultipleChoiceField. Om vi bruke redigerTilgangQueryset
            # rett model alltid være modellen den som styrer tilgangen på feltet, og om resModel ikke erlik den kan den anntas
            # å være den andre siden. 
            (fieldType == forms.ModelMultipleChoiceField)
        ):
            return resModel.objects.all()

        # Medlem er komplisert fordi medlem ikke har et enkelt forhold til kor. 
        if model == Medlem:
            # Skaff medlemmer i koret du har tilgangen
            medlemmer = getInstancesForKor(resModel, Kor.objects.filter(tilganger__in=self.tilganger.filter(navn='medlemsdata')))
            
            # Dersom du har tversAvKor, hiv på alle medlemmer uten kor
            if resModel == Medlem and self.tilganger.filter(navn='tversAvKor').exists():
                medlemmer |= Medlem.objects.exclude(
                    stemmegruppeVerv('vervInnehavelser__verv', includeDirr=True)
                )

            return medlemmer

        # For alle andre modeller, bare skaff objektene for modellen og koret du evt har tilgangen. 
        returnQueryset = getInstancesForKor(resModel, Kor.objects.filter(tilganger__in=self.tilganger.filter(navn=consts.modelTilTilgangNavn[model.__name__])))

        # Exclude Verv og VervInnehavelser som gir tilganger som medlemmet ikke har, dersom medlemmet ikke har tilgang tilgangen 
        # i koret til vervet. Dette hindre at noen med vervInnehavelse tilgangen kan gjøre seg selv til Formann og gå løs på 
        # medlemsregisteret, men fungere også for alle verv som gir tilganger man ikkje selv har. 
        
        if model in [Verv, VervInnehavelse] and resModel in [Verv, VervInnehavelse]:
            if resModel == Verv:
                return returnQueryset.exclude(
                    ~Q(kor__tilganger__in=self.tilganger.filter(navn='tilgang')),
                    tilganger__in=Tilgang.objects.exclude(pk__in=self.tilganger),
                )
            if resModel == VervInnehavelse:
                return returnQueryset.exclude(
                    ~Q(verv__kor__tilganger__in=self.tilganger.filter(navn='tilgang')),
                    verv__tilganger__in=Tilgang.objects.exclude(pk__in=self.tilganger), 
                )

        return returnQueryset
    
    def harSideTilgang(self, instance):
        'Returne en boolean som sie om man har tilgang til denne siden'
        return self.sideTilgangQueryset(type(instance)).contains(instance)

    @bareAktiveDecorator
    def sideTilgangQueryset(self, model):
        '''
        Returne queryset av objekt der vi har tilgang til noe på den tilsvarende siden.
        Dette slår altså sammen logikken for 
        1. Hva som kommer opp i lister
        2. Hvilke sider man har tilgang til, og herunder hvilke logger man har tilgang til
        '''

        # Om du har tversAvKor sie vi at du har sidetilgang til alle objekt. Det e en overforenkling som unødvendig også 
        # gir sideTilgang til f.eks. andre kor sine tilgang sider, men det gjør at denne koden bli ekstremt my enklar.
        # Alternativt hadd vi måtta skrevet "Om du har tversAvKor tilgangen i samme kor som en tilgang til en relasjon
        # til andre objekt, har du tilgang til alle andre slike objekter.", som e veldig vanskelig å uttrykke godt. Vi kan prøv å 
        # fiks dette i framtiden om vi orke og ser behov for det. E gjør ikke det no. 

        # Dette gjør også at de eneste som kan styre med folk som ikke har kor er korlederne, som virke fair. 
        if self.tilganger.filter(navn='tversAvKor').exists() and model in [Medlem, Verv]:
            return model.objects.all()
        
        # For Logg sjekke vi bare om du har tilgang til modellen og koret loggen refererer til
        if model == Logg:
            loggs = Logg.objects.none()
            for loggedModel in strToModels(consts.loggedModelNames):
                loggs |= Logg.objects.filter(
                    Q(model=loggedModel.__name__, instancePK__in=self.redigerTilgangQueryset(loggedModel).values_list('id', flat=True)) | 
                    Q(model=None)
                )
            return loggs

        # Du har tilgang til sider (som medlem) der du kan endre et relatert form (som vervInnehavelse, dekorasjonInnehavelse eller turneer). 
        # Dette kunna vi åpenbart automatisert meir, men e like slik det e no. Med full automatisering med modelUtils.getAllRelatedModels 
        # hadd f.eks. folk med tilgang til oppmøter hatt tilgang til alle medlemmer, som ikkje stemme overrens med siden. 
        # Det er trygt å returne dette siden det alltid vil være likt redigerTilgangQueryset eller større (trur e)
        for sourceModel, relatedModel in consts.modelWithRelated.items():
            if (
                (model.__name__ == sourceModel) and \
                (relatedTilgang := [consts.modelTilTilgangNavn[m] for m in relatedModel]) and \
                (relaterteTilganger := self.tilganger.filter(navn__in=relatedTilgang))
            ):
                return getInstancesForKor(model, Kor.objects.filter(tilganger__in=relaterteTilganger)) | self.redigerTilgangQueryset(model)

        # Forøverig, return de sidene der du kan redigere sidens instans
        return self.redigerTilgangQueryset(model)

    @property
    def kor(self):
        annotateInstance(self, MedlemQuerySet.annotateKor)
        return Kor.objects.get(navn=self.korNavn) if self.korNavn else None
    
    def get_absolute_url(self):
        return reverse('medlem', args=[self.pk])
    
    @dbCache(affectedByFields=['vervInnehavelser'])
    def __str__(self):
        if self.pk:
            # Det som allerede e annotata kan vær feil no, så gjør det på nytt!
            annotateInstance(self, MedlemQuerySet.annotateKor)
            annotateInstance(self, MedlemQuerySet.annotateKarantenekor, storkor=True)
            if self.korNavn:
                return f'{self.navn} {self.korNavn} ' + 'K' + (str(self.karantenekor)[-2:] if self.karantenekor >= 2000 else str(self.karantenekor))
        return self.navn
    
    class Meta:
        ordering = ['fornavn', 'mellomnavn', 'etternavn', '-pk']
        verbose_name_plural = 'medlemmer'

    def save(self, *args, **kwargs):
        # Crop bildet om det har endret seg
        if self.pk and self.bilde and self.bilde != Medlem.objects.get(pk=self.pk).bilde:
            self.bilde = cropImage(self.bilde, self.bilde.name, 270, 330)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        validateM2MFieldEmpty(self, 'turneer')
        super().delete(*args, **kwargs)


class KorQuerySet(models.QuerySet):
    def orderKor(self, tksRekkefølge=False):
        'Sorter kor på storkor først og deretter på kjønnsfordeling'
        return self.order_by(Case(
            *[When(navn=kor, then=i) for i, kor in 
                (enumerate(consts.bareKorNavn if not tksRekkefølge else consts.bareKorNavnTKSRekkefølge))
            ]
        ))


class Kor(models.Model):
    objects = KorQuerySet.as_manager()

    navn = models.CharField(max_length=10)
    tittel = models.CharField(max_length=50)
    stemmefordeling = models.CharField(choices=[(sf, sf) for sf in ['SA', 'TB', 'SATB', '']], default='', blank=True)

    def stemmegrupper(self, lengde=2):
        'Skaffe stemmegruppan til koret (strings) opp til ønsket lengde'
        if self.navn == 'Sangern':
            return []
        stemmegrupper = ','.join(self.stemmefordeling)
        for i in range(1, lengde):
            stemmegrupper = ','.join([f'1{s},2{s}' for s in stemmegrupper.split(',')])
        return stemmegrupper.split(',')

    # Dropper å drive med strRep her, blir bare overhead for ingen fortjeneste
    def __str__(self):
        return self.navn
    
    class Meta:
        verbose_name_plural = 'kor'


class Verv(DbCacheModel):
    navn = models.CharField(max_length=50)

    kor = models.ForeignKey(
        Kor,
        related_name='verv',
        on_delete=models.DO_NOTHING,
        null=True
    )

    bruktIKode = models.BooleanField(
        default=False, 
        help_text=toolTip('Hvorvidt vervet er brukt i kode og følgelig ikke kan endres på av brukere.'),
        verbose_name='Brukt i kode'
    )

    @cached_property
    def stemmegruppeVerv(self):
        return isStemmegruppeVervNavn(self.navn)

    def get_absolute_url(self):
        return reverse('verv', args=[self.kor.navn, self.navn])

    @dbCache
    def __str__(self):
        return f'{self.navn}({self.kor.navn})'
    
    class Meta:
        unique_together = ('navn', 'kor')
        ordering = ['kor', stemmegruppeOrdering(), 'navn']
        verbose_name_plural = 'verv'

    def clean(self, *args, **kwargs):
        validateBruktIKode(self)
    
    def delete(self, *args, **kwargs):
        validateM2MFieldEmpty(self, 'tilganger')
        super().delete(*args, **kwargs)


class VervInnehavelse(DbCacheModel):
    medlem = models.ForeignKey(
        Medlem,
        on_delete=models.PROTECT,
        null=False,
        related_name='vervInnehavelser'
    )
    verv = models.ForeignKey(
        Verv,
        on_delete=models.PROTECT,
        null=False,
        related_name='vervInnehavelser'
    )
    start = MyDateField(blank=False)
    slutt = MyDateField(blank=True, null=True)
    
    @property
    def aktiv(self):
        return self.start <= datetime.date.today() and (self.slutt == None or datetime.date.today() <= self.slutt)

    @property
    def kor(self):
        return self.verv.kor if self.verv_id else None
    
    @dbCache(affectedByCache=['medlem', 'verv'])
    def __str__(self):
        return f'{self.medlem.__str__()} -> {self.verv.__str__()}'
    
    class Meta:
        unique_together = ('medlem', 'verv', 'start')
        ordering = ['-start', '-slutt', '-pk']
        verbose_name_plural = 'vervinnehavelser'

    def clean(self, *args, **kwargs):
        validateStartSlutt(self)
        # Valider at dette medlemmet ikke har dette vervet i samme periode med en annen vervInnehavelse.
        if hasattr(self, 'verv'):
            if self.verv.stemmegruppeVerv:
                if VervInnehavelse.objects.filter(
                    ~Q(pk=self.pk),
                    stemmegruppeVerv(),
                    ~(Q(slutt__isnull=False) & Q(slutt__lt=self.start)),
                    ~qBool(self.slutt, trueOption=Q(start__gt=self.slutt)),
                    verv__kor=self.kor,
                    medlem=self.medlem,
                ).exists():
                    raise ValidationError(
                        _('Kan ikke ha flere stemmegruppeverv i samme kor samtidig'),
                        code='overlappingVervInnehavelse'
                    )
            else:
                if VervInnehavelse.objects.filter(
                    ~Q(pk=self.pk),
                    ~(Q(slutt__isnull=False) & Q(slutt__lt=self.start)),
                    ~qBool(self.slutt, trueOption=Q(start__gt=self.slutt)),
                    medlem=self.medlem,
                    verv=self.verv,
                ).exists():
                    raise ValidationError(
                        _('Kan ikke ha flere vervInnehavelser av samme verv samtidig'),
                        code='overlappingVervInnehavelse'
                    )

    def save(self, *args, **kwargs):
        self.clean()

        oldSelf = VervInnehavelse.objects.filter(pk=self.pk).first()

        super().save(*args, **kwargs)

        # Oppdater hvilke oppmøter man har basert på stemmegruppeVerv og permisjon

        # Per no ser e ikkje en ryddigar måte å gjør dette på, enn å bare prøv å minimer antall 
        # hendelser vi calle genererOppmøter på. Det e vanskelig å skaff hvilke oppmøter 
        # som blir lagt til og fjernet av en endring av varighet eller type av verv. Sammenlign
        # - "Medlemmer som har aktive stemmegruppeverv som ikke har permisjon den dagen."
        # - "Hendelsene som faller på dager der vi har endret et permisjon/stemmegruppeverv, 
        # eller dager vi ikke har endret dersom vi endrer typen verv."
        if self.verv.stemmegruppeVerv or self.verv.navn == 'Permisjon' or \
            (oldSelf and (oldSelf.verv.stemmegruppeVerv or oldSelf.verv.navn == 'Permisjon')):

            hendelser = Hendelse.objects.filter(kor=self.verv.kor)
            
            if not oldSelf:
                # Om ny vervInnehavelse, save på alle hendelser i varigheten
                hendelser.genererHendelseOppmøter(self.start, self.slutt)
            elif self.verv.stemmegruppeVerv != oldSelf.verv.stemmegruppeVerv or \
                (self.verv.navn == 'Permisjon') != (oldSelf.verv.navn == 'Permisjon'):
                # Om vi bytte hvilken type verv det er, save alle hendelser i hele perioden
                hendelser.genererHendelseOppmøter(self.start, self.slutt, oldSelf.start, oldSelf.slutt)
            else:
                # Om vi ikke bytte hvilken type verv det er, save hendelser som er 
                # mellom start og start, og mellom slutt og slutt
                if oldSelf.start != self.start:
                    hendelser.genererHendelseOppmøter(self.start, oldSelf.start)
                if oldSelf.slutt != self.slutt:
                    hendelser.genererHendelseOppmøter(self.slutt, oldSelf.slutt)
    
    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)

        # Om vi sletter vervInnehavelsen, save alle i varigheten
        if self.verv.stemmegruppeVerv or self.verv.navn == 'Permisjon':
            Hendelse.objects.filter(kor=self.verv.kor).genererHendelseOppmøter(self.start, self.slutt)


class Tilgang(DbCacheModel):
    navn = models.CharField(max_length=50)

    kor = models.ForeignKey(
        Kor,
        related_name='tilganger',
        on_delete=models.DO_NOTHING,
        null=True
    )

    verv = MyManyToManyField(
        Verv,
        related_name='tilganger',
        blank=True
    )

    beskrivelse = models.CharField(
        max_length=200, 
        default='',
        blank=True
    )

    bruktIKode = models.BooleanField(
        default=False, 
        help_text=toolTip('Hvorvidt tilgangen er brukt i kode og følgelig ikke kan endres på av brukere.'),
        verbose_name='Brukt i kode'
    )

    sjekkheftetSynlig = models.BooleanField(
        default=False,
        help_text=toolTip('Om de som har denne tilgangen skal vises som en gruppe i sjekkheftet.'),
        verbose_name='Synlig i sjekkheftet'
    )

    def get_absolute_url(self):
        return reverse('tilgang', args=[self.kor.navn, self.navn])

    @dbCache
    def __str__(self):
        if self.kor:
            return f'{self.kor.navn}-{self.navn}'
        return self.navn

    class Meta:
        unique_together = ('kor', 'navn')
        ordering = ['kor', 'navn']
        verbose_name_plural = 'tilganger'

    def clean(self, *args, **kwargs):
        validateBruktIKode(self)

    def delete(self, *args, **kwargs):
        validateM2MFieldEmpty(self, 'verv')
        super().delete(*args, **kwargs)


class Dekorasjon(DbCacheModel):
    navn = models.CharField(max_length=30)
    kor = models.ForeignKey(
        Kor,
        related_name='dekorasjoner',
        on_delete=models.DO_NOTHING,
        null=True
    )
    overvalør = models.OneToOneField(
        "self",
        related_name='undervalør',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    ikon = models.ImageField(null=True, blank=True)

    def get_absolute_url(self):
        return reverse('dekorasjon', args=[self.kor.navn, self.navn])

    @dbCache
    def __str__(self):
        return f'{self.navn}({self.kor.navn})'
    
    class Meta:
        unique_together = ('navn', 'kor')
        ordering = ['kor', 'navn']
        verbose_name_plural = 'dekorasjoner'

    def clean(self, *args, **kwargs):
        validateDekorasjon(self)

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


def validateDekorasjon(instance):
    if instance.overvalør is not None:
        if instance.overvalør.id == instance.id:
            raise ValidationError(
                _(f'{instance} kan ikke være undervalør av seg selv'),
                code='overvalørUgyldig',
            )
        ugyldigInnehavelse = instance.dekorasjonInnehavelser.annotate(overvalørStart=F('dekorasjon__overvalør__dekorasjonInnehavelser__start')).filter(overvalørStart__lt=F('start')).first()
        if ugyldigInnehavelse is not None:
            raise ValidationError(
                _(f'{ugyldigInnehavelse.medlem} kan ikke ha fått dekorasjonen {ugyldigInnehavelse.dekorasjon} ({ugyldigInnehavelse.start}) etter {ugyldigInnehavelse.dekorasjon.overvalør} ({ugyldigInnehavelse.overvalørStart})'),
                code='dekorasjonInnehavelseUgyldigDato'
            )


class DekorasjonInnehavelse(DbCacheModel):
    medlem = models.ForeignKey(
        Medlem,
        on_delete=models.PROTECT,
        null=False,
        related_name='dekorasjonInnehavelser'
    )
    dekorasjon = models.ForeignKey(
        Dekorasjon,
        on_delete=models.PROTECT,
        null=False,
        related_name='dekorasjonInnehavelser'
    )
    start = MyDateField(null=False)
    
    @property
    def kor(self):
        return self.dekorasjon.kor if self.dekorasjon_id else None
    
    @dbCache(affectedByCache=['medlem', 'dekorasjon'])
    def __str__(self):
        return f'{self.medlem.__str__()} -> {self.dekorasjon.__str__()}'
    
    class Meta:
        unique_together = ('medlem', 'dekorasjon', 'start')
        ordering = ['-start', '-pk']
        verbose_name_plural = 'dekorasjoninnehavelser'

    def clean(self, *args, **kwargs):
        validateDekorasjonInnehavelse(self)

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


def validateDekorasjonInnehavelse(instance):
    '''
    Sjekke om medlemmet innehar eventuell undervalør, og sjekke om startdato
    er kompatibel med eventuell undervalør og overvalør.
    '''
    kanHaUndervalør = hasattr(instance.dekorasjon, 'undervalør')
    if kanHaUndervalør:
        undervalør = instance.dekorasjon.undervalør.dekorasjonInnehavelser.filter(medlem__id=instance.medlem.id).first()
        if undervalør is None:
            raise ValidationError(
                _(f'Dekorasjonen {instance.dekorasjon} krever {instance.dekorasjon.undervalør}'),
                code='undervalørMangler'
            )
        elif instance.start < undervalør.start:
            raise ValidationError(
                _(f'Dekorasjonsinnehavelsen {instance} kan ikke ha startdato før {undervalør} ({undervalør.start})'),
                code='dekorasjonInnehavelseUgyldigDato'
            )
    kanHaOvervalør = instance.dekorasjon.overvalør is not None
    if kanHaOvervalør:
        overvalør = instance.dekorasjon.overvalør.dekorasjonInnehavelser.filter(medlem__id=instance.medlem.id).first()
        if overvalør is not None and instance.start > overvalør.start:
            raise ValidationError(
                _(f'Dekorasjonsinnehavelsen {instance} kan ikke ha startdato etter {overvalør} ({overvalør.start})'),
                code='dekorasjonInnehavelseUgyldigDato'
            )


class Turne(DbCacheModel):
    navn = models.CharField(max_length=30)
    kor = models.ForeignKey(
        Kor,
        related_name='turneer',
        on_delete=models.DO_NOTHING,
        null=True
    )

    start = MyDateField(null=False)
    slutt = MyDateField(null=True, blank=True)

    beskrivelse = models.TextField(blank=True)

    medlemmer = MyManyToManyField(
        Medlem,
        related_name='turneer',
        blank=True
    )

    def get_absolute_url(self):
        return reverse('turne', args=[self.kor.navn, self.start.year, self.navn])

    @dbCache
    def __str__(self):
        if self.kor:
            return f'{self.navn}({self.kor.navn}, {self.start.year})'
        return self.navn

    class Meta:
        unique_together = ('kor', 'navn', 'start')
        ordering = ['kor', '-start', 'navn']
        verbose_name_plural = 'turneer'
    
    def clean(self, *args, **kwargs):
        validateStartSlutt(self)

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        validateM2MFieldEmpty(self, 'medlemmer')
        super().delete(*args, **kwargs)


class HendelseQuerySet(models.QuerySet):
    def genererHendelseOppmøter(self, *dates):
        'Call genererOppmøter på hendelser mellom minste og støste Date i dates. None skal tolkes som date.max'
        for hendelse in self.filter(
            qBool(True) if None in dates else Q(startDate__lte=max(dates)), 
            startDate__gte=min([d for d in dates if d != None]), 
        ):
            hendelse.genererOppmøter()


class Hendelse(DbCacheModel):
    objects = HendelseQuerySet.as_manager()

    navn = models.CharField(max_length=60)

    @property
    def prefiksArray(self):
        return self.navn[1:].split(']')[0].split() if self.navn.startswith('[') else []
    
    @property
    def navnMedPrefiks(self):
        if self.navn.startswith('['):
            return self.navn[2:].strip() if self.navn.startswith('[]') else self.navn
        
        if self.kor.navn == 'Sangern':
            return f'[Sangern] {self.navn}'
        
        if self.kategori == Hendelse.FRIVILLIG:
            return self.navn
        
        return f'[{self.get_kategori_display().upper()}] {self.navn}'

    beskrivelse = models.TextField(blank=True)
    sted = models.CharField(blank=True, max_length=50)

    kor = models.ForeignKey(
        'Kor',
        related_name='hendelser',
        on_delete=models.SET_NULL,
        null=True
    )

    # Oblig e aktiv avmelding, med fraværsføring
    # Påmelding e aktiv påmelding
    # Frivilling e uten føring av oppmøte/fravær
    # Undergruppe er for undergrupper, kommer bare i de koristene sin kalender, klassisk barvakter
    OBLIG, PÅMELDING, FRIVILLIG, UNDERGRUPPE = 'O', 'P', 'F', 'U'
    KATEGORI_CHOICES = ((OBLIG, 'Oblig'), (PÅMELDING, 'Påmelding'), (FRIVILLIG, 'Frivillig'), (UNDERGRUPPE, 'Undergruppe'))
    kategori = models.CharField(max_length=1, choices=KATEGORI_CHOICES, null=False, blank=False, default=OBLIG, help_text=toolTip('Ikke endre dette uten grunn!'))

    startDate = MyDateField(blank=False, verbose_name='Start dato', help_text=toolTip(\
        'Oppmøtene for hendelsen, altså for fraværsføring og fraværsmelding, ' + 
        'genereres av hvilke medlemmer som er aktive i koret på denne datoen, ' + 
        'og ikke har permisjon'))
    startTime = MyTimeField(blank=True, null=True, verbose_name='Start tid')

    sluttDate = MyDateField(blank=True, null=True, verbose_name='Slutt dato')
    sluttTime = MyTimeField(blank=True, null=True, verbose_name='Slutt tid')

    @property
    def start(self):
        'Start av hendelsen som datetime eller date'
        if self.startTime:
            return datetime.datetime.combine(self.startDate, self.startTime)
        return self.startDate

    @property
    def slutt(self):
        'Slutt av hendelsen som datetime, date eller None'
        if not self.sluttTime:
            return self.sluttDate
        
        if self.sluttDate:
            return datetime.datetime.combine(self.sluttDate, self.sluttTime)
        
        return datetime.datetime.combine(self.startDate, self.sluttTime)

    @property
    def varighet(self):
        return int((self.slutt - self.start).total_seconds() // 60) if self.sluttTime else None
    
    def getKalenderMedlemmer(self):
        'Omvendte av Medlem.getHendelser, returne queryset av medlemmer som skal få opp dette i kalendern sin.'
        if self.kategori == Hendelse.UNDERGRUPPE:
            return Medlem.objects.filter(oppmøter__hendelse=self)

        # Dette må vær det nøyaktig omvendte av Medlem.getHendelser, om ikkje vil vi få unødvendige updates
        return Medlem.objects.filter(# Dem som e aktiv no
            vervInnehavelseAktiv(),
            stemmegruppeVerv('vervInnehavelser__verv', includeDirr=True),
            vervInnehavelser__verv__kor__navn__in=consts.bareStorkorNavn if self.kor.navn == 'Sangern' else [self.kor.navn]
        ).filter(# Og som begynt før hendelsen her
            stemmegruppeVerv('vervInnehavelser__verv', includeDirr=True),
            vervInnehavelser__start__lte=self.startDate,
            vervInnehavelser__verv__kor__navn__in=consts.bareStorkorNavn if self.kor.navn == 'Sangern' else [self.kor.navn]
        )

    @property
    def oppmøteMedlemmer(self):
        'Dette gir deg basert på stemmegruppeverv og permisjon, hvilke medlemmer som burde ha oppmøter for hendelsen'
        if self.kategori == Hendelse.FRIVILLIG:
            return Medlem.objects.none()
        
        if self.kategori == Hendelse.UNDERGRUPPE:
            return getattr(self, '_oppmøteMedlemmer', Medlem.objects.filter( # De som er valgt til hendelsen
                Q(oppmøter__hendelse=self)
            ).distinct()) | Medlem.objects.filter( # De som er i en tilgangPrefix
                vervInnehavelseAktiv(),
                vervInnehavelser__verv__tilganger__navn__in=self.prefiksArray,
                vervInnehavelser__verv__tilganger__kor=self.kor
            ).distinct()

        return Medlem.objects.filter(# Skaff aktive korister...
            vervInnehavelseAktiv(dato=self.startDate),
            stemmegruppeVerv('vervInnehavelser__verv', includeDirr=True),
            korLookup(self.kor, 'vervInnehavelser__verv__kor'),
        ).annotatePermisjon(kor=self.kor, dato=self.startDate).filter(# ...som ikke har permisjon
            permisjon=False
        ).distinct() # distinct fordi dirigenten også kan syng i koret

    def genererOppmøter(self, oldSelf=None, softDelete=True):
        '''
        Legg til og fjerner så hendelsen har oppmøtene den skal ha. 
        Sletter ikke oppmøter som har informasjon assosiert med seg, om ikke softDelete er False.
        '''
        if not oldSelf:
            oldSelf = Hendelse.objects.filter(pk=self.pk).first()

        # Legg til oppmøter som skal være der
        for medlem in self.oppmøteMedlemmer.filter(~Q(oppmøter__hendelse=self)):
            self.oppmøter.create(medlem=medlem, hendelse=self, ankomst=self.defaultAnkomst)

        if oldSelf:
            # Slett oppmøter som ikke skal være der (og ikke har noen informasjon assosiert med seg)
            self.oppmøter.filter(
                ~Q(medlem__in=self.oppmøteMedlemmer),
                qBool(True) if not softDelete else Q(
                    fravær__isnull=True,
                    ankomst=oldSelf.defaultAnkomst,
                    melding=''
                )
            ).delete()

            # Bytt resten av oppmøtene sin ankomst til default ankomsten, dersom de ikke har en medling. 
            if self.defaultAnkomst != oldSelf.defaultAnkomst:
                for oppmøte in self.oppmøter.filter(melding=''):
                    oppmøte.ankomst = self.defaultAnkomst
                    oppmøte.save()

    def getStemmeFordeling(self):
        '''
        Returne dict med stemmefordelingen på en hendelse, der key er stemmegruppen (len=2), 
        og valuen med en liste av antall som KOMMER, KOMMER_KANSKJE og KOMMER_IKKE i den stemmegruppen. 
        '''
        stemmefordeling = {key: [0, 0, 0] for key in self.kor.stemmegrupper()}

        for oppmøte in MedlemQuerySet.annotateStemmegruppe(self.oppmøter, kor=self.kor, pkPath='medlem__pk'):
            if not oppmøte.stemmegruppe:
                # Skip dirigenten
                continue
            stemmefordeling[oppmøte.stemmegruppe][[Oppmøte.KOMMER, Oppmøte.KOMMER_KANSKJE, Oppmøte.KOMMER_IKKE].index(oppmøte.ankomst)] += 1
            
        return stemmefordeling
    
    @property
    def defaultAnkomst(self):
        if self.kategori in [Hendelse.OBLIG, Hendelse.UNDERGRUPPE]:
            return Oppmøte.KOMMER
        return Oppmøte.KOMMER_KANSKJE

    def get_absolute_url(self):
        return reverse('hendelse', args=[self.pk])

    @dbCache
    def __str__(self):
        return f'{self.navn[2:].strip() if self.navn.startswith("[]") else self.navn}({self.startDate})'

    class Meta:
        unique_together = ('kor', 'navn', 'startDate')
        ordering = ['startDate', 'startTime', 'navn', 'kor']
        verbose_name_plural = 'hendelser'

    def clean(self, *args, **kwargs):
        # Sjekk at navn har opptil et sett matchende '[' og ']' på begynnelsen
        if '[' in self.navn or ']' in self.navn:
            if not self.navn.startswith('[') or self.navn.count('[') != 1 or self.navn.count(']') != 1:
                raise ValidationError(
                    _('Firkantede parenteser i hendelse navn må være på starten, må matche hverandre, og maks et sett.'),
                    code='invalidPrefix'
                )
        
        # Validering av start og slutt
        if bool(self.startTime) != bool(self.sluttTime): # Dette er XOR
            raise ValidationError(
                _('Må ha både startTime og sluttTime eller verken'),
                code='startAndEndTime'
            )
        
        if self.sluttTime:
            validateStartSlutt(self, canEqual=False)

        if self.kor.navn == 'Sangern' and self.kategori in [Hendelse.OBLIG, Hendelse.PÅMELDING]:
            raise ValidationError(
                _('Sangern kan ikke ha obligatoriske hendelser'),
                code='sangernOblig'
            )

        # Sjekk at varigheten på en obligatorisk hendelse ikke e meir enn 12 timer
        if self.kategori == Hendelse.OBLIG and 720 < (self.varighet or 0):
            raise ValidationError(
                _('En obligatorisk hendelse kan ikke vare lengere enn 12 timer'),
                code='tooLongDuration'
            )

        # Herunder kjem validering av relaterte oppmøter, om den ikkje e lagret ennå, skip dette
        if not self.pk:
            return
        
        if self.oppmøter.filter(fravær__isnull=False).exists() and self.varighet == None:
            raise ValidationError(
                _(f'Kan ikke ha fravær på en hendelse uten varighet'),
                code='fraværUtenVarighet'
            )

        # Sjekk at hendelsen vare lenger enn det største fraværet
        if (self.varighet or 0) < (self.oppmøter.filter(fravær__isnull=False).aggregate(Max('fravær')).get('fravær__max') or 0):
            raise ValidationError(
                _(f'Å lagre dette vil føre til at noen får mere fravær enn varigheten av hendelsen.'),
                code='merFraværEnnHendelse'
            )
    
    def save(self, *args, **kwargs):
        self.clean()

        oldSelf = Hendelse.objects.filter(pk=self.pk).first()

        oldMedlemmer = [] if not oldSelf else list(oldSelf.getKalenderMedlemmer())

        super().save(*args, **kwargs)

        self.genererOppmøter(oldSelf=oldSelf)

        newMedlemmer = list(self.getKalenderMedlemmer())

        changed = not oldSelf or any([getattr(self, f) != getattr(oldSelf, f) for f in self.__dict__.keys() if not f.startswith('_')])

        if os.environ.get('GOOGLE_CALENDAR_TOKEN_PATH') and (changed or oldMedlemmer != newMedlemmer):
            # Bare oppdater Google Calendar om noko har endra seg, for å unngå API spam
            updateGoogleCalendar(self, changed=changed, oldMedlemmer=oldMedlemmer, newMedlemmer=newMedlemmer)

    def delete(self, *args, **kwargs):
        # Hendelsen sin pk blir None når den slettes, så vi må pass den videre separat her
        updateGoogleCalendar(self, oldMedlemmer=list(self.getKalenderMedlemmer()), hendelsePK=self.pk)

        super().delete(*args, **kwargs)


class Oppmøte(DbCacheModel):
    medlem = models.ForeignKey(
        Medlem,
        on_delete=models.CASCADE,
        null=False,
        related_name='oppmøter'
    )

    hendelse = models.ForeignKey(
        Hendelse,
        on_delete=models.CASCADE,
        null=False,
        related_name='oppmøter'
    )

    fravær = models.PositiveSmallIntegerField(null=True, blank=True)
    'Om fravær er None tolkes det som ikke møtt'

    GYLDIG, IKKE_BEHANDLET, UGYLDIG = True, None, False
    GYLDIG_CHOICES = ((GYLDIG, 'Gyldig'), (IKKE_BEHANDLET, 'Ikke behandlet'), (UGYLDIG, 'Ugyldig'))
    gyldig = models.BooleanField(null=True, blank=True, choices=GYLDIG_CHOICES, default=IKKE_BEHANDLET)
    'Om minuttene du hadde av fravær var gyldige'

    @property
    def minutterBorte(self):
        if self.fravær == None:
            return self.hendelse.varighet
        return self.fravær

    KOMMER, KOMMER_KANSKJE, KOMMER_IKKE = True, None, False
    ANKOMST_CHOICES = ((KOMMER, 'Kommer'), (KOMMER_KANSKJE, 'Kommer kanskje'), (KOMMER_IKKE, 'Kommer ikke'))
    ankomst = models.BooleanField(null=True, blank=True, choices=ANKOMST_CHOICES, default=KOMMER_KANSKJE)

    melding = models.TextField(blank=True)

    @property
    def fraværTekst(self):
        '''
        Brukes som lenke tekst i semesterplan, og skrives før lenker i ical eksporten. 
        Om ingenting returnes skal fraværet ikke lenkes til. 
        '''
        if self.hendelse.startDate < datetime.date.today():
            if self.hendelse.kategori == Hendelse.OBLIG and self.hendelse.varighet:
                return f'{self.minutterBorte} min {"" if self.gyldig else "u"}gyldig fravær'
        elif self.hendelse.kategori in [Hendelse.OBLIG, Hendelse.PÅMELDING]:
            if self.ankomst != self.hendelse.defaultAnkomst or self.melding != '':
                return 'Se melding'
            else:
                return 'Søk fravær' if self.hendelse.kategori == Hendelse.OBLIG else 'Meld ankomst'

    @property
    def kor(self):
        return self.hendelse.kor if self.pk else None
    
    def get_absolute_url(self):
        return reverse('meldFravær', args=[self.medlem.pk, self.hendelse.pk])

    @dbCache(affectedByCache=['hendelse', 'medlem'])
    def __str__(self):
        if self.hendelse.kategori == Hendelse.OBLIG:
            return f'Fraværssøknad {self.medlem} -> {self.hendelse}'
        elif self.hendelse.kategori == Hendelse.PÅMELDING:
            return f'Påmelding {self.medlem} -> {self.hendelse}'
        else:
            return f'Oppmøte {self.medlem} -> {self.hendelse}'

    class Meta:
        unique_together = ('medlem', 'hendelse')
        ordering = ['-hendelse', 'medlem']
        verbose_name_plural = 'oppmøter'

    def clean(self, *args, **kwargs):
        # Valider mengden fravær
        if self.fravær != None and self.hendelse.varighet == None:
            raise ValidationError(
                _(f'Kan ikke ha fravær på en hendelse uten varighet'),
                code='fraværUtenVarighet'
            )
        
        if self.fravær and self.fravær > (self.hendelse.varighet or 0):
            raise ValidationError(
                _('Kan ikke ha mere fravær enn varigheten av hendelsen.'),
                code='merFraværEnnHendelse'
            )

    def save(self, *args, **kwargs):
        self.clean()

        oldSelf = Oppmøte.objects.filter(pk=self.pk).first()

        if oldSelf:
            # Dersom melding har endret seg, og gyldig er UGYLDIG, endre gyldig til IKKE_BEHANDLET.
            if self.gyldig == Oppmøte.UGYLDIG and oldSelf.melding != self.melding:
                self.gyldig = Oppmøte.IKKE_BEHANDLET

            # Dersom de har en epost, og en gyldig endres til GYLDIG eller UGYLDIG, skyt de en epost
            if self.medlem.epost and self.medlem.innstillinger.get('epost', 0) & 2**0 == 0 \
                and self.hendelse.kategori == Hendelse.OBLIG and self.gyldig != Oppmøte.IKKE_BEHANDLET and self.gyldig != oldSelf.gyldig:
                mail.send_mail(
                    subject=f'Fraværssøknad besvart for {self.hendelse}',
                    message=f'Markert som: {"Gyldig" if self.gyldig else "Ugyldig"} fravær\nLenke: {"http://" + mytxsSettings.ALLOWED_HOSTS[0] + self.get_absolute_url()}\nMelding:\n{self.melding}',
                    from_email=None,
                    recipient_list=[self.medlem.epost]
                )
        
        super().save(*args, **kwargs)


class Lenke(DbCacheModel):
    navn = models.CharField(max_length=255)
    lenke = models.CharField(max_length=255)
    synlig = models.BooleanField(default=False, help_text=toolTip('Om denne lenken skal være synlig på MyTXS'))
    redirect = models.BooleanField(default=False, help_text=toolTip('Om denne lenken skal kunne redirectes til'))

    @property
    def redirectUrl(self):
        if self.pk and self.redirect:
            return 'http://' + mytxsSettings.ALLOWED_HOSTS[0] + reverse('lenkeRedirect', args=[self.kor.navn, self.navn])

    kor = models.ForeignKey(
        'Kor',
        related_name='lenker',
        on_delete=models.SET_NULL,
        null=True
    )

    @dbCache
    def __str__(self):
        return f'{self.navn}({self.kor})'
    
    class Meta:
        unique_together = ('kor', 'navn', 'lenke')
        ordering = ['kor', 'navn', '-pk']
        verbose_name_plural = 'lenker'
