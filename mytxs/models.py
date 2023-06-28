import datetime
from functools import cached_property
import os
import json
from urllib.parse import unquote

from django.apps import apps
from django.conf import settings
from django.db import models
from django.db.models import Value as V, Q, Case, When, Min
from django.db.models.functions import Concat
from django.forms import ValidationError
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.utils.safestring import mark_safe

from mytxs.fields import MyDateField, MyManyToManyField, MyTimeField
from mytxs.settings import ALLOWED_HOSTS
from mytxs.utils.modelUtils import groupBy, orderStemmegruppeVerv, toolTip, vervInnehavelseAktiv, stemmegruppeVerv


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

    instancePK = models.PositiveIntegerField(
        null=False
    )

    value = models.JSONField(null=False)
    'Se to_dict i mytxs/signals/logSignals.py'

    strRep = models.CharField(null=False, max_length=100)
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
        ordering = ['-timeStamp']
        verbose_name_plural = 'logger'


class LoggM2M(models.Model):
    timeStamp = models.DateTimeField(auto_now_add=True)

    m2mName = models.CharField(
        max_length=50
    )
    'A string containing the m2m source model name and the m2m field name separated by an underscore'

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
        ordering = ['-timeStamp']


class MedlemQuerySet(models.QuerySet):
    def annotateFulltNavn(self):
        'Annotate feltet "fulltNavn" med deres navn med korrekt mellomrom, viktig for søk på medlemmer'
        return self.annotate(
            fulltNavn=Case(
                When(
                    mellomnavn='',
                    then=Concat('fornavn', V(' '), 'etternavn')
                ),
                default=Concat('fornavn', V(' '), 'mellomnavn', V(' '), 'etternavn')
            )
        )

    def annotateKarantenekor(self, kor=None):
        'Annotate feltet "K" med int året de startet i sitt storkor'
        kVerv = Verv.objects.filter(stemmegruppeVerv('vervInnehavelse__verv') | Q(vervInnehavelse__verv__navn='dirigent'))
        if kor:
            kVerv = kVerv.filter(kor=kor)
        return self.annotate(
            K=Min(
                'vervInnehavelse__start__year', 
                filter=Q(vervInnehavelse__verv__in=kVerv)
            )
        )

    def filterIkkePermitert(self, kor, dato=None):
        'Returne et queryset av (medlemmer som er aktive) and (ikke permiterte)'
        if dato == None:
            dato = datetime.datetime.today()

        permiterte = self.filter(
            vervInnehavelseAktiv(dato=dato),
            Q(vervInnehavelse__verv__navn='permisjon'),
            Q(vervInnehavelse__verv__kor=kor)
        ).values_list('pk', flat=True)

        return self.filter(# Skaff aktive korister...
            vervInnehavelseAktiv(dato=dato),
            stemmegruppeVerv('vervInnehavelse__verv'),
            vervInnehavelse__verv__kor=kor
        ).exclude(# ...som ikke har permisjon
            pk__in=permiterte
        )

