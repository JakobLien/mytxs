import datetime

from django.test import SimpleTestCase
from mytxs.templateTags import alder

testCases = [
    # (fødselsdato, dato, forventet alder)
    (datetime.date(2000, 5, 17), datetime.date(2026, 5, 16), 25),
    (datetime.date(2000, 5, 17), datetime.date(2026, 5, 17), 26),
    (datetime.date(2000, 5, 17), datetime.date(2026, 12, 31), 26),
    (datetime.date(2000, 12, 31), datetime.date(2026, 1, 1), 25),
    (datetime.date(2004, 2, 29), datetime.date(2026, 2, 28), 21),
    (datetime.date(2004, 2, 29), datetime.date(2026, 3, 1), 22),
]

class SjekkheftetAlderTestCase(SimpleTestCase):
    def testAlder(self):
        for fødselsdato, dato, answer in testCases:
            self.assertEqual(alder(fødselsdato, dato), answer)

    def testIngenFødselsdato(self):
        self.assertEqual(alder(None), '')
