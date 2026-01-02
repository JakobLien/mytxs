from django.test import SimpleTestCase
from mytxs.utils.modelUtils import gjettStemmegruppe

testCases = [
    ('Slutkör A2.mp3', '2A'),
    ('Aquaviten S1.mp3', '1S'),
    ('Gammelt øl 1B', '1B'),
    ('Unicornis Captivatur-alt1.MID', '1A'),
    ('Fædrelandssang Alle.mp3', ''),
    ('Fredmans epistel nr 9 Stemmefil.sib', ''),
    ('Fredmans epistel nr 13 (2014-02) T2.mp3', '2T'),
    ('2A', '2A'),
    ('A2', '2A')
]

class DekorasjonOvervalørTestCase(SimpleTestCase):
    def testGjettStemmegruppe(self):
        for param, answer in testCases:
            self.assertEquals(gjettStemmegruppe(param), answer)