class Medlem(models.Model):
    objects = MedlemQuerySet.as_manager()
    
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
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


    # Følgende fields er bundet av GDPR, vi må ha godkjennelse fra medlemmet for å lagre de. 
    fødselsdato = MyDateField(null=True, blank=True)
    epost = models.EmailField(max_length=100, blank=True)
    tlf = models.CharField(max_length=20, default='', blank=True)
    studieEllerJobb = models.CharField(max_length=100, blank=True)
    boAdresse = models.CharField(max_length=100, blank=True)
    foreldreAdresse = models.CharField(max_length=100, blank=True)

    def generateUploadTo(instance, fileName):
        path = 'sjekkhefteBilder/'
        format = f'{instance.pk}.{fileName.split(".")[-1]}'
        fullPath = os.path.join(path, format)
        return fullPath

    bilde = models.ImageField(upload_to=generateUploadTo, null=True, blank=True)

    @property
    def kor(self):
        'Returne kor medlemmet er aktiv i'
        return Kor.objects.filter(
            stemmegruppeVerv(),
            vervInnehavelseAktiv('verv__vervInnehavelse'),
            verv__vervInnehavelse__medlem=self
        )

    @cached_property
    def firstStemmegruppeVervInnehavelse(self):
        'Returne første stemmegruppeverv de hadde i et storkor'
        return self.vervInnehavelse.filter(
            stemmegruppeVerv(),
            verv__kor__kortTittel__in=['TSS', 'TKS']
        ).order_by('start').first()
    
    @property
    def storkor(self):
        'Returne koran TSS eller TKS eller en tom streng'
        if self.firstStemmegruppeVervInnehavelse:
            return self.firstStemmegruppeVervInnehavelse.verv.kor
        return ''

    @property
    def karantenekor(self):
        'Returne K{to sifret år av første storkor stemmegruppeverv}, eller 4 dersom det e før år 2000'
        if self.firstStemmegruppeVervInnehavelse:
            if self.firstStemmegruppeVervInnehavelse.start.year >= 2000:
                return f'K{self.firstStemmegruppeVervInnehavelse.start.strftime("%y")}'
            else:
                return f'K{self.firstStemmegruppeVervInnehavelse.start.strftime("%Y")}'
        else:
            return ''

    @cached_property
    def tilganger(self):
        'Returne aktive tilganger'
        return Tilgang.objects.filter(vervInnehavelseAktiv('verv__vervInnehavelse'), verv__vervInnehavelse__medlem=self).distinct()
    
    @cached_property
    def navBarTilgang(self):
        sider = set()
        tilganger = self.tilganger
        if self.tilganger.filter(navn='medlemsdata').exists():
            sider.add('medlemListe')
            sider.add('loggListe')

        if self.tilganger.filter(navn='semesterplan').exists():
            sider.add('hendelseListe')
            sider.add('loggListe')

        if self.tilganger.filter(navn='fravær').exists():
            sider.add('hendelseListe')
            sider.add('loggListe')

        if self.tilganger.filter(navn='vervInnehavelse').exists():
            sider.add('medlemListe')
            sider.add('vervListe')
            sider.add('loggListe')

        if self.tilganger.filter(navn='dekorasjonInnehavelse').exists():
            sider.add('medlemListe')
            sider.add('dekorasjonListe')
            sider.add('loggListe')

        if self.tilganger.filter(navn='verv').exists():
            sider.add('vervListe')
            sider.add('loggListe')

        if self.tilganger.filter(navn='dekorasjon').exists():
            sider.add('dekorasjonListe')
            sider.add('loggListe')

        if self.tilganger.filter(navn='tilgang').exists():
            sider.add('vervListe')
            sider.add('tilgangListe')
            sider.add('loggListe')

        if self.tilganger.filter(navn='logg').exists():
            sider.add('loggListe')

        return list(sider)

    def harSideTilgang(self, instance):
        'Returne en boolean som sie om man kan redigere noe på denne instansens side'
        return self.tilgangQueryset(type(instance), extended=False).filter(pk=instance.pk).exists()

    def tilgangQueryset(self, model, extended=False):
        '''
        Returne queryset av objekt der vi har tilgang til noe på den tilsvarende siden og 
        sansynligvis vil gjøre noe med (samme kor som grunnen til at man har tilgang til det).
        Med extended=True returne den absolutt alle objekt hvis sider brukeren kan redigere noe. 
        Dette slår altså sammen logikken for 
        1. Hva som kommer opp i lister
        2. Hvilke instans-sider man har tilgang til
        3. Hvilke alternativ som dukker opp i dropdown menyer
        4. Hvilke logger man har tilgang til
        '''

        if model == Medlem: # For Medlem siden
            medlemmer = Medlem.objects.distinct().filter(pk=self.pk)
            if self.tilganger.filter(navn='medlemsdata').exists():
                # Uavhengig av extended, ha inn folk fra det koret, og folk uten kor
                medlemmer |= Medlem.objects.distinct().filter(
                    stemmegruppeVerv('vervInnehavelse__verv'), 
                    Q(vervInnehavelse__verv__kor__tilganger__in=self.tilganger.filter(navn='medlemsdata'))
                )

                medlemmer |= Medlem.objects.distinct().exclude(
                    stemmegruppeVerv('vervInnehavelse__verv')
                )

            if self.tilganger.filter(navn='vervInnehavelse').exists():
                # if extended:
                #     # Om extended, ha med alle potensielle vervInnehavere
                #     return Medlem.objects.distinct()
                # else:
                #     # Om ikke, bare ha med aktive i det samme koret som tilgangen, og folk uten kor
                #     medlemmer |= Medlem.objects.distinct().filter(
                #         stemmegruppeVerv('vervInnehavelse__verv'),
                #         Q(vervInnehavelse__verv__kor__tilganger__in=self.tilganger.filter(navn='vervInnehavelse'))
                #     )

                #     medlemmer |= Medlem.objects.distinct().exclude(
                #         stemmegruppeVerv('vervInnehavelse__verv')
                #     )

                return Medlem.objects.distinct()

            if self.tilganger.filter(navn='dekorasjonInnehavelse').exists():
                # if extended:
                #     # Om extended, ha med alle potensielle vervInnehavere
                #     return Medlem.objects.distinct()
                # else:
                #     # Om ikke, bare ha med aktive i det samme koret som tilgangen, og folk uten kor
                #     medlemmer |= Medlem.objects.distinct().filter(
                #         stemmegruppeVerv('vervInnehavelse__verv'),
                #         Q(vervInnehavelse__verv__kor__tilganger__in=self.tilganger.filter(navn='dekorasjonInnehavelse'))
                #     )

                #     medlemmer |= Medlem.objects.distinct().exclude(
                #         stemmegruppeVerv('vervInnehavelse__verv')
                #     )

                return Medlem.objects.distinct()

            return medlemmer
        
        if model == Verv: # For Verv siden
            if extended and self.tilganger.filter(navn='tilgang').exists():
                # Man kan sette en tilgang på alle verv
                return Verv.objects.all()
            else:
                # Forøverig, send vervene som er samme kor som grunnen til at du ser siden her. 
                return Verv.objects.filter(
                    kor__tilganger__in=self.tilganger.filter(
                        Q(navn='verv') | Q(navn='vervInnehavelse') | Q(navn='tilgang')
                    )
                ).distinct()
            
        if model == Dekorasjon: # For Dekorasjon siden
            return Dekorasjon.objects.filter(
                kor__tilganger__in=self.tilganger.filter(
                    Q(navn='dekorasjon') | Q(navn='dekorasjonInnehavelse')
                )
            ).distinct()
            
        if model == Tilgang: # For Tilgang siden
            return Tilgang.objects.filter(
                kor__tilganger__in=self.tilganger.filter(navn='tilgang')
            ).distinct()
        
        if model == Hendelse:
            return Hendelse.objects.filter(
                Q(kor__tilganger__in=self.tilganger.filter(navn='semesterplan')) |
                Q(kor__tilganger__in=self.tilganger.filter(navn='fravær'))
            ).distinct()
        
        if model == Oppmøte:
            return Oppmøte.objects.filter(
                hendelse__kor__tilganger__in=self.tilganger.filter(navn='fravær')
            ).distinct()

        if model == Logg:
            loggs = Logg.objects.distinct().none()

            # Tanken her er at om man har noen av tilgangen til høyre får man tilgang til loggs for 
            # den modellen, dersom tilgangen er i samme kor som loggen, eller loggen ikke har et kor. 
            modelOgTilgang = {
                VervInnehavelse: ['vervInnehavelse'],
                Verv: ['verv', 'vervInnehavelse', 'tilgang'], 
                DekorasjonInnehavelse: ['dekorasjonInnehavelse'],
                Dekorasjon: ['dekorasjon', 'dekorasjonInnehavelse'],
                Medlem: ['medlemsdata', 'vervInnehavelse', 'dekorasjonInnehavelse'],
                Tilgang: ['tilgang', 'verv'],
                Hendelse: ['semesterplan', 'fravær'],
                Oppmøte: ['semesterplan', 'fravær'],
                Lenke: ['lenke']
            }

            for model, tilgangNavn in modelOgTilgang.items():
                if self.tilganger.filter(navn__in=tilgangNavn).exists():
                    loggs |= Logg.objects.filter(
                        Q(kor__tilganger__in=self.tilganger.filter(navn__in=tilgangNavn)) | Q(kor__isnull=True), 
                        model=model.__name__
                    ).distinct()
            
            return loggs

    def get_absolute_url(self):
        return reverse('medlem', args=[self.pk])
    
    def __str__(self):
        strRep = self.navn
        if storkor := self.storkor:
            strRep += f' {storkor} {self.karantenekor}'
        return strRep

    class Meta:
        ordering = ['fornavn', 'mellomnavn', 'etternavn']
        verbose_name_plural = 'medlemmer'


