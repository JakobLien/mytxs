import datetime
from django.test import TestCase
from django.urls import reverse

from mytxs.models import Kor, Medlem, Tilgang, Verv, VervInnehavelse

from django.contrib.auth.models import User

# Create your tests here.

class ModelTests(TestCase):
    kortTittel = ['TSS', 'P', 'KK', 'C', 'TKS']
    langTittel = [
        'Trondhjems Studentersangforening',
        'Pirum',
        'Knauskoret',
        'Candiss',
        'Trondhjems Kvinnelige Studentersangforening'
    ]

    korTilStemmeFordeling = [0, 0, 1, 2, 2]
    stemmeFordeling = [
        ['1T', '2T', '1B', '2B'], 
        ['1S', '2S', '1A', '2A', '1T', '2T', '1B', '2B'], 
        ['1S', '2S', '1A', '2A']
    ]

    def setUp(self):
        peder = Medlem.objects.create(
            fornavn='Peder', 
            etternavn='Hoås', 
            user=User.objects.create_user(
                'peder', 'peder@example.com', 'testUser'
            )
        )
        hilde = Medlem.objects.create(
            fornavn='Hilde', 
            mellomnavn='Anne', 
            etternavn='Mellow'
        )
        
        for i in range(5):
            # Opprett korene
            kor = Kor.objects.create(pk=i, kortTittel=self.kortTittel[i], langTittel=self.langTittel[i])

            # Opprett aktiv-tilgangen
            aktivTilgang = Tilgang.objects.create(navn=kor.kortTittel+'-aktiv')

            # For hver stemmegruppe i koret, opprett stemmegruppeverv, og gi de tilgangen om de ikke har det alt. 
            for stemmegruppe in self.stemmeFordeling[self.korTilStemmeFordeling[i]]:
                stemmegruppeVerv = kor.verv.create(navn=stemmegruppe)
                stemmegruppeVerv.tilganger.add(aktivTilgang)
            
            dirVerv = kor.verv.create(navn='Dirigent')

            dirVerv.tilganger.add(aktivTilgang)

        # Sett folk inn i stemmegrupper
        VervInnehavelse.objects.create(
            verv=Verv.objects.get(kor__kortTittel='TSS', navn='2B'), 
            medlem=peder, 
            start=datetime.date(2010, 2, 4), 
            slutt=datetime.date.today()
        )

        VervInnehavelse.objects.create(
            verv=Verv.objects.get(kor__kortTittel='KK', navn='1B'), 
            medlem=peder, 
            start=datetime.date(2012, 2, 4), 
            slutt=datetime.date(2014, 2, 4)
        )

        VervInnehavelse.objects.create(
            verv=Verv.objects.get(kor__kortTittel='P', navn='1B'), 
            medlem=peder, 
            start=datetime.date(2020, 2, 4), 
            slutt=datetime.date.today()
        )

        VervInnehavelse.objects.create(
            verv=Verv.objects.get(kor__kortTittel='TKS', navn='1S'), 
            medlem=hilde, 
            start=datetime.date(1990, 6, 12), 
            slutt=datetime.date.today()
        )

        VervInnehavelse.objects.create(
            verv=Verv.objects.get(kor__kortTittel='KK', navn='2S'), 
            medlem=hilde, 
            start=datetime.date(1995, 6, 12), 
            slutt=datetime.date(1998, 5, 4)
        )


    def testModels(self):
        'Medlem properties'
        peder = Medlem.objects.get(fornavn='Peder')
        hilde = Medlem.objects.get(fornavn='Hilde')
        
        self.assertEqual(peder.navn, 'Peder Hoås')
        self.assertEqual(peder.storkor, Kor.objects.get(kortTittel='TSS'))
        self.assertEqual(peder.karantenekor, 'K10')
        self.assertSetEqual(set(peder.tilganger), {'TSS-aktiv', 'P-aktiv'})

        self.assertEqual(hilde.navn, 'Hilde Anne Mellow')
        self.assertEqual(hilde.storkor, Kor.objects.get(kortTittel='TKS'))
        self.assertEqual(hilde.karantenekor, 'K1990')
        self.assertSetEqual(set(hilde.tilganger), {'TKS-aktiv'})

        # Test annotateFulltNavn
        medlemmer = Medlem.objects.annotateFulltNavn()

        for medlem in medlemmer:
            self.assertEqual(medlem.fullt_navn, medlem.navn)

    def testSjekkheftet(self):
        peder = Medlem.objects.get(fornavn='Peder')
        hilde = Medlem.objects.get(fornavn='Hilde')

        # Vi må logg inn med en user som har et medlem, slik at det funke i templates der vi har user.medlem...
        self.client.force_login(peder.user)

        for kor in Kor.objects.all():
            # Issue a GET request.
            response = self.client.get(reverse('sjekkheftet', kwargs={'gruppe': kor.kortTittel}))

            # Check that the response is 200 OK.
            self.assertEqual(response.status_code, 200)

            # Sjekk at vi får (minst) de andre korene som grupper
            for kortTittel in self.kortTittel:
                self.assertIn(kortTittel, response.context['grupper'])

            # Sjekk at vi har rett stemmegrupper
            self.assertListEqual(list(response.context['grupperinger'].keys()), [verv.navn for verv in kor.stemmegruppeVerv])

            # Sjekk at vi har rett medlemmer i stemmegruppene
            for stemmegruppeNavn, stemmegruppeMedlemmer in response.context['grupperinger'].items():
                self.assertSetEqual(stemmegruppeMedlemmer, Medlem.objects.filter(
                    vervInnehavelse__verv__navn=stemmegruppeNavn,
                    vervInnehavelse__verv__kor=kor,
                    vervInnehavelse__start__lte=datetime.date.today(),
                    vervInnehavelse__slutt__gte=datetime.date.today()
                ))