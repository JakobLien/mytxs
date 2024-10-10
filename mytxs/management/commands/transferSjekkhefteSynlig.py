from django.core.management.base import BaseCommand

from mytxs.management.commands.updateField import objectsGenerator
from mytxs.models import Medlem

class Command(BaseCommand):
    help = 'Dette kjøre en gong hvert minutt på serveren, da får vi cron jobs på prosjektet:)'

    def handle(self, *args, **options):
        for medlem in objectsGenerator(Medlem.objects.all()):
            medlem.innstillinger['sjekkhefteSynlig'] = medlem.sjekkhefteSynlig
