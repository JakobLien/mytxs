from django.core.management.base import BaseCommand

from mytxs.management.commands.transferNotearkiv import splitAlphaNumeric

from mytxs.models import *

class Command(BaseCommand):
    help = 'Pull data from the old site, using key specified in .env'

    def handle(self, *args, **options):

        print('Hello World')

        medlemmer = Medlem.objects.all()

        medlemmer = medlemmer.annotateFravær(consts.Kor.TSS)

        # medlemmerMedNavnTest = medlemmer.filter(mellomnavn='test')
        # medlemmerMedNavnAdmin = medlemmerMedNavnTest.filter(fornavn='admin')

        # print(medlemmerMedNavnAdmin.query)


        m = medlemmer.first()

        print(Verv.objects.filter(vervInnehavelser__medlem=m))

        print(Medlem.objects.filter(
            stemmegruppeVerv('vervInnehavelser__verv'),
            vervInnehavelseAktiv(),
            vervInnehavelser__verv__kor__navn=consts.Kor.TSS,
        ).query)


        # stemmegrupper = {'sopran': 'S', 'alt': 'A', 'tenor': 'T', 'bass': 'B'}
        # for k, v in dict(**stemmegrupper).items():
        #     stemmegrupper[k[:3]] = v
        #     stemmegrupper[k[:1]] = v


        # # Prøv å gjett på stemmegruppe, vanskelig men hadd vært veldig nice
        # filNavnUtenSangNavn = splitAlphaNumeric("asdf 12 bass 12 ")

        # for i, aplhaNumeric in enumerate(filNavnUtenSangNavn):
        #     if aplhaNumeric in stemmegrupper.keys():
        #         stemmegruppe = stemmegrupper[aplhaNumeric]
        #         # Flytt så vi har lista før stemmegruppa baklengs 
        #         filNavnUtenSangNavn = [*filNavnUtenSangNavn[i::-1][1:], *filNavnUtenSangNavn[i+1:]]

        #         for part in filNavnUtenSangNavn:
        #             if part.isnumeric() and 1 <= int(part) <= 2:
        #                 stemmegruppe += part
        #                 if len(stemmegruppe) >= 3:
        #                     break
                
        #         stemmegruppe = stemmegruppe[::-1]

        #         print(stemmegruppe)

        #         break
