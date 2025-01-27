from django.core.management.base import BaseCommand

from mytxs.models import DekorasjonInnehavelse, Dekorasjon


class Command(BaseCommand):
    help = '''
    Bruk: python manage.py setOvervalør undervalørPk overvalørPk
    Definer overvalørPk som overvalør for undervalørPk, og gjør nødvendige endringer i dekorasjonsinnehavelser.
    Eksempel: undervalørPk er pk for "VM i fotball (bronse)", overvalørPk er pk for "VM i fotball (sølv)".
    Tildeler undervalør til alle som kun har overvalør. Startdato settes da til den samme som startdato for overvalørinnehavelsen.
    Medlemmer som kun har undervalør, tildeles ikke overvalør, naturligvis.
    Dersom noen medlemmer har både undervalør og overvalør fra før, men startdato for undervalør er senere enn overvalørs startdato (altså ugyldig), settes startdato for undervalør til overvalør sin startdato.
    Hvis undervalørPk allerede har en overvalør eller overvalørPk har en undervalør, gjøres ingenting.
    '''

    def add_arguments(self, parser):

        parser.add_argument("undervalørPk", nargs=None, type=int)
        parser.add_argument("overvalørPk", nargs=None, type=int)

    def handle(self, *args, **options):

        undervalørPk = options["undervalørPk"]
        overvalørPk = options["overvalørPk"]

        undervalør = Dekorasjon.objects.get(id=undervalørPk)
        overvalør = Dekorasjon.objects.get(id=overvalørPk)

        prompt = input(f"Vil du gjøre {str(undervalør)} undervalør av {str(overvalør)}? y/n\n")
        if prompt != "y":
            return

        if hasattr(undervalør, "overvalør") and undervalør.overvalør is not None:
            print(f"Ingenting gjøres fordi {str(undervalør)} allerede har overvaløren {str(undervalør.overvalør)}")
            return
        elif hasattr(overvalør, "undervalør") and overvalør.undervalør is not None:
            print(f"Ingenting gjøres fordi {str(overvalør)} allerede har undervaløren {str(overvalør.undervalør)}")
            return

        for overvalørInnehavelse in DekorasjonInnehavelse.objects.filter(dekorasjon=overvalørPk):
            undervalørInnehavelse = DekorasjonInnehavelse.objects.filter(dekorasjon=undervalørPk, medlem=overvalørInnehavelse.medlem).first()
            if undervalørInnehavelse is None:
                print(f"Tildeler {str(overvalørInnehavelse.medlem)} manglende undervalør {str(undervalør)} fordi hen allerede har overvaløren {str(overvalør)}. Bruker overvalørinnehavelsens startdato: {overvalørInnehavelse.start}")
                DekorasjonInnehavelse.objects.create(dekorasjon_id=undervalørPk, medlem=overvalørInnehavelse.medlem, start=overvalørInnehavelse.start)
            elif undervalørInnehavelse.start > overvalørInnehavelse.start:
                print(f"Endrer ugyldig startdato {undervalørInnehavelse.start} for {str(undervalørInnehavelse)} til {str(overvalørInnehavelse)} sin startdato {overvalørInnehavelse.start}")
                undervalørInnehavelse.start = overvalørInnehavelse.start
                undervalørInnehavelse.save()

        undervalør.overvalør = overvalør
        undervalør.save()