class KorQuerySet(models.QuerySet):
    def korForInstance(self, instance):
        '''
        Returne det tilsvarende koret for instancen, eller None om det ikkje har et kor, 
        brukes i signals/logSignals.py
        '''
        if type(instance) == Medlem:
            return instance.storkor or None
        elif type(instance) == VervInnehavelse:
            return instance.verv.kor
        elif type(instance) == DekorasjonInnehavelse:
            return instance.dekorasjon.kor
        elif type(instance) == Oppmøte:
            return instance.hendelse.kor
        else:
            return instance.kor

class Kor(models.Model):
    objects = KorQuerySet.as_manager()
    kortTittel = models.CharField(max_length=10)
    langTittel = models.CharField(max_length=50)

    def __str__(self):
        return self.kortTittel
    
    class Meta:
        verbose_name_plural = 'kor'


class Tilgang(models.Model):
    navn = models.CharField(max_length=50)

    kor = models.ForeignKey(
        Kor,
        related_name='tilganger',
        on_delete=models.DO_NOTHING,
        null=True
    )

    beskrivelse = models.CharField(
        max_length=200, 
        default='',
        blank=True
    )

    bruktIKode = models.BooleanField(
        default=False, 
        help_text=toolTip('Hvorvidt tilgangen er brukt i kode og følgelig ikke kan endres på av brukere.')
    )

    sjekkheftetSynlig = models.BooleanField(
        default=False,
        help_text=toolTip('Om de som har denne tilgangen skal vises som en gruppe i sjekkheftet.')
    )

    @property
    def tittel(self):
        return self.__str__()
    
    def get_absolute_url(self):
        return reverse('tilgang', args=[self.kor.kortTittel, self.navn])

    def __str__(self):
        if self.kor:
            return f'{self.kor.kortTittel}-{self.navn}'
        return self.navn

    class Meta:
        ordering = ['kor', 'navn']
        unique_together = ('kor', 'navn')
        verbose_name_plural = 'tilganger'

    def clean(self, *args, **kwargs):
        if Tilgang.objects.filter(bruktIKode=True, navn=self.navn).exists():
            raise ValidationError(
                _('Kan ikke opprette eller endre navn til noe som er brukt i kode'),
                code='bruktIKodeError',
            )


