from functools import cached_property
import os
import json

from django.apps import apps
from django.conf import settings
from django.db import models
from django.db.models import Value as V, Q, F, Case, When, Min
from django.db.models.functions import Concat
from django.forms import ValidationError
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from mytxs.fields import MyDateField, MyManyToManyField
from mytxs.utils.modelUtils import groupBy, orderStemmegruppeVerv, toolTip, vervInnehavelseAktiv, stemmegruppeVerv

class LoggQueryset(models.QuerySet):
    def getLoggFor(self, instance):
        'Gets the logg corresponding to the instance'
        if logg := self.getLoggForModelPK(type(instance), instance.pk):
            return logg

    def getLoggLinkFor(self, instance):
        'get_absolute_url for the logg correpsonding to the instance'
        if logg := self.getLoggFor(instance):
            return logg.get_absolute_url()
        
    def getLoggForModelPK(self, model, pk):
        'Gets a logg given a model (which may be a string or an actual model) and a pk'
        if type(model) == str:
            model = apps.get_model('mytxs', model)
        if logg := Logg.objects.filter(model=model.__name__, instancePK=pk).order_by('-timeStamp').first():
            return logg


class Logg(models.Model):
    objects = LoggQueryset.as_manager()
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
        ''' Returne oversiktlig json representasjon av objektet, med <a> lenker
            satt inn der det e foreign keys til andre Logg objekt, slik at dette
            fint kan settes inn i en <pre> tag.'''
        jsonRepresentation = json.dumps(self.value, indent=4)

        foreignKeyFields = list(filter(lambda field: isinstance(field, models.ForeignKey), self.getModel()._meta.get_fields()))

        lines = jsonRepresentation.split('\n')

        def getLineKey(line):
            return line.split(":")[0].strip().replace('"', '')

        for l in range(len(lines)):
            for foreignKeyField in foreignKeyFields:
                if foreignKeyField.name == getLineKey(lines[l]) and type(self.value[foreignKeyField.name]) == int:
                    relatedLogg = Logg.objects.filter(pk=self.value[foreignKeyField.name]).first()

                    lines[l] = lines[l].replace(f'{self.value[foreignKeyField.name]}', 
                        f'<a href={relatedLogg.get_absolute_url()}>{relatedLogg.strRep}</a>')

        jsonRepresentation = '\n'.join(lines)

        return jsonRepresentation

    def getReverseRelated(self):
        "Returne en liste av logger som referere (via 1:1 eller n:1) til denne loggen"
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
        "Skaffe alle m2m logger for denne loggen"
        return groupBy(self.forwardM2Ms.all() | self.backwardM2Ms.all(), 'm2mName')

    def getActual(self):
        "Get the object this Logg is a log of, if it exists"
        return self.getModel().objects.filter(pk=self.instancePK).first()
    
    def getActualUrl(self):
        "get_absolute_url for the object this Logg is a log of, if it exists"
        if actual := self.getActual():
            if hasattr(actual, 'get_absolute_url'):
                return actual.get_absolute_url()

    def nextLogg(self):
        return Logg.objects.filter(
            model=self.model,
            instancePK=self.instancePK,
            timeStamp__gt=self.timeStamp
        ).order_by("timeStamp").first()
    
    def lastLogg(self):
        return Logg.objects.filter(
            model=self.model,
            instancePK=self.instancePK,
            timeStamp__lt=self.timeStamp
        ).order_by("-timeStamp").first()

    def get_absolute_url(self):
        return reverse('logg', args=[self.pk])

    def __str__(self):
        return f'{self.model}{"-*+"[self.change+1]} {self.strRep}'

    class Meta:
        ordering = ['-timeStamp']
        verbose_name_plural = "logger"


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
        "Gets the corresponding create or delete M2M"
        if self.change == LoggM2M.CREATE:
            return LoggM2M.objects.filter(
                fromLogg__instancePK=self.fromLogg.instancePK,
                toLogg__instancePK=self.toLogg.instancePK,
                m2mName=self.m2mName,
                change=LoggM2M.DELETE,
                timeStamp__gt=self.timeStamp
            ).order_by(
                "timeStamp"
            ).first()
        else:
            return LoggM2M.objects.filter(
                fromLogg__instancePK=self.fromLogg.instancePK,
                toLogg__instancePK=self.toLogg.instancePK,
                m2mName=self.m2mName,
                change=LoggM2M.CREATE,
                timeStamp__lt=self.timeStamp
            ).order_by(
                "-timeStamp"
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
                "vervInnehavelse__start__year", 
                filter=Q(vervInnehavelse__verv__in=kVerv)
            )
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
    fødselsdato = MyDateField(null=True, blank=True) # https://stackoverflow.com/questions/12370177/django-set-default-widget-in-model-definition
    epost = models.EmailField(max_length=100, blank=True)
    tlf = models.CharField(max_length=20, default='', blank=True)
    studieEllerJobb = models.CharField(max_length=100, blank=True)
    boAdresse = models.CharField(max_length=100, blank=True)
    foreldreAdresse = models.CharField(max_length=100, blank=True)

    def generateUploadTo(instance, fileName):
        path = "sjekkhefteBilder/"
        format = f'{instance.pk}.{fileName.split(".")[-1]}'
        fullPath = os.path.join(path, format)
        return fullPath

    bilde = models.ImageField(upload_to=generateUploadTo, null=True, blank=True)

    def __str__(self):
        strRep = self.navn
        if storkor := self.storkor:
            strRep += f' {storkor} {self.karantenekor}'
        return strRep

    @cached_property
    def firstStemmegruppeVervInnehavelse(self):
        """Returne første stemmegruppeverv de hadde i et storkor"""
        return self.vervInnehavelse.filter(
            stemmegruppeVerv(),
            verv__kor__kortTittel__in=["TSS", "TKS"]
        ).order_by('start').first()
    
    @property
    def storkor(self):
        """Returne koran TSS eller TKS eller en tom streng """
        if self.firstStemmegruppeVervInnehavelse:
            return self.firstStemmegruppeVervInnehavelse.verv.kor
        return ''

    @property
    def karantenekor(self):
        """Returne K{to sifret år av første storkor stemmegruppeverv}, eller 4 dersom det e før år 2000"""
        if self.firstStemmegruppeVervInnehavelse:
            if self.firstStemmegruppeVervInnehavelse.start.year >= 2000:
                return f'K{self.firstStemmegruppeVervInnehavelse.start.strftime("%y")}'
            else:
                return f'K{self.firstStemmegruppeVervInnehavelse.start.strftime("%Y")}'
        else:
            return ''

    # @property
    # def stemmegrupper(self):
    #     """Returne aktive stemmegruppeverv"""
    #     return Verv.objects.filter(vervInnehavelseAktiv(), vervInnehavelse__medlem=self)

    @cached_property
    def tilganger(self):
        """Returne aktive tilganger"""
        return Tilgang.objects.filter(vervInnehavelseAktiv('verv__vervInnehavelse'), verv__vervInnehavelse__medlem=self).distinct()
    
    @cached_property
    def navBarTilgang(self):
        sider = set()
        tilganger = self.tilganger
        if self.tilganger.filter(navn='medlemsdata').exists():
            sider.add('medlemListe')
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
        "Returne en boolean som sie om man kan redigere noe på denne instansens side"
        return self.tilgangQueryset(type(instance), extended=False).filter(pk=instance.pk).exists()

    def tilgangQueryset(self, model, extended=False):
        """ Returne i queryset over objekt der vi har tilgang til noe på den tilsvarende siden og 
            sansynligvis vil gjøre noe med (samme kor som grunnen til at man har tilgang til det).
            Med extended=True returne den absolutt alle objekt hvis sider brukeren kan redigere noe. 
            Dette slår altså sammen logikken for hva som kommer opp i lister, og hvilke instans-sider man har 
            tilgang til. 
        """
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
        
        if model == Logg: # For Logg siden
            loggs = Logg.objects.distinct().none()

            models = [
                [Verv, 'verv'], 
                [VervInnehavelse, 'vervInnehavelse'],
                [Dekorasjon, 'dekorasjon'],
                [DekorasjonInnehavelse, 'dekorasjonInnehavelse'],
                [Tilgang, 'tilgang']
            ]

            for [model, tilgangNavn] in models:
                loggs |= Logg.objects.filter(Q(kor__tilganger__in=self.tilganger.filter(navn=tilgangNavn)) | Q(kor__isnull=True), model=model.__name__).distinct()

            return loggs

    def get_absolute_url(self):
        return reverse('medlem', args=[self.pk])
    
    class Meta:
        ordering = ['fornavn', 'mellomnavn', 'etternavn']
        verbose_name_plural = "medlemmer"


