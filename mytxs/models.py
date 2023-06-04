from functools import cached_property
import os
from django.conf import settings
from django.db import models
from django.db.models import Value as V, Q, F, Case, When
from django.db.models.functions import Concat
from django.forms import ValidationError
from django.urls import reverse

from mytxs.fields import MyDateField, MyManyToManyField

from mytxs.utils.modelUtils import orderStemmegruppeVerv, toolTip, vervInnehavelseAktiv, hovedStemmeGruppeVerv, stemmeGruppeVerv

from django.utils.translation import gettext_lazy as _

from django.core import serializers

import json

from django.template import defaultfilters

from django.apps import apps

class LoggQueryset(models.QuerySet):
    def getLoggLinkFor(self, instance):
        if logg := Logg.objects.filter(model=type(instance).__name__, instancePK=instance.pk).order_by('-timeStamp').first():
            return logg.get_absolute_url

class Logg(models.Model):
    objects = LoggQueryset.as_manager()
    timeStamp = models.DateTimeField(auto_now_add=True, editable=True)

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

    CREATE_CHANGE, UPDATE_CHANGE, DELETE_CHANGE = 1, 0, -1
    CHANGE_CHOICES = ((CREATE_CHANGE, 'Create'), (UPDATE_CHANGE, 'Update'), (DELETE_CHANGE, 'Delete'))
    change = models.SmallIntegerField(choices=CHANGE_CHOICES, null=False)
    
    model = models.CharField(
        max_length=50
    )

    instancePK = models.PositiveIntegerField(
        null=False
    )

    value = models.JSONField(null=False)

    def deserialize(self):
        for obj in serializers.deserialize("jsonl", json.dumps(self.value)):
            return obj.object
        
    def getActual(self):
        obj = self.deserialize()
        return type(obj).objects.filter(pk=obj.pk).first()

    def get_absolute_url(self):
        return reverse('logg', args=[self.pk])

    def __str__(self):
        return f'{self.model}{"-*+"[self.change+1]} ({defaultfilters.date(self.timeStamp, "Y-m-d H:i:s")})'#.strftime("%Y-%m-%d %H:%M:%S")

    class Meta:
        ordering = ['-timeStamp']
        verbose_name_plural = "logger"


class LoggM2M(models.Model):
    timeStamp = models.DateTimeField(auto_now_add=True, editable=True)

    author = models.ForeignKey(
        'Medlem',
        on_delete=models.SET_NULL,
        null=True,
        related_name='m2mlogger'
    )

    model = models.CharField(
        max_length=50
    )

    fromPK = models.PositiveIntegerField(
        null=False
    )

    toPK = models.PositiveIntegerField(
        null=False
    )

    CHANGE_CREATE, CHANGE_DELETE = 1, -1
    CHANGE_CHOICES = ((CHANGE_CREATE, 'Create'), (CHANGE_DELETE, 'Delete'))
    change = models.SmallIntegerField(choices=CHANGE_CHOICES, null=False)

    def __str__(self):
        return f'{self.model} ({self.timeStamp})' #.strftime("%Y-%m-%d %H:%M:%S")

    class Meta:
        ordering = ['-timeStamp']