class Verv(models.Model):
    navn = models.CharField(max_length=50)

    tilganger = MyManyToManyField(
        Tilgang,
        related_name='verv',
        blank=True
    )

    kor = models.ForeignKey(
        Kor,
        related_name='verv',
        on_delete=models.DO_NOTHING,
        null=True
    )

    bruktIKode = models.BooleanField(
        default=False, 
        help_text=toolTip('Hvorvidt vervet er brukt i kode og følgelig ikke kan endres på av brukere.')
    )

    @property
    def stemmegruppeVerv(self):
        return Verv.objects.filter(stemmegruppeVerv(''), pk=self.pk).exists()

    def get_absolute_url(self):
        return reverse('verv', args=[self.kor.kortTittel, self.navn])

    def __str__(self):
        return f'{self.navn}({self.kor.__str__()})'
    
    class Meta:
        unique_together = ('navn', 'kor')
        ordering = ['kor', orderStemmegruppeVerv(), 'navn']
        verbose_name_plural = 'verv'

    def clean(self, *args, **kwargs):
        if Verv.objects.filter(bruktIKode=True, navn=self.navn).exists():
            raise ValidationError(
                _('Kan ikke opprette eller endre navn til noe som er brukt i kode'),
                code='bruktIKodeError',
            )
    


