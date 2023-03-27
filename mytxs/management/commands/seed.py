from django.core.management.base import BaseCommand
from mytxs.models import *

class Command(BaseCommand):
    help = "seed database for testing and development."

    # def add_arguments(self, parser):
    #     parser.add_argument('--mode', type=str, help="Mode")

    def handle(self, *args, **options):
        self.stdout.write('seeding data...')
        run_seed(self)
        self.stdout.write('done.')

def run_seed(self):
    """ Seed database based on mode

    :param mode: refresh / clear 
    :return:
    """

    kortTittel = ["TSS", "P", "KK", "C", "TKS"]
    langTittel = [
		"Trondhjems Studentersangforening",
		"Pirum",
		"Knauskoret",
		"Candiss",
		"Trondhjems Kvinnelige Studentersangforening"
    ]

    korTilStemmeFordeling = [0, 0, 1, 2, 2]
    stemmeFordeling = [
        ["1T", "2T", "1B", "2B"], 
        ["1S", "2S", "1A", "2A", "1T", "2T", "1B", "2B"], 
        ["1S", "2S", "1A", "2A"]
    ]
	
    for i in range(5):
        # Opprett korene
        kor, korCreated = Kor.objects.get_or_create(pk=i, defaults={"kortTittel":kortTittel[i], "langTittel":langTittel[i]})
        if(korCreated):
            self.stdout.write("Created kor " + kor.kortTittel + " at id " + kor.pk)

        # Opprett aktiv-tilgangen
        aktivTilgang, aktivTilgangCreated = Tilgang.objects.get_or_create(navn=kor.kortTittel+"-aktiv")

        # For hver stemmegruppe i koret, opprett stemmegruppeverv, og gi de tilgangen om de ikke har det alt. 
        for stemmeGruppe in stemmeFordeling[korTilStemmeFordeling[i]]:
            stemmeGruppeVerv, stemmeGruppeVervCreated = kor.verv.get_or_create(navn=stemmeGruppe)
            if(stemmeGruppeVervCreated):
                self.stdout.write("Created verv " + stemmeGruppeVerv.navn + " for kor " + kor.kortTittel + " at id " + str(stemmeGruppeVerv.pk))

            stemmeGruppeVerv.tilganger.add(aktivTilgang)
        
        # Opprett vervInnehavelse tilgangen
        vervInnehavelseTilgang, vervInnehavelseTilgangCreated = Tilgang.objects.get_or_create(navn=kor.kortTittel+"-vervInnehavelse")
        if vervInnehavelseTilgangCreated:
            print("Created tilgang " + vervInnehavelseTilgang.navn)

        # Opprett daljeInnehavelse tilgangen
        daljeInnehavelseTilgang, daljeInnehavelseTilgangCreated = Tilgang.objects.get_or_create(navn=kor.kortTittel+"-daljeInnehavelse")
        if daljeInnehavelseTilgangCreated:
            print("Created tilgang " + daljeInnehavelseTilgang.navn)

        
