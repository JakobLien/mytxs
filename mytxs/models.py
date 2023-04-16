import os
from django.conf import settings
from django.db import models
from datetime import datetime
from django.db.models import F

class MedlemManager(models.Manager):
    def medlemmerMedAktivTilgang(self, tilgangNavn):
        tilgang = Tilgang.objects.get(navn=tilgangNavn)
        verv = tilgang.verv.all()
        vervInnehavelser = []
        for verv in verv:
            vervInnehavelser.extend(verv.vervInnehavelse.all())
        return [vervInnehavelse.medlem for vervInnehavelse in vervInnehavelser
                if vervInnehavelse.start <= datetime.now().date() <= vervInnehavelse.slutt]
    
    def medlemmerMedTilgang(self, tilgangNavn):
        tilgang = Tilgang.objects.get(navn=tilgangNavn)
        verv = tilgang.verv.all()
        vervInnehavelser = []
        for verv in verv:
            vervInnehavelser.extend(verv.vervInnehavelse.all())
        return [vervInnehavelse.medlem for vervInnehavelse in vervInnehavelser]

# Create your models here.
class Medlem(models.Model):
    objects = MedlemManager()
    
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='medlem'
    )

    fornavn = models.CharField(max_length = 50, default='Ola')
    mellomnavn = models.CharField(max_length = 50, default='', blank=True)
    etternavn = models.CharField(max_length = 50, default='Nordmann')

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
    fødselsdato = models.DateField(null=True, blank=True)
    epost = models.EmailField(max_length=100, blank=True)
    tlf = models.BigIntegerField(null=True, blank=True)
    studieEllerJobb = models.CharField(max_length=100, blank=True)
    boAdresse = models.CharField(max_length=100, blank=True)
    foreldreAdresse = models.CharField(max_length=100, blank=True)

    def generateUploadTo(instance, fileName):
        path = "sjekkhefteBilder/"
        format = f'{instance.pk}.{fileName.split(".")[-1]}'
        fullPath = os.path.join(path, format)

        # print(f'Instance: {instance.bilde}')

        # if instance.bilde:
        #     print("GotHere")
        #     instance.bilde.delete()

        return fullPath

    bilde = models.ImageField(upload_to=generateUploadTo, null=True, blank=True)

    def __str__(self):
        return f'{self.fornavn} {self.mellomnavn} {self.etternavn}'

    # @property
    # def tattOpp(self):
    #     """
    #     Returne en date de startet i sitt første kor
    #     """
    #     stemmegruppeNavn = ["1S", "2S", "1A", "2A", "1T", "2T", "1B", "2B"]
    #     firstVervInnehavelse = self.vervInnehavelse.filter(verv__navn__in=stemmegruppeNavn).order_by('start').first()
    #     return firstVervInnehavelse.start

    @property
    def storkor(self):
        """
        Returne {'TSS', 'TKS' eller ''}
        """
        stemmegruppeNavn = ["1S", "2S", "1A", "2A", "1T", "2T", "1B", "2B"]
        firstVervInnehavelse = self.vervInnehavelse\
            .filter(verv__navn__in=stemmegruppeNavn)\
            .filter(verv__kor__kortTittel__in=["TSS", "TKS"])\
            .order_by('start').first()
        if firstVervInnehavelse:
            return f'{firstVervInnehavelse.verv.kor.kortTittel}'
        else:
            return ''

    @property
    def karantenekor(self):
        """
        Returne K{to sifret år av første storkor stemmegruppeverv}
        """
        stemmegruppeNavn = ["1S", "2S", "1A", "2A", "1T", "2T", "1B", "2B"]
        firstVervInnehavelse = self.vervInnehavelse\
            .filter(verv__navn__in=stemmegruppeNavn)\
            .filter(verv__kor__kortTittel__in=["TSS", "TKS"])\
            .order_by('start').first()
        if firstVervInnehavelse:
            return f'K{firstVervInnehavelse.start.strftime("%y")}'
        else:
            return ''

    @property
    def tilganger(self):
        tilganger = []

        for verv in [vervInnehavelse.verv for vervInnehavelse in self.vervInnehavelse.all()
            if vervInnehavelse.start <= datetime.now().date() <= vervInnehavelse.slutt
        ]:
            tilganger.extend([tilgang.navn for tilgang in verv.tilganger.all()])
        return tilganger

    def harTilgang(self, tilgangNavn):
        for verv in [vervInnehavelse.verv for vervInnehavelse in self.vervInnehavelse.all()]:
            if tilgangNavn in [tilgang.navn for tilgang in verv.tilganger.all()]:
                return True
        return False
    
    def korForTilgang(self, tilgangNavn):
        kor = filter(lambda tilgang : tilgang.endswith(tilgangNavn), self.tilganger)
        return list(map(lambda kor : kor.split("-")[0], kor))
    
    def iKor(self, kor):
        return self.harTilgang(kor+"-aktiv")
    
    @property
    def tilgangTilSider(self):
        sider = set()
        tilganger = self.tilganger
        if 'medlemsregister' in tilganger:
            sider.add('medlem')
            sider.add('medlemListe')

        if len(self.korForTilgang('vervInnehavelse')) > 0:
            sider.add('medlem')
            sider.add('medlemListe')
            sider.add('verv')
            sider.add('vervListe')

        if self.harTilgang('tilgang'):
            sider.add('verv')
            sider.add('vervListe')
            sider.add('tilgangListe')
            sider.add('tilgang')

        if len(self.korForTilgang('dekorasjonInnehavelse')) > 0:
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
        ordering = ['kor', 'navn']


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
    start = models.DateField(blank=False)
    slutt = models.DateField(blank=False)
    def __str__(self):
        return f'{self.medlem.__str__()} -> {self.verv.__str__()}'
    
    class Meta:
        ordering = ['start']


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
    start = models.DateField(null=False)
    def __str__(self):
        return f'{self.medlem.__str__()} -> {self.dekorasjon.__str__()}'
    
    class Meta:
        ordering = ['start']