class VervInnehavelse(models.Model):
    medlem = models.ForeignKey(
        Medlem,
        on_delete=models.PROTECT,
        null=False,
        related_name='vervInnehavelse'
    )
    verv = models.ForeignKey(
        Verv,
        on_delete=models.PROTECT,
        null=False,
        related_name='vervInnehavelse'
    )
    start = MyDateField(blank=False)
    slutt = MyDateField(blank=True, null=True)
    
    @property
    def aktiv(self):
        return VervInnehavelse.objects.filter(vervInnehavelseAktiv(''), pk=self.pk).exists()
    
    def __str__(self):
        return f'{self.medlem.__str__()} -> {self.verv.__str__()}'
    
    class Meta:
        unique_together = ('medlem', 'verv', 'start')
        ordering = ['-start']
        verbose_name_plural = 'vervinnehavelser'

    def clean(self, *args, **kwargs):
        if self.slutt is not None and self.start > self.slutt:
            raise ValidationError(
                _('Ugyldig start slutt rekkefølge.'),
                code='invalidDateOrder',
            )
    
    def save(self, *args, **kwargs):
        oldSelf = VervInnehavelse.objects.filter(pk=self.pk).first()

        super().save(*args, **kwargs)

        # Oppdater hvilke oppmøter man har basert på stemmegruppeVerv og permisjon

        # Per no ser e ikkje en ryddigar måte å gjør dette på, enn å bare prøv å minimer antall 
        # hendelser vi calle save metoden på. Det e vanskelig å skaff hvilke hendelser 
        # som blir lagt til og fjernet av en endring av varighet eller type av verv. Sammenlign
        # - "Medlemmer som har aktive stemmegruppeverv som ikke har permisjon den dagen."
        # - "Hendelsene som faller på dager der vi har endret et permisjon/stemmegruppeverv, 
        # eller dager vi ikke har endret dersom vi endrer typen verv."
        if self.verv.stemmegruppeVerv or self.verv.navn == 'permisjon' or \
            (oldSelf and (oldSelf.verv.stemmegruppeVerv or oldSelf.verv.navn == 'permisjon')):

            hendelser = Hendelse.objects.filter(kor=self.verv.kor)
            
            if not oldSelf:
                # Om ny vervInnehavelse, save på alle hendelser i varigheten
                hendelser.saveAllInPeriod(self.start, self.slutt)

            elif self.verv.stemmegruppeVerv != oldSelf.verv.stemmegruppeVerv or \
                self.verv.navn == 'permisjon' != oldSelf.verv.navn == 'permisjon':
                # Om vi bytte hvilken type verv det er, save alle hendelser i hele perioden
                hendelser.saveAllInPeriod(self.start, self.slutt, oldSelf.start, oldSelf.slutt)

            elif (self.verv.stemmegruppeVerv and oldSelf.verv.stemmegruppeVerv) or \
                (self.verv.navn == 'permisjon' and oldSelf.verv.navn == 'permisjon'):
                # Om vi ikke bytte hvilken type verv det er, save hendelser som er 
                # mellom start og start, og mellom slutt og slutt

                if oldSelf.start != self.start:
                    # Start av verv er aldri None
                    hendelser.saveAllInPeriod(self.start, oldSelf.start)

                if oldSelf.slutt != self.slutt:
                    if oldSelf.slutt != None and self.slutt != None:
                        # Om verken e None, lagre som vanlig
                        hendelser.saveAllInPeriod(self.slutt, oldSelf.slutt)
                    else:
                        hendelser.saveAllInPeriod(self.slutt, oldSelf.slutt)
    
    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)

        # Om vi sletter vervInnehavelsen, save alle i varigheten
        if self.verv.stemmegruppeVerv or self.verv.navn == 'permisjon':
            Hendelse.objects.filter(kor=self.verv.kor).saveAllInPeriod(self.start, self.slutt)


class Dekorasjon(models.Model):
    navn = models.CharField(max_length=30)
    kor = models.ForeignKey(
        Kor,
        related_name='dekorasjoner',
        on_delete=models.DO_NOTHING,
        null=True
    )

    def get_absolute_url(self):
        return reverse('dekorasjon', args=[self.kor.kortTittel, self.navn])

    def __str__(self):
        return f'{self.navn}({self.kor.__str__()})'
    
    class Meta:
        unique_together = ('navn', 'kor')
        ordering = ['kor', 'navn']
        verbose_name_plural = 'dekorasjoner'