class MedlemQuerySet(models.QuerySet):
    def annotateFulltNavn(self):
        "Annotate fullt navn med korrekt mellomrom, viktig for søk på medlemmer"
        return self.annotate(
            fullt_navn=Case(
                When(
                    mellomnavn='',
                    then=Concat('fornavn', V(' '), 'etternavn')
                ),
                default=Concat('fornavn', V(' '), 'mellomnavn', V(' '), 'etternavn')
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
        """
        Returne navnet korrekt spaced (mellomnavn kan vær '')
        """
        if self.mellomnavn:
            return f'{self.fornavn} {self.mellomnavn} {self.etternavn}'
        else:
            return f'{self.fornavn} {self.etternavn}'


    # Følgende fields er bundet av GDPR, vi må ha godkjennelse fra medlemmet for å lagre de. 
    fødselsdato = MyDateField(null=True, blank=True) # https://stackoverflow.com/questions/12370177/django-set-default-widget-in-model-definition
    epost = models.EmailField(max_length=100, blank=True)
    tlf = models.BigIntegerField(null=True, blank=True)
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
        return f'{self.navn} {self.storkor} {self.karantenekor}'

    @cached_property
    def firstStemmegruppeVervInnehavelse(self):
        """Returne første stemmegruppeverv de hadde i et storkor"""
        return self.vervInnehavelse.filter(
            stemmeGruppeVerv(),
            verv__kor__kortTittel__in=["TSS", "TKS"]
        ).order_by('start').first()
    
    @property
    def storkor(self):
        """Returne {'TSS', 'TKS' eller ''}"""
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

        if self.tilganger.filter(navn='vervInnehavelse').exists():
            sider.add('medlemListe')
            sider.add('vervListe')

        if self.tilganger.filter(navn='dekorasjonInnehavelse').exists():
            sider.add('medlemListe')
            sider.add('dekorasjonListe')

        if self.tilganger.filter(navn='verv').exists():
            sider.add('vervListe')

        if self.tilganger.filter(navn='dekorasjon').exists():
            sider.add('dekorasjonListe')

        if self.tilganger.filter(navn='tilgang').exists():
            sider.add('vervListe')
            sider.add('tilgangListe')

        if self.tilganger.filter(navn='logg').exists():
            sider.add('loggListe')

        return list(sider)

    def harSideTilgang(self, instance):
        "Returne en boolean som sie om man kan redigere noe på denne instansens side"
        return self.tilgangQueryset(type(instance), extended=True).filter(pk=instance.pk).exists()

    def tilgangQueryset(self, model, extended=False):
        """ Returne i queryset over objekt der vi har tilgang til noe på siden og sansynligvis vil
            gjøre noe med (samme kor som grunnen til at man har tilgang til det).
            Med extended=True returne den absolutt alle objekt hvis sider brukeren kan redigere noe. 
            Dette slår altså sammen logikken for hva som kommer opp i lister, og hvilke instans-sider man har 
            tilgang til. 
        """
        if model == Medlem: # For Medlem siden
            medlemmer = Medlem.objects.distinct().filter(pk=self.pk)
            if self.tilganger.filter(navn='medlemsdata').exists():
                if extended: # Om extended, også ha med inaktive korister, og folk uten kor
                    medlemmer |= Medlem.objects.filter(
                        stemmeGruppeVerv('vervInnehavelse__verv'),
                        Q(vervInnehavelse__verv__kor__tilganger__in=self.tilganger.filter(navn='medlemsdata')) | 
                        Q(vervInnehavelse__verv__kor__isnull=True)
                    ).distinct()
                else: # Om ikke extended, ha inn aktive korister i det koret
                    medlemmer |= Medlem.objects.filter(
                        vervInnehavelseAktiv(),
                        stemmeGruppeVerv('vervInnehavelse__verv'),
                        vervInnehavelse__verv__kor__tilganger__in=self.tilganger.filter(navn='medlemsdata')
                    ).distinct()
                
            if self.tilganger.filter(navn='vervInnehavelse').exists():
                if extended: # Om extended, ha med alle potensielle vervInnehavere
                    return Medlem.objects
                else: # Om ikke, bare ha med aktive i det samme koret
                    medlemmer |= Medlem.objects.filter(
                        vervInnehavelseAktiv(),
                        stemmeGruppeVerv('vervInnehavelse__verv'),
                        vervInnehavelse__verv__kor__tilganger__in=self.tilganger.filter(navn='vervInnehavelse')
                    )
            
            if self.tilganger.filter(navn='dekorasjonInnehavelse').exists():
                if extended: # Om extended, ha med alle vervInnehavere
                    return Medlem.objects
                else: # Om ikke, bare ha med aktive i det samme koret
                    medlemmer |= Medlem.objects.filter(
                        vervInnehavelseAktiv(),
                        stemmeGruppeVerv('vervInnehavelse__verv'),
                        vervInnehavelse__verv__kor__tilganger__in=self.tilganger.filter(navn='dekorasjonInnehavelse')
                    )
            
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
            return Logg.objects.filter(kor__tilganger__in=self.tilganger.filter(navn='logg'))

    def get_absolute_url(self):
        return reverse('medlem', args=[self.pk])
    
    class Meta:
        verbose_name_plural = "medlemmer"


class Kor(models.Model):
    kortTittel = models.CharField(max_length=10) # [TSS, Pirum, KK, Candiss, TKS] helst i den rekkefølgen på id (0-4)
    langTittel = models.CharField(max_length=50) # Trondhjems Studentersangforening, Pirum osv

    @property
    def logg_url(self):
        return Logg.objects.getLoggLinkFor(self)
    
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

    @property
    def tittel(self):
        return self.__str__()
    
    @property
    def logg_url(self):
        return Logg.objects.getLoggLinkFor(self)
    
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
        return Verv.objects.filter(stemmeGruppeVerv(''), pk=self.pk).exists()

    @property
    def logg_url(self):
        return Logg.objects.getLoggLinkFor(self)
    
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
    def kor(self): # For at Logg skal knytte alle objekt til kor
        return self.verv.kor
    
    @cached_property
    def aktiv(self):
        VervInnehavelse.objects.filter(vervInnehavelseAktiv(''), pk=self.pk).exists()

    @property
    def logg_url(self):
        return Logg.objects.getLoggLinkFor(self)
    
    def __str__(self):
        return f'{self.medlem.__str__()} -> {self.verv.__str__()}'
    
    class Meta:
        ordering = ['start']
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

    @property
    def logg_url(self):
        return Logg.objects.getLoggLinkFor(self)
    
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

    @property
    def kor(self): # For at Logg skal knytte alle objekt til kor
        return self.verv.kor
    
    @property
    def logg_url(self):
        return Logg.objects.getLoggLinkFor(self)
    
    def __str__(self):
        return f'{self.medlem.__str__()} -> {self.dekorasjon.__str__()}'
    
    class Meta:
        ordering = ['start']
        verbose_name_plural = "dekorasjoninnehavelser"

