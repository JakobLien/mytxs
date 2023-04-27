from functools import cached_property
import os
from django.conf import settings
from django.db import models
import datetime
from django.db.models import Value as V, Case, When
from django.db.models.functions import Concat
from django import forms

from mytxs.fields import MyDateField

class MedlemQuerySet(models.QuerySet):
    def medlemmerMedTilgang(self, tilgangNavn):
        return self.filter(vervInnehavelse__verv__tilganger__navn=tilgangNavn,
                           vervInnehavelse__start__lte=datetime.date.today(),
                           vervInnehavelse__slutt__gte=datetime.date.today())
    
    def annotateFulltNavn(self):
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
        related_name='medlem'
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


    # Følgende fields er bundet av GDPR, må slettes om noen etterspør det. 
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
        return f'{self.fornavn} {self.mellomnavn} {self.etternavn}'

    @cached_property
    def firstStemmegruppeVervInnehavelse(self):
        """Returne første stemmegruppeverv de hadde i et storkor"""
        stemmegruppeNavn = ["1S", "2S", "1A", "2A", "1T", "2T", "1B", "2B"]
        return self.vervInnehavelse\
            .filter(verv__navn__in=stemmegruppeNavn)\
            .filter(verv__kor__kortTittel__in=["TSS", "TKS"])\
            .order_by('start').first()
    
    @property
    def storkor(self):
        """Returne {'TSS', 'TKS' eller ''}"""
        return self.firstStemmegruppeVervInnehavelse.verv.kor

    @property
    def karantenekor(self):
        """Returne K{to sifret år av første storkor stemmegruppeverv}, eller 4 dersom det e før år 2000"""
        if self.firstStemmegruppeVervInnehavelse.start.year >= 2000:
            return f'K{self.firstStemmegruppeVervInnehavelse.start.strftime("%y")}'
        else:
            return f'K{self.firstStemmegruppeVervInnehavelse.start.strftime("%Y")}'

    @property
    def stemmegrupper(self):
        """Returne aktive stemmegruppeverv"""
        return Verv.objects.filter(vervInnehavelse__medlem=self,
                                   vervInnehavelse__start__lte=datetime.date.today(),
                                   vervInnehavelse__slutt__gte=datetime.date.today())

    @cached_property
    def tilganger(self):
        return [tilgang.navn for tilgang in
            Tilgang.objects.filter(verv__vervInnehavelse__medlem=self, 
                                   verv__vervInnehavelse__start__lte=datetime.date.today(),
                                   verv__vervInnehavelse__slutt__gte=datetime.date.today())]
    
    @cached_property
    def tilgangTilSider(self):
        sider = set()
        tilganger = self.tilganger
        if 'medlemsregister' in tilganger:
            sider.add('medlem')
            sider.add('medlemListe')

        if [tilgang for tilgang in tilganger if tilgang.endswith("vervInnehavelse")]:
            sider.add('medlem')
            sider.add('medlemListe')
            sider.add('verv')
            sider.add('vervListe')

        if 'tilgang' in tilganger:
            sider.add('verv')
            sider.add('vervListe')
            sider.add('tilgangListe')
            sider.add('tilgang')

        if [tilgang for tilgang in tilganger if tilgang.endswith("vervInnehavelse")]:
            sider.add('medlem')
            sider.add('medlemListe')
            sider.add('dekorasjon')
            sider.add('dekorasjonListe')
        
        return list(sider)


class Kor(models.Model):
    kortTittel = models.CharField(max_length=3) # [TSS, P, KK, C, TKS] helst i den rekkefølgen på id (0-4)
    langTittel = models.CharField(max_length=50) # Trondhjems Studentersangforening, Pirum osv
    def __str__(self):
        return self.kortTittel
    
    @property
    def stemmegruppeVerv(self):
        stemmegrupper = ["1S", "2S", "1A", "2A", "1T", "2T", "1B", "2B"]
        return Verv.objects.filter(navn__in=stemmegrupper, kor=self)


class Tilgang(models.Model):
    navn = models.CharField(max_length=50, unique=True)
    def __str__(self):
        return self.navn
    
    class Meta:
        ordering = ['navn']

class Verv(models.Model):
    navn = models.CharField(max_length=30)
    tilganger = models.ManyToManyField(
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
    def __str__(self):
        return f'{self.navn}({self.kor.__str__()})'
    
    class Meta:
        unique_together = ('navn', 'kor')
        ordering = ['kor', Case(
                When(navn='1S', then=0),
                When(navn='2S', then=1),
                When(navn='1A', then=2),
                When(navn='2A', then=3),
                When(navn='1T', then=4),
                When(navn='2T', then=5),
                When(navn='1B', then=6),
                When(navn='2B', then=7),
                default=8
            ), 'navn']


class VervInnehavelse(models.Model):
    medlem = models.ForeignKey(
        Medlem,
        on_delete=models.CASCADE,
        null=False,
        related_name='vervInnehavelse'
    )
    verv = models.ForeignKey(
        Verv,
        on_delete=models.CASCADE,
        null=False,
        related_name='vervInnehavelse'
    )
    start = MyDateField(blank=False)
    slutt = MyDateField(blank=False)
    def __str__(self):
        return f'{self.medlem.__str__()} -> {self.verv.__str__()}'
    
    class Meta:
        ordering = ['start']
    
    @cached_property
    def aktiv(self):
        return self.start <= datetime.date.today() <= self.slutt


class Dekorasjon(models.Model):
    navn = models.CharField(max_length=30)
    kor = models.ForeignKey(
        Kor,
        related_name='dekorasjoner',
        on_delete=models.DO_NOTHING,
        null=True
    )
    def __str__(self):
        return f'{self.navn}({self.kor.__str__()})'
    
    class Meta:
        unique_together = ('navn', 'kor')
        ordering = ['kor', 'navn']

class DekorasjonInnehavelse(models.Model):
    medlem = models.ForeignKey(
        Medlem,
        on_delete=models.CASCADE,
        null=False,
        related_name='dekorasjonInnehavelse'
    )
    dekorasjon = models.ForeignKey(
        Dekorasjon,
        on_delete=models.CASCADE,
        null=False,
        related_name='dekorasjonInnehavelse'
    )
    start = MyDateField(null=False)
    def __str__(self):
        return f'{self.medlem.__str__()} -> {self.dekorasjon.__str__()}'
    
    class Meta:
        ordering = ['start']
