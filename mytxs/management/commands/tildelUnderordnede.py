from django.core.management.base import BaseCommand

from mytxs.management.commands.updateField import objectsGenerator
from mytxs.models import DekorasjonInnehavelse
from mytxs.utils.modelUtils import kanHaUnderordnet, harUnderordnet


def tildelAlleUnderordnede(dekorasjonInnehavelse):
    '''
    Tildeler alle manglende underordnede dekorasjoner.
    Lagring av nye innehavelser gjøres i omvendt topologisk sortert 
    rekkefølge (laveste valør først) for å passere validering.
    '''
    nyeInnehavelser = []
    nåværende = dekorasjonInnehavelse
    while kanHaUnderordnet(nåværende) and not harUnderordnet(nåværende):
        ny = DekorasjonInnehavelse(
            medlem=nåværende.medlem,
            dekorasjon=nåværende.dekorasjon.erOverordnet,
            start=nåværende.start
        )
        nyeInnehavelser.append(ny)
        nåværende = ny
    for innehavelse in reversed(nyeInnehavelser):
        innehavelse.save()


class Command(BaseCommand):
    help = 'tildel underordnede dekorasjoner til alle medlemmer som mangler det'

    def handle(self, *args, **options):
        for instance in objectsGenerator(DekorasjonInnehavelse.objects.all()):
            tildelAlleUnderordnede(instance)
