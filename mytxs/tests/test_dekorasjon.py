from django.test import TestCase
from django.forms import ValidationError
from django.db.utils import IntegrityError
from mytxs.models import Kor, Medlem, Dekorasjon, DekorasjonInnehavelse
from datetime import date


class DekorasjonErUnderordnetTestCase(TestCase):
    def setUp(self):
        self.kor = Kor.objects.create(navn='kor', tittel='kor')
        self.medlem = Medlem.objects.create()
        self.dekorasjon1 = Dekorasjon.objects.create(navn='dekorasjon1', kor=self.kor)
        self.dekorasjon2 = Dekorasjon.objects.create(navn='dekorasjon2', kor=self.kor)
        self.lavStart = date.min
        self.høyStart = date.max

    def test_opprette_dekorasjoninnehavelse_mislykket_når_start_ikke_oppgitt(self):
        self.assertRaises(IntegrityError, DekorasjonInnehavelse.objects.create, medlem=self.medlem, dekorasjon=self.dekorasjon1)

    def test_opprette_dekorasjoninnehavelse_vellykket_når_start_oppgitt(self):
        DekorasjonInnehavelse.objects.create(medlem=self.medlem, dekorasjon=self.dekorasjon1, start=self.lavStart)

    def test_opprette_dekorasjoninnehavelse_mislykket_når_underordnet_mangler(self):
        self.dekorasjon1.erUnderordnet = self.dekorasjon2
        self.dekorasjon1.save()
        self.assertRaises(ValidationError, DekorasjonInnehavelse.objects.create, medlem=self.medlem, dekorasjon=self.dekorasjon2, start=self.lavStart)

    def test_opprette_dekorasjoninnehavelse_mislykket_når_underordnet_etter_overordnet(self):
        self.dekorasjon1.erUnderordnet = self.dekorasjon2
        self.dekorasjon1.save()
        DekorasjonInnehavelse.objects.create(medlem=self.medlem, dekorasjon=self.dekorasjon1, start=self.høyStart)
        self.assertRaises(ValidationError, DekorasjonInnehavelse.objects.create, medlem=self.medlem, dekorasjon=self.dekorasjon2, start=self.lavStart)

    def test_opprette_underordning_mislykket_når_medlem_mangler_underordnet(self):
        DekorasjonInnehavelse.objects.create(medlem=self.medlem, dekorasjon=self.dekorasjon2, start=self.lavStart)
        self.dekorasjon1.erUnderordnet = self.dekorasjon2
        self.assertRaises(ValidationError, self.dekorasjon1.save)

    def test_opprette_underordning_mislykket_når_medlem_fikk_underordnet_sist(self):
        DekorasjonInnehavelse.objects.create(medlem=self.medlem, dekorasjon=self.dekorasjon1, start=self.høyStart)
        DekorasjonInnehavelse.objects.create(medlem=self.medlem, dekorasjon=self.dekorasjon2, start=self.lavStart)
        self.dekorasjon1.erUnderordnet = self.dekorasjon2
        self.assertRaises(ValidationError, self.dekorasjon1.save)
