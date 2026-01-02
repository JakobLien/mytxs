import datetime
from io import StringIO
from unittest.mock import Mock
import random

from django.contrib.auth.models import User
from django.db.models import Q
from django.test import TestCase

from mytxs import consts
from mytxs.management.commands.seed import adminAdmin, makeMedlem, runSeed, setTop100Navn
from mytxs.models import Kor, Medlem, Tilgang, Verv, VervInnehavelse
from mytxs.utils.formAccess import fieldIsVisible
from mytxs.utils.modelUtils import stemmegruppeVerv
from mytxs.utils.utils import getHalvårStart

start = getHalvårStart()
slutt = start + datetime.timedelta(days=365)

def getRandomStemmegruppe(kor):
    return Verv.objects.get(kor__navn=kor, navn=random.choice(kor.stemmegrupper()))

class TilgangerTestCase(TestCase):
    def seed():
        setTop100Navn()
        # Lage 15 stk jevnt fordelt i alle koran. 
        for korNavn in consts.bareKorNavn * 3:
            kor = Kor.objects.get(navn=korNavn)
            medlem = makeMedlem(kor, start, slutt, getRandomStemmegruppe(kor))
            if korNavn in consts.bareSmåkorNavn:
                storkor = Kor.objects.get(navn=[K for K, k in consts.småkorForStorkor.items() if korNavn in k][0])
                VervInnehavelse.objects.create(
                    medlem=medlem,
                    verv=getRandomStemmegruppe(storkor),
                    start=start,
                    slutt=slutt
                )

        for i in range(5):
            # Lag en par medlemma som ikkje er i noen kor
            makeMedlem()

        # Lag et Formann verv som man ikke får tilgang til uten tilgang tilgangen
        Verv.objects.create(
            navn='Formann',
            kor=Kor.objects.get(navn=consts.Kor.TSS)
        ).tilganger.set(Tilgang.objects.filter(kor__navn=consts.Kor.TSS))

        Verv.objects.create(
            navn='Lokfører',
            kor=Kor.objects.get(navn=consts.Kor.TSS)
        )

    def setTilganger(cls, tilgangKorNavn=[consts.Kor.TSS], tilgangNavn=[consts.Tilgang.vervInnehavelse]):
        # Gjør admin til ikke superbruker for å kunne avdekke flere edge cases. 
        cls.user.is_superuser = False
        cls.user.is_staff = False
        cls.user.save()
        # TODO: Her endre vi på hvilke tilganger admin har i praksis. 
        # For å unngå uforutsigbare resultater må vi enten få inn faktisk testisolering med transaction rollback, 
        # eller reverser denne endringen før testen (klassen) fullføre. 

        sekretær, created = Verv.objects.get_or_create(
            navn='Sekretær',
            kor=Kor.objects.get(navn=consts.Kor.TSS),
        )
        sekretær.tilganger.set(Tilgang.objects.filter(kor__navn__in=tilgangKorNavn, navn__in=tilgangNavn))

        VervInnehavelse.objects.get_or_create(
            verv=sekretær, 
            medlem=cls.medlem, 
            start=datetime.date.today() - datetime.timedelta(1),
            slutt=datetime.date.today() + datetime.timedelta(1)
        )

    @classmethod
    def setUpTestData(cls):
        mock_self = Mock()
        mock_self.stdout = StringIO()
        runSeed(mock_self)
        adminAdmin(mock_self)

        cls.user = User.objects.get(username='admin')
        cls.medlem = Medlem.objects.get(user=cls.user)
        cls.kor = Kor.objects.get(navn=consts.Kor.TSS)

        TilgangerTestCase.seed()
        TilgangerTestCase.setTilganger(cls)

    def assertFieldDisabled(self, field, reason=None, disabled=True):
        if not fieldIsVisible(field):
            # Hidden fields håndteres separat, dem treng vi ikkje bry oss med
            return
        
        self.assertEqual(field.disabled, disabled, f'Field {field.label} should ' + ('not ' if not disabled else '') + 'be disabled. ' + (reason if reason else ''))

    def assertFormDisabled(self, form, reason=None, disabled=True):
        for field in form.fields.values():
            self.assertFieldDisabled(field, reason=reason, disabled=disabled)

    def testMedlemSide(self):
        'Teste at vi får opp medlemmers side som vi skal, og kan sette TSS verv som ikke gir fleir tilganger enn vi har på de.'
        self.client.force_login(self.user)

        # Har ikke tilgang til en TKSer sin medlem side
        self.assertEqual(self.client.get(
            Medlem.objects.filter(
                vervInnehavelser__verv__kor__navn=consts.Kor.TKS
            ).first().get_absolute_url()
        ).status_code, 302) # Vi svare på manglende tilgang med redirects

        response = self.client.get(Medlem.objects.filter(
            ~Q(pk=self.medlem.pk),
            vervInnehavelser__verv__kor__navn=consts.Kor.TSS,
        ).first().get_absolute_url())

        # Har tilgang til en TSSer sin medlem side
        self.assertEqual(response.status_code, 200, response.request)

        # Har ikke tilgang til å rediger dataen demmers
        medlemForm = response.context['forms'][0]
        self.assertEqual(medlemForm.prefix, 'medlemdata')
        self.assertFormDisabled(medlemForm)

        # Har ikke tilgang til å rediger dekorasjonInnehavelser
        dekorasjonInnehavelseFormset = response.context['formsets'][1]
        self.assertEqual(dekorasjonInnehavelseFormset.prefix, 'dekorasjonInnehavelser')
        for form in dekorasjonInnehavelseFormset:
            self.assertFormDisabled(form)

        vervInnehavelseFormset = response.context['formsets'][0]
        self.assertEqual(vervInnehavelseFormset.prefix, 'vervInnehavelser')
        for form in vervInnehavelseFormset:
            # Har tilgang til å rediger usatte eller TSS vervInnehavelser
            if form.instance.pk and form.instance.kor.navn != consts.Kor.TSS:
                self.assertFormDisabled(form)
                continue
            self.assertFormDisabled(form, disabled=False)

            # Har ikke tilgang til å sette noen verv utenfor TSS
            self.assertFalse(
                form.fields['verv'].queryset.exclude(kor__navn=consts.Kor.TSS), 
                'Burde ikke ha tilgang til å sette verv utenfor TSS'
            )

            # Har ikke tilgang til å sette formann på vedkommende, 
            # grunnet det gir flere tilganger enn medlemmet har
            self.assertFalse(
                form.fields['verv'].queryset.filter(navn='Formann'), 
                'Burde ikke ha tilgang til å sette Formann på noen'
            )

    def vervInnehavelseFormsetKunTSSere(self, vervInnehavelseFormset):
        'Hjelpefunksjon som tar et vervInnehavelseFormset fra en Verv side og sjekke at man kan sett TSSera på dem.'
        for form in vervInnehavelseFormset:
            # Har kun tilgang til felt med TSSera
            if form.instance.pk and not VervInnehavelse.objects.filter(
                stemmegruppeVerv(includeDirr=True),
                medlem=form.instance.medlem,
            ).exists():
                self.assertFormDisabled(form)
                continue
            self.assertFormDisabled(form, disabled=False)

            # Har ikke tilgang til å sette noen utenfor TSS
            self.assertFalse(
                form.fields['medlem'].queryset.exclude(
                    vervInnehavelser__verv__kor__navn=consts.Kor.TSS
                ), 
                'Burde ikke ha tilgang til å sette verv utenfor TSS'
            )

    def testVervSideVervInnehavelseUtenTilganger(self):
        'Sjekk at man kan sett vervInnehavelsa for verv uten bredere tilganger på folk.'
        self.client.force_login(self.user)

        # Har ikke tilgang til et TKS verv sin side
        self.assertEqual(self.client.get(Verv.objects.filter(
            kor__navn=consts.Kor.TKS
        ).first().get_absolute_url()).status_code, 302) # Vi svare på manglende tilgang med redirects

        # Hent et TSS verv som har ingen tilganger
        response = self.client.get(Verv.objects.filter(
            kor__navn=consts.Kor.TSS,
            tilganger__isnull=True # Verv som har ingen tilganger
        ).first().get_absolute_url())

        # Har tilgang til vervet
        self.assertEqual(response.status_code, 200, response.request)

        vervInnehavelseFormset = response.context['formsets'][0]
        self.assertEqual(vervInnehavelseFormset.prefix, 'vervInnehavelse')
        self.vervInnehavelseFormsetKunTSSere(vervInnehavelseFormset)

    def testVervSideInnehavelseMedTilganger(self):
        'Sjekk at man ikkje kan sett vervInnehavelsa for verv med bredere tilganger på folk.'
        self.client.force_login(self.user)
        
        # Hent et TSS verv som har tilganger
        response = self.client.get(Verv.objects.filter(
            navn='Formann', # Formann som har flere tilganger enn brukeren
            kor__navn=consts.Kor.TSS
        ).first().get_absolute_url())

        # Har tilgang til vervet
        self.assertEqual(response.status_code, 200, response.request)

        vervInnehavelseFormset = response.context['formsets'][0]
        self.assertEqual(vervInnehavelseFormset.prefix, 'vervInnehavelse')
        for form in vervInnehavelseFormset:
            self.assertFormDisabled(form, reason='Vervet gir flere tilganger enn brukeren har.')

    def testVervSideInnehavelseMedTilgangerOgTilgang(self):
        'Sjekk at man kan sett vervInnehavelsa for verv med bredere tilganger på folk dersom man sjølv har Tilgang tilgangen'
        self.client.force_login(self.user)
        self.setTilganger(tilgangNavn=['vervInnehavelse', 'tilgang'])

        # Hent et TSS verv som har tilganger
        response = self.client.get(Verv.objects.filter(
            navn='Formann', # Formann har flere tilganger enn brukeren
            kor__navn=consts.Kor.TSS
        ).first().get_absolute_url())

        # Har tilgang til vervet
        self.assertEqual(response.status_code, 200, response.request)

        vervInnehavelseFormset = response.context['formsets'][0]
        self.assertEqual(vervInnehavelseFormset.prefix, 'vervInnehavelse')
        self.vervInnehavelseFormsetKunTSSere(vervInnehavelseFormset)

    def testVervSideInnehavelseTversAvKor(self):
        'Sjekk at med tversAvKor tilgangen skrudd på får man opp alle.'
        self.setTilganger(tilgangNavn=['vervInnehavelse', 'tversAvKor'])
        self.medlem.innstillinger = {'tversAvKor': True}
        self.medlem.save()
        self.client.force_login(self.user)

        # Hent et TSS verv som har ingen tilganger
        response = self.client.get(Verv.objects.filter(
            kor__navn=consts.Kor.TSS,
            tilganger__isnull=True # Verv som har ingen tilganger
        ).first().get_absolute_url())

        # Har tilgang til vervet
        self.assertEqual(response.status_code, 200, response.request)

        vervInnehavelseFormset = response.context['formsets'][0]
        self.assertEqual(vervInnehavelseFormset.prefix, 'vervInnehavelse')
        for form in vervInnehavelseFormset.forms:
            self.assertFormDisabled(form, reason='Burde ha tilgang til alle', disabled=False)
            self.assertFalse(
                Medlem.objects.all().exclude(pk__in=form.fields['medlem'].queryset.values_list('pk', flat=True)), 
                'Burde få opp alle herifra, også de som er fra andre kor eller ikke har et kor.'
            )

    def testVervSideBruktIKode(self):
        'Sjekk at man ikke har tilgang til å styre med verv som er bruktIKode'
        self.setTilganger(tilgangNavn=['verv'])
        self.client.force_login(self.user)

        # Hent et verv som e bruktIKode
        response = self.client.get(Verv.objects.filter(
            kor__navn=consts.Kor.TSS,
            bruktIKode=True
        ).first().get_absolute_url())

        # Har tilgang til siden
        self.assertEqual(response.status_code, 200, response.request)

        # Kan ikke slette det
        vervForm = response.context['forms'][0]
        self.assertEqual(vervForm.prefix, 'vervForm')
        self.assertFieldDisabled(vervForm.fields['navn'])
        self.assertFieldDisabled(vervForm.fields['DELETE'])
        self.assertNotIn('bruktIKode', vervForm.fields)

    def testVervSideIkkeBruktIKode(self):
        'Sjekk at man har tilgang til å styre med verv som ikke er bruktIKode'
        self.setTilganger(tilgangNavn=['verv'])
        self.client.force_login(self.user)

        # Hent et verv som ikkje e bruktIKode
        response = self.client.get(Verv.objects.filter(
            kor__navn=consts.Kor.TSS,
            bruktIKode=False,
            tilganger__isnull=True
            # TODO: Ideelt sett skulla man hatt lesetilgang for å sjå at det finnes et verv som hette 
            # formann med bare Verv tilgangen, ikkje veldig farlig tho, men ye. 
        ).first().get_absolute_url())

        # Har tilgang til siden
        self.assertEqual(response.status_code, 200, response.request)

        # Kan slette det
        vervForm = response.context['forms'][0]
        self.assertEqual(vervForm.prefix, 'vervForm')
        self.assertFieldDisabled(vervForm.fields['navn'], disabled=False)
        self.assertFieldDisabled(vervForm.fields['DELETE'], disabled=False)
        self.assertNotIn('bruktIKode', vervForm.fields)
