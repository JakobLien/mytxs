from datetime import date
from io import StringIO
from unittest.mock import Mock

from django.contrib.auth.models import User
from django.db.utils import IntegrityError
from django.forms import ValidationError
from django.test import TestCase, Client
from django.urls import reverse

from mytxs.management.commands.seed import adminAdmin, runSeed
from mytxs.models import Kor, Medlem, Dekorasjon, DekorasjonInnehavelse

class DekorasjonOvervalørTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        mock_self = Mock()
        mock_self.stdout = StringIO()
        runSeed(mock_self)
        adminAdmin(mock_self)

        cls.user = User.objects.get(username='admin')

        cls.medlem = Medlem.objects.get(user=cls.user)

        cls.kor = Kor.objects.get(navn='TSS')

        cls.dekorasjon1 = Dekorasjon.objects.create(navn='dekorasjon1', kor=cls.kor)
        cls.dekorasjon2 = Dekorasjon.objects.create(navn='dekorasjon2', kor=cls.kor)

        cls.lavStart = date.min
        cls.høyStart = date.max

    def testOppretteDekorasjoninnehavelseMislykketNårStartIkkeOppgitt(self):
        self.assertRaises(IntegrityError, DekorasjonInnehavelse.objects.create, medlem=self.medlem, dekorasjon=self.dekorasjon1)

    def testOppretteDekorasjoninnehavelseVellykketNårStartOppgitt(self):
        DekorasjonInnehavelse.objects.create(medlem=self.medlem, dekorasjon=self.dekorasjon1, start=self.lavStart)

    def testOppretteDekorasjoninnehavelseMislykketNårUndervalørMangler(self):
        self.dekorasjon1.overvalør = self.dekorasjon2
        self.dekorasjon1.save()
        self.assertRaises(ValidationError, DekorasjonInnehavelse.objects.create, medlem=self.medlem, dekorasjon=self.dekorasjon2, start=self.lavStart)

    def testOppretteDekorasjoninnehavelseMislykketNårMedlemFikkUndervalørEtterOvervalør(self):
        self.dekorasjon1.overvalør = self.dekorasjon2
        self.dekorasjon1.save()
        DekorasjonInnehavelse.objects.create(medlem=self.medlem, dekorasjon=self.dekorasjon1, start=self.høyStart)
        self.assertRaises(ValidationError, DekorasjonInnehavelse.objects.create, medlem=self.medlem, dekorasjon=self.dekorasjon2, start=self.lavStart)

    def testOppretteOvervalørMislykketNårMedlemManglerUndervalør(self):
        DekorasjonInnehavelse.objects.create(medlem=self.medlem, dekorasjon=self.dekorasjon2, start=self.lavStart)
        self.dekorasjon1.overvalør = self.dekorasjon2
        self.assertRaises(ValidationError, self.dekorasjon1.save)

    def testOppretteOvervalørMislykketNårMedlemFikkUndervalørEtterOvervalør(self):
        DekorasjonInnehavelse.objects.create(medlem=self.medlem, dekorasjon=self.dekorasjon1, start=self.høyStart)
        DekorasjonInnehavelse.objects.create(medlem=self.medlem, dekorasjon=self.dekorasjon2, start=self.lavStart)
        self.dekorasjon1.overvalør = self.dekorasjon2
        self.assertRaises(ValidationError, self.dekorasjon1.save)

    def testUndervalørSkjulesISjekkheftet(self):
        self.dekorasjon1.overvalør = self.dekorasjon2
        self.dekorasjon1.save()
        DekorasjonInnehavelse.objects.create(medlem=self.medlem, dekorasjon=self.dekorasjon1, start=self.lavStart)
        DekorasjonInnehavelse.objects.create(medlem=self.medlem, dekorasjon=self.dekorasjon2, start=self.høyStart)
        client = Client()
        logged_in = client.login(username='admin', password='admin')
        response = client.get(reverse('sjekkheftet', args=[self.kor.navn]), follow=True)
        content = str(response.content)
        self.assertFalse(self.dekorasjon1.navn in content)
        self.assertTrue(self.dekorasjon2.navn in content)