class KorQuerySet(models.QuerySet):
    def korForInstance(self, instance):
        'Returne det tilsvarende koret for instancen, brukes i logSignals'
        if type(instance) == VervInnehavelse:
            return instance.verv.kor
        elif type(instance) == DekorasjonInnehavelse:
            return instance.dekorasjon.kor
        else:
            return instance.kor

class Kor(models.Model):
    objects = KorQuerySet.as_manager()
    kortTittel = models.CharField(max_length=10) # [TSS, Pirum, KK, Candiss, TKS] helst i den rekkefølgen på id (0-4)
    langTittel = models.CharField(max_length=50) # Trondhjems Studentersangforening, Pirum osv

    def __str__(self):
        return self.kortTittel
    
    class Meta:
        verbose_name_plural = "kor"


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
        default="",
        blank=True
    )

    brukt = models.BooleanField(
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
        verbose_name_plural = "tilganger"


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
        verbose_name_plural = "verv"


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
        ordering = ['-start']
        verbose_name_plural = "vervinnehavelser"

    # https://docs.djangoproject.com/en/4.2/ref/models/instances/#django.db.models.Model.clean
    def clean(self, *args, **kwargs):
        if self.slutt is not None and self.start > self.slutt:
            raise ValidationError(
                _("Ugyldig start slutt rekkefølge: %(start)s %(slutt)s"),
                code="invalid",
                params={"start": self.start, "slutt": self.slutt},
            )


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
        verbose_name_plural = "dekorasjoner"


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
        ordering = ['-start']
        verbose_name_plural = "dekorasjoninnehavelser"