class DekorasjonInnehavelse(models.Model):
    medlem = models.ForeignKey(
        Medlem,
        on_delete=models.PROTECT,
        null=False,
        related_name='dekorasjonInnehavelse'
    )
    dekorasjon = models.ForeignKey(
        Dekorasjon,
        on_delete=models.PROTECT,
        null=False,
        related_name='dekorasjonInnehavelse'
    )
    start = MyDateField(null=False)
    
    def __str__(self):
        return f'{self.medlem.__str__()} -> {self.dekorasjon.__str__()}'
    
    class Meta:
        unique_together = ('medlem', 'dekorasjon', 'start')
        ordering = ['-start']
        verbose_name_plural = 'dekorasjoninnehavelser'


class HendelseQuerySet(models.QuerySet):
    def generateICal(self):
        'Returne en (forhåpentligvis) rfc5545 kompatibel string'
        iCalString= f'''\
BEGIN:VCALENDAR
PRODID:-//mytxs.samfundet.no//MyTXS semesterplan//
VERSION:2.0
CALSCALE:GREGORIAN
METHOD:PUBLISH
X-WR-CALNAME:MyTXS 2.0 semesterplan
X-WR-CALDESC:Denne kalenderen ble generert av MyTXS {
datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S')}Z
X-WR-TIMEZONE:Europe/Oslo
BEGIN:VTIMEZONE
TZID:Europe/Oslo
X-LIC-LOCATION:Europe/Oslo
BEGIN:DAYLIGHT
TZOFFSETFROM:+0100
TZOFFSETTO:+0200
TZNAME:CEST
DTSTART:19700329T020000
RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU
END:DAYLIGHT
BEGIN:STANDARD
TZOFFSETFROM:+0200
TZOFFSETTO:+0100
TZNAME:CET
DTSTART:19701025T030000
RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU
END:STANDARD
END:VTIMEZONE
{''.join(map(lambda h: h.getVevent(), self))}END:VCALENDAR\n'''

        # Split lines som e lenger enn 75 characters over fleir linja
        iCalLines = iCalString.split('\n')
        l = 0
        while l < len(iCalLines):
            if len(iCalLines[l]) > 75:
                iCalLines.insert(l+1, ' ' + iCalLines[l][75:])
                iCalLines[l] = iCalLines[l][:75]
            l += 1
        iCalString = '\n'.join(iCalLines)

        # Erstatt alle newlines med CRLF
        iCalString = iCalString.replace('\n', '\r\n')

        return iCalString
    
    def saveAllInPeriod(self, *dates):
        '''
        Utility method for å gjøre koden for lagring av vervInnehavelser enklere,
        dates argumentet kan inneholde datoer eller None, i hvilken som helst rekkefølge.
        '''

        if len(dates) > 0:
            if None in dates:
                datesWithoutNone = [*filter(lambda d: d != None, dates)]
                hendelser = self.filter(startDate__gte=min(datesWithoutNone))
            else:
                hendelser = self.filter(startDate__gte=min(dates), startDate__lte=max(dates))
            for hendelse in hendelser:
                hendelse.save()


class Hendelse(models.Model):
    objects = HendelseQuerySet.as_manager()

    navn = models.CharField(max_length=60)
    beskrivelse = models.CharField(blank=True, max_length=150)
    sted = models.CharField(blank=True, max_length=50)

    kor = models.ForeignKey(
        'Kor',
        related_name='events',
        on_delete=models.SET_NULL,
        null=True
    )

    # Oblig e aktiv avmelding
    # Påmelding e aktiv påmelding
    # Frivilling e uten føring av oppmøte/fravær
    OBLIG, PÅMELDING, FRIVILLIG = 'O', 'P', 'F'
    KATEGORI_CHOICES = ((OBLIG, 'Oblig'), (PÅMELDING, 'Påmelding'), (FRIVILLIG, 'Frivillig'))
    kategori = models.CharField(max_length=1, choices=KATEGORI_CHOICES, null=False)

    startDate = MyDateField(blank=False)
    startTime = MyTimeField(blank=True, null=True)

    sluttDate = MyDateField(blank=True, null=True)
    sluttTime = MyTimeField(blank=True, null=True)

    @property
    def start(self):
        'Start av hendelsen som datetime eller date'
        if self.startTime:
            return datetime.datetime.combine(self.startDate, self.startTime)
        return self.startDate

    @property
    def slutt(self):
        'Slutt av hendelsen som datetime, date eller None'
        if self.sluttTime:
            return datetime.datetime.combine(self.sluttDate, self.sluttTime)
        return self.sluttDate

    @property
    def varighet(self):
        return (self.slutt - self.start).total_seconds() / 60 if self.sluttTime else None

    def getVeventStart(self):
        if self.startTime:
            return self.start.strftime('%Y%m%dT%H%M%S')
        return self.start.strftime('%Y%m%d')

    def getVeventSlutt(self):
        if self.sluttTime:
            return self.slutt.strftime('%Y%m%dT%H%M%S')
        if self.sluttDate:
            # I utgangspunktet er slutt tiden (hovedsakling tidspunktet) ekskludert i ical formatet, 
            # men følgelig om det er en sluttdato (uten tid), vil det vises som en dag for lite
            # i kalenderapplikasjonene. Derfor hive vi på en dag her, så det vises rett:)
            return (self.slutt + datetime.timedelta(days=1)).strftime('%Y%m%d')
        return None

    @property
    def UID(self):
        return f'{self.kor}-{self.pk}@mytxs.samfundet.no'
    
    def getOppmøteLink(self):
        if self.kategori != Hendelse.FRIVILLIG:
            return ALLOWED_HOSTS[0] + unquote(reverse('meldFravær', args=[self.pk]))

    def getVevent(self):
        vevent =  'BEGIN:VEVENT\n'
        vevent += f'UID:{self.UID}\n'

        if self.kategori == Hendelse.OBLIG:
            vevent += f'SUMMARY:[OBLIG]: {self.navn}\n'
        elif self.kategori == Hendelse.PÅMELDING:
            vevent += f'SUMMARY:[PÅMELDING]: {self.navn}\n'
        else:
            vevent += f'SUMMARY:{self.navn}\n'

        vevent += f'DESCRIPTION:{self.beskrivelse}'
        if self.kategori != Hendelse.FRIVILLIG:
            if self.beskrivelse:
                vevent += '\\n\\n'
            vevent += self.getOppmøteLink()
        vevent += '\n'

        vevent += f'LOCATION:{self.sted}\n'

        if self.startTime:
            vevent += f'DTSTART;TZID=Europe/Oslo:{self.getVeventStart()}\n'
        else:
            vevent += f'DTSTART;VALUE=DATE:{self.getVeventStart()}\n'

        if slutt := self.getVeventSlutt():
            if self.sluttTime:
                vevent += f'DTEND;TZID=Europe/Oslo:{slutt}\n'
            else:
                vevent += f'DTEND;VALUE=DATE:{slutt}\n'
        
        vevent += f'DTSTAMP:{datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S")}Z\n'
        vevent += 'END:VEVENT\n'
        return vevent
    
    def getMedlemmer(self):
        return Medlem.objects.filterIkkePermitert(kor=self.kor, dato=self.startDate)

    def getStemmeFordeling(self):
        stemmefordeling = {}
        for oppmøte in self.oppmøter.filter():
            if oppmøte.ankomst != Oppmøte.KOMMER:
                continue
            stemmegruppe = Verv.objects.filter(
                vervInnehavelseAktiv(dato=self.startDate),
                stemmegruppeVerv(''),
                vervInnehavelse__medlem=oppmøte.medlem,
                kor=self.kor,
            ).first().navn[-2:]
            if stemmegruppe not in stemmefordeling.keys():
                stemmefordeling[stemmegruppe] = 1
            else:
                stemmefordeling[stemmegruppe] += 1
        return stemmefordeling
    
    def get_absolute_url(self):
        return reverse('hendelse', args=[self.pk])

    def __str__(self):
        return f'{self.navn}({self.startDate})'

    class Meta:
        ordering = ['startDate', 'startTime']

    def clean(self, *args, **kwargs):
        # Validering av start og slutt
        if not self.sluttDate:
            if self.sluttTime:
                raise ValidationError(
                    _('Kan ikke ha sluttTime uten sluttDate'),
                    code='timeWithoutDate'
                )
        else:
            if bool(self.startTime) != bool(self.sluttTime): # Dette er XOR
                raise ValidationError(
                    _('Må ha både startTime og sluttTime eller verken'),
                    code='startAndEndTime'
                )
            
            if self.start >= self.slutt:
                raise ValidationError(
                    _('Slutt må være etter start'),
                    code='invalidDateOrder'
                )
        
        # Validering av relaterte oppmøter
        if self.pk and (oppmøter := self.oppmøter.filter(
            ~Q(medlem__in=self.getMedlemmer()),
            Q(fravær__isnull=False) | ~Q(melding='')
        )):
            raise ValidationError(
                _(f'Å flytte hendelsen til dette tidspunktet kommer til å slette oppmøtene til {", ".join(map(lambda o: str(o.medlem), oppmøter))}' +
                   ', slett disse oppmøtene manuelt først.'),
                code='saveWouldDeleteRelated'
            )
        
        if self.pk and len(fraværListe := [*filter(lambda o: o, self.oppmøter.values_list('fravær', flat=True))]) > 0 and \
            self.varighet < max(fraværListe):
            raise ValidationError(
                _(f'Å lagre dette vil føre til at noen får mere fravær enn varigheten av hendelsen.'),
                code='merFraværEnnHendelse'
            )

    def save(self, *args, **kwargs):
        # Fiksing av relaterte oppmøter
        super().save(*args, **kwargs)

        medlemmer = self.getMedlemmer()
        
        # Slett oppmøter som ikke skal være der
        self.oppmøter.filter(~Q(medlem__in=medlemmer)).delete()

        # Legg til oppmøter som skal være der
        for medlem in medlemmer.filter(~Q(oppmøter__hendelse=self)):
            self.oppmøter.create(medlem=medlem, hendelse=self)


