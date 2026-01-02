from io import StringIO
from unittest.mock import Mock

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.test import TestCase

from mytxs.management.commands.seed import runSeed
from mytxs.models import *


class NoteTilgangTestCase(TestCase):
    'Logikken rundt kæm som kan last ned en fil fra notearkivet e ganske komplisert, så vi lage en test på den.'
    @classmethod
    def setUpTestData(cls):
        mock_self = Mock()
        mock_self.stdout = StringIO()
        runSeed(mock_self)

        cls.user = User.objects.create(username='admin')
        cls.medlem = Medlem.objects.create(user=cls.user, fornavn='admin', etternavn='adminsen')

        cls.lagSangFil(cls, 'TSS nå', consts.Kor.TSS, inneværendeSemester=True)
        cls.lagSangFil(cls, 'TSS før', consts.Kor.TSS, inneværendeSemester=False)
        cls.lagSangFil(cls, 'TSS nå og før', consts.Kor.TSS, inneværendeSemester=None)
        cls.lagSangFil(cls, 'KK nå', consts.Kor.Knauskoret, inneværendeSemester=True)
        cls.lagSangFil(cls, 'KK før', consts.Kor.Knauskoret, inneværendeSemester=False)
        cls.lagSangFil(cls, 'KK nå og før', consts.Kor.Knauskoret, inneværendeSemester=None)

    def settKorMedlemskap(self, korNavn, aktiv=True):
        'Setter kormedlemskap i TSS eller Knauskoret.'
        VervInnehavelse.objects.filter(
            medlem=self.medlem,
            verv__kor__navn=korNavn
        ).delete()

        Verv.objects.filter(
            stemmegruppeVerv(''),
            kor__navn=korNavn,
        ).first().vervInnehavelser.create(
            medlem=self.medlem,
            start=datetime.date.today() - datetime.timedelta(365),
            **({} if aktiv else {'slutt': datetime.date.today() - datetime.timedelta(1)})
        )

    def lagSangFil(self, navn, korNavn, inneværendeSemester):
        sang = Sang.objects.create(
            navn='testSang: ' + navn,
            kor=Kor.objects.filter(navn=consts.Kor.TXS if korNavn in consts.bareStorkorNavn else korNavn).first()
        )
        # TODO: Dette kjem te å faktisk overskriv filer som ligg på disk, fra index 1-6. Hadd vært fint om det va 
        # trygt å kjør denne på servern også bare, uten å ødelegg noko. Går fint da:)
        sang.filer.create(
            navn='testFil: ' + navn,
            fil=ContentFile(bytes(), name='testFilNavn.mp3')
        )

        if inneværendeSemester != False:
            sang.repertoar.create(
                navn='testRep: ' + navn,
                kor=Kor.objects.filter(navn=korNavn).first(),
                dato=datetime.date.today()
            )

        if inneværendeSemester != True:
            sang.repertoar.create(
                navn='testRep2: ' + navn,
                kor=Kor.objects.filter(navn=korNavn).first(),
                dato=datetime.date.today() - datetime.timedelta(365)
            )

    def sjekkFilTilgang(self, sang, skalHaTilgang=True):
        self.client.force_login(self.user)
        res = self.client.get(sang.filer.first().fil.url)
        self.assertEqual(res.status_code, 200 if skalHaTilgang else 403, 'Skal ' + ('' if skalHaTilgang else 'ikke ') + 'ha tilgang til ' + str(sang))

    def testStorkorTilgang(self):
        'Aktive og gamle storkorister kan laste ned alle filer i storkor, og ingen i småkor'
        for i in range(2):
            self.settKorMedlemskap(consts.Kor.TSS, aktiv=i==1)
            for sang in Sang.objects.all():
                self.sjekkFilTilgang(sang, skalHaTilgang=sang.kor.navn==consts.Kor.TXS)

    def testAktivSmåkorTilgang(self):
        'Aktive småkorister kan laste ned alle filer i småkor og storkor.'
        self.settKorMedlemskap(consts.Kor.TSS, aktiv=True)
        self.settKorMedlemskap(consts.Kor.Knauskoret, aktiv=True)
        for sang in Sang.objects.all():
            self.sjekkFilTilgang(sang)

    def testUtelukkendeSmåkoristTilgang(self):
        'Folk som e i småkor men ikkje i storkor har kun tilgang til småkor ting. Ikke så realistisk, men hjelpsomt for å bekreft logikken i koden.'
        self.settKorMedlemskap(consts.Kor.Knauskoret, aktiv=True)
        for sang in Sang.objects.all():
            self.sjekkFilTilgang(sang, skalHaTilgang=sang.kor.navn==consts.Kor.Knauskoret)

    def testTidligarSmåkorTilgang(self):
        'Tidligere småkorista kan last ned alle filer i storkor og filer i småkor som ikke KUN e på inneværende semester.'
        self.settKorMedlemskap(consts.Kor.TSS, aktiv=True)
        self.settKorMedlemskap(consts.Kor.Knauskoret, aktiv=False)
        for sang in Sang.objects.all():
            self.sjekkFilTilgang(sang, skalHaTilgang=sang.kor.navn==consts.Kor.TXS or sang.repertoar.filter(dato__lt=getHalvårStart()).exists())
