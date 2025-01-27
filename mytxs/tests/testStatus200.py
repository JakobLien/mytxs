from io import StringIO
import re
from unittest.mock import Mock

from django.test import TestCase

from mytxs.management.commands.seed import adminAdmin, runSeed
from mytxs.models import *


def getUrlFromText(html, linkText):
    'Skaffe URLen fra en link gitt tekst'
    # Ja e veit, vær forsiktig med kjøretid på regular expression pattern matching, men
    # - Disse testan ska bare kjør lokalt (evt på Github), så det vil ikke ha nån innvirkning på prod. 
    # - E kjørt denne matchen på en ish tom semesterplan side og fann en lenke 100k gong på 4 sekund. 
    # - E ønske virkelig ikkje å begynn med HTML parsing i større grad enn dette, hvilket e trur uansett bli treigar. 
    NCB = '[^>]*?' # Not closing bracket
    NCT = '((?!</a>).)*' # Not closing tag
    match = re.compile(f'<a{NCB}href="({NCB})"{NCB}>{NCT}{linkText}{NCT}</a>', flags=re.DOTALL).search(html)
    if match:
        return match.groups()[0]


class Status200TestCase(TestCase):
    '''
    Dette e en ganske grunnleggende testfil, bare for å sjå ka Django kan gjør. Denne tråkke 
    gjennom requests med Django sin client, bare for å sjå at en del sida returne noko med 
    status code 200. Sjekke også at medlem kan rediger seg sjølv, og at man kan meld seg opp 
    te jobbvakta. 
    '''
    @classmethod
    def setUpTestData(cls):
        # Hver test kjøre i en transaction som rollbacke te dette, veldig effektivt. 
        mock_self = Mock()
        mock_self.stdout = StringIO()
        runSeed(mock_self)
        adminAdmin(mock_self)

    def login(self):
        return self.client.post('', {'username': 'admin', 'password': 'admin'}, follow=True)

    def followLink(self, res, linkText, follow=False):
        url = getUrlFromText(res.content.decode(), linkText)
        if not url:
            raise AssertionError('URL not found')
        url = url.replace('&amp;', '&')
        if url.startswith('?'):
            url = res.request['PATH_INFO'] + url
        return self.client.get(url, follow=follow)

    def testLogin(self):
        res = self.login()
        self.assertIn('Login successful', res.content.decode())
        self.assertEqual(res.status_code, 200)

    def testSjekkheftet(self):
        self.login()
        res = self.client.get('/sjekkheftet/TSS')

        for linkText in ['TKS', 'Knauskoret', 'Søk', 'Kart', 'Jubileum', 'SjekkhefTest', 'FellesEmner']:
            res = self.followLink(res, linkText)

            self.assertEqual(res.status_code, 200, msg=linkText)

    def testSemesterplan(self):
        self.login()
        semesterplanRes = self.client.get('/semesterplan/TSS')

        for linkText in ['Knauskoret', 'Kalenderfeed lenke']:
            res = self.followLink(semesterplanRes, linkText)

            self.assertEqual(res.status_code, 200, msg=linkText)

        Hendelse.objects.create(
            navn='[#2] Barvakt', 
            kor=Kor.objects.filter(navn='Sangern').first(),
            kategori=Hendelse.UNDERGRUPPE,
            startDate=datetime.date.today()
        )

        jobbVakterRes = self.followLink(semesterplanRes, 'Jobbvakter')

        jobbVakterRes2 = self.followLink(jobbVakterRes, 'Påmeld', follow=True)

        self.assertIn('Avmeld', jobbVakterRes2.content.decode())

    def testRedigerData(self):
        self.login()
        res = self.client.get('/medlem/1')
        self.assertEqual(res.status_code, 200)

        res = self.client.post('/medlem/1', {
            'medlemdata-fornavn': 'admin', 
            'medlemdata-mellomnavn': 'MELLOMNAVN', 
            'medlemdata-etternavn': 'adminsen',
            'medlemdata-fødselsdato': '2000-01-01'
        }, follow=True)

        self.assertEqual(res.status_code, 200)

        medlem = Medlem.objects.filter(pk=1).first()

        self.assertEqual(medlem.fornavn, 'admin')
        self.assertEqual(medlem.mellomnavn, 'MELLOMNAVN')
        self.assertEqual(medlem.etternavn, 'adminsen')
        self.assertEqual(medlem.fødselsdato, datetime.date(2000, 1, 1))
