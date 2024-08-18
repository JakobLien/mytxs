from django.core.management.base import BaseCommand

from mytxs.management.commands.updateField import objectsGenerator
from mytxs.models import DekorasjonInnehavelse


def manglerUndervalør(innehavelse):
    return hasattr(innehavelse.dekorasjon, 'undervalør') and not innehavelse.innehavelse.dekorasjon.undervalør.dekorasjonInnehavelser.filter(medlem__id=innehavelse.medlem.id).exists()


def tildelUndervalører(dekorasjonInnehavelse):
    '''
    Tildeler alle manglende underordnede dekorasjoner.
    Lagring av nye innehavelser gjøres i omvendt topologisk sortert 
    rekkefølge (laveste valør først) for å passere validering.
    '''
    nyeInnehavelser = []
    nåværende = dekorasjonInnehavelse
    while manglerUndervalør(nåværende):
        ny = DekorasjonInnehavelse(
            medlem=nåværende.medlem,
            dekorasjon=nåværende.dekorasjon.undervalør,
            start=nåværende.start
        )
        nyeInnehavelser.append(ny)
        nåværende = ny
    for innehavelse in reversed(nyeInnehavelser):
        innehavelse.save()


class Command(BaseCommand):
    help = 'tildel undervalør til alle medlemmer som mangler det'

    def handle(self, *args, **options):
        for instance in objectsGenerator(DekorasjonInnehavelse.objects.all()):
            tildelUndervalører(instance)
