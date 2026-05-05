import datetime
from io import StringIO
from unittest.mock import Mock

from django.contrib.auth.models import User
from django.db.utils import IntegrityError
from django.forms import ValidationError
from django.test import TestCase, Client
from django.urls import reverse

from mytxs import consts
from mytxs.management.commands.seed import makeMedlem, runSeed, setTop100Navn
from mytxs.models import Kor, Dekorasjon, DekorasjonInnehavelse, Verv

def getDato(offset):
    return datetime.date.today() + datetime.timedelta(offset)

class DekorasjonOvervalørTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        mock_self = Mock()
        mock_self.stdout = StringIO()
        runSeed(mock_self)

        cls.kor = Kor.objects.get(navn=consts.Kor.TSS)
        cls.user = User.objects.create(username='admin', email='testUser@example.com')
        cls.user.set_password('admin')
        cls.user.save()

        setTop100Navn()
        cls.medlem = makeMedlem(consts.Kor.TSS, start=getDato(-20), stemmegruppe=Verv.objects.filter(
            kor__navn=consts.Kor.TSS,
            navn='2B'
        ).first())
        cls.medlem.user=cls.user
        cls.medlem.save()


        cls.dekorasjon1 = Dekorasjon.objects.create(navn='dekorasjon1', kor=cls.kor)
        cls.dekorasjon2 = Dekorasjon.objects.create(navn='dekorasjon2', kor=cls.kor)

    def testOppretteDekorasjoninnehavelseMislykketNårStartIkkeOppgitt(self):
        self.assertRaises(IntegrityError, DekorasjonInnehavelse.objects.create, medlem=self.medlem, dekorasjon=self.dekorasjon1)

    def testOppretteDekorasjoninnehavelseVellykketNårStartOppgitt(self):
        DekorasjonInnehavelse.objects.create(medlem=self.medlem, dekorasjon=self.dekorasjon1, start=getDato(-10))

    def testOppretteDekorasjoninnehavelseMislykketNårUndervalørMangler(self):
        self.dekorasjon1.overvalør = self.dekorasjon2
        self.dekorasjon1.save()
        self.assertRaises(ValidationError, DekorasjonInnehavelse.objects.create, medlem=self.medlem, dekorasjon=self.dekorasjon2, start=getDato(-10))

    def testOppretteDekorasjoninnehavelseMislykketNårMedlemFikkUndervalørEtterOvervalør(self):
        self.dekorasjon1.overvalør = self.dekorasjon2
        self.dekorasjon1.save()
        DekorasjonInnehavelse.objects.create(medlem=self.medlem, dekorasjon=self.dekorasjon1, start=getDato(-5))
        self.assertRaises(ValidationError, DekorasjonInnehavelse.objects.create, medlem=self.medlem, dekorasjon=self.dekorasjon2, start=getDato(-10))

    def testOppretteOvervalørMislykketNårMedlemManglerUndervalør(self):
        DekorasjonInnehavelse.objects.create(medlem=self.medlem, dekorasjon=self.dekorasjon2, start=getDato(-10))
        self.dekorasjon1.overvalør = self.dekorasjon2
        self.assertRaises(ValidationError, self.dekorasjon1.save)

    def testOppretteOvervalørMislykketNårMedlemFikkUndervalørEtterOvervalør(self):
        DekorasjonInnehavelse.objects.create(medlem=self.medlem, dekorasjon=self.dekorasjon1, start=getDato(-5))
        DekorasjonInnehavelse.objects.create(medlem=self.medlem, dekorasjon=self.dekorasjon2, start=getDato(-10))
        self.dekorasjon1.overvalør = self.dekorasjon2
        self.assertRaises(ValidationError, self.dekorasjon1.save)

    def setupForSjekkheftet(self, start1, start2, sjekkhefteDato:datetime.date=None):
        self.dekorasjon1.overvalør = self.dekorasjon2
        self.dekorasjon1.save()
        DekorasjonInnehavelse.objects.create(medlem=self.medlem, dekorasjon=self.dekorasjon1, start=start1)
        DekorasjonInnehavelse.objects.create(medlem=self.medlem, dekorasjon=self.dekorasjon2, start=start2)
        client = Client()
        logged_in = client.login(username='admin', password='admin')
        response = client.get(reverse('sjekkheftet', args=[self.kor.navn]) + ('?dato=' + sjekkhefteDato.isoformat() if sjekkhefteDato else ''), follow=True)
        return str(response.content)

    def testUndervalørSkjules(self):
        content = self.setupForSjekkheftet(getDato(-5), getDato(-3))
        self.assertFalse(self.dekorasjon1.navn in content)
        self.assertTrue(self.dekorasjon2.navn in content)

    def testUndervalørVises(self):
        content = self.setupForSjekkheftet(getDato(-3), getDato(3))
        self.assertTrue(self.dekorasjon1.navn in content)
        self.assertFalse(self.dekorasjon2.navn in content)

    def testUndervalørSkjulesGammelDato(self):
        content = self.setupForSjekkheftet(getDato(-10), getDato(-8), sjekkhefteDato=getDato(-5))
        self.assertFalse(self.dekorasjon1.navn in content)
        self.assertTrue(self.dekorasjon2.navn in content)

    def testUndervalørVisesGammelDato(self):
        content = self.setupForSjekkheftet(getDato(-10), getDato(-3), sjekkhefteDato=getDato(-5))
        self.assertTrue(self.dekorasjon1.navn in content)
        self.assertFalse(self.dekorasjon2.navn in content)
