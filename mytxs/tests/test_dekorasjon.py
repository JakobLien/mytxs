from django.test import TestCase, Client
from django.forms import ValidationError
from django.urls import reverse
from django.db.utils import IntegrityError
from django.core.management import call_command
from django.contrib.auth.models import User
from mytxs.models import Kor, Medlem, Dekorasjon, DekorasjonInnehavelse
from datetime import date


class DekorasjonOvervalørTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed', '--adminAdmin')

        cls.user = User.objects.get(username='admin')

        cls.medlem = Medlem.objects.get(user=cls.user)

        cls.kor = Kor.objects.get(navn='TSS')

        cls.dekorasjon1 = Dekorasjon.objects.create(navn='dekorasjon1', kor=cls.kor)
        cls.dekorasjon2 = Dekorasjon.objects.create(navn='dekorasjon2', kor=cls.kor)

        cls.lavStart = date.min
        cls.høyStart = date.max

    def test_opprette_dekorasjoninnehavelse_mislykket_når_start_ikke_oppgitt(self):
        self.assertRaises(IntegrityError, DekorasjonInnehavelse.objects.create, medlem=self.medlem, dekorasjon=self.dekorasjon1)

    def test_opprette_dekorasjoninnehavelse_vellykket_når_start_oppgitt(self):
        DekorasjonInnehavelse.objects.create(medlem=self.medlem, dekorasjon=self.dekorasjon1, start=self.lavStart)

    def test_opprette_dekorasjoninnehavelse_mislykket_når_undervalør_mangler(self):
        self.dekorasjon1.overvalør = self.dekorasjon2
        self.dekorasjon1.save()
        self.assertRaises(ValidationError, DekorasjonInnehavelse.objects.create, medlem=self.medlem, dekorasjon=self.dekorasjon2, start=self.lavStart)

    def test_opprette_dekorasjoninnehavelse_mislykket_når_undervalør_etter_overvalør(self):
        self.dekorasjon1.overvalør = self.dekorasjon2
        self.dekorasjon1.save()
        DekorasjonInnehavelse.objects.create(medlem=self.medlem, dekorasjon=self.dekorasjon1, start=self.høyStart)
        self.assertRaises(ValidationError, DekorasjonInnehavelse.objects.create, medlem=self.medlem, dekorasjon=self.dekorasjon2, start=self.lavStart)

    def test_opprette_overvalør_mislykket_når_medlem_mangler_undervalør(self):
        DekorasjonInnehavelse.objects.create(medlem=self.medlem, dekorasjon=self.dekorasjon2, start=self.lavStart)
        self.dekorasjon1.overvalør = self.dekorasjon2
        self.assertRaises(ValidationError, self.dekorasjon1.save)

    def test_opprette_overvalør_mislykket_når_medlem_fikk_undervalør_sist(self):
        DekorasjonInnehavelse.objects.create(medlem=self.medlem, dekorasjon=self.dekorasjon1, start=self.høyStart)
        DekorasjonInnehavelse.objects.create(medlem=self.medlem, dekorasjon=self.dekorasjon2, start=self.lavStart)
        self.dekorasjon1.overvalør = self.dekorasjon2
        self.assertRaises(ValidationError, self.dekorasjon1.save)

    def test_undervalør_skjules_i_sjekkheftet(self):
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