class Oppmøte(models.Model):
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
    'Om det er None tolkes det som ikke møtt'

    @property
    def minutterBorte(self):
        if self.fravær == None:
            return self.hendelse.varighet
        return self.fravær

    KOMMER, KOMMER_KANSKJE, KOMMER_IKKE = 1, 0, -1
    ANKOMST_CHOICES = ((KOMMER, 'Kommer'), (KOMMER_KANSKJE, 'Kommer kanskje'), (KOMMER_IKKE, 'Kommer ikke'))
    ankomst = models.IntegerField(choices=ANKOMST_CHOICES, null=False, default=KOMMER_KANSKJE)

    melding = models.TextField(blank=True)

    gyldig = models.BooleanField(default=False)
    'Om minuttene du hadde av fravær var gyldige'

    def __str__(self):
        if self.hendelse.kategori == Hendelse.OBLIG:
            return f'Fraværssøknad {self.medlem} -> {self.hendelse}'
        elif self.hendelse.kategori == Hendelse.PÅMELDING:
            return f'Påmelding {self.medlem} -> {self.hendelse}'
        else:
            return f'Oppmøte {self.medlem} -> {self.hendelse}'

    class Meta:
        ordering = ['-ankomst']
        unique_together = ('medlem', 'hendelse')

    def clean(self, *args, **kwargs):
        # Valider mengden fravær
        if self.fravær and self.fravær > self.hendelse.varighet:
            raise ValidationError(
                _('Kan ikke ha mere fravær enn varigheten av hendelsen.'),
                code='merFraværEnnHendelse'
            )
    
    def save(self, *args, **kwargs):
        # Sett et nytt oppmøte sin ankomst til KOMMER dersom hendelsen e OBLIG
        if not Oppmøte.objects.filter(pk=self.pk).exists() and self.hendelse.kategori == Hendelse.OBLIG:
            self.ankomst = Oppmøte.KOMMER
        
        super().save(*args, **kwargs)

class Lenke(models.Model):
    navn = models.CharField(max_length=255)
    lenke = models.CharField(max_length=255)

    kor = models.ForeignKey(
        'Kor',
        related_name='lenker',
        on_delete=models.SET_NULL,
        null=True
    )

    def __str__(self):
        return f'{self.navn}({self.kor})'
    
    class Meta:
        ordering = ['kor']
