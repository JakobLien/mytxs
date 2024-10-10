from django.core.management.base import BaseCommand

from mytxs.management.commands.updateField import objectsGenerator
from mytxs.models import Medlem

class Command(BaseCommand):

    help = 'Command som clearer emnekoder-charfieldet til hvert medlem, ved semesterslutt.'

    def handle(self, *args, **options):
        for medlem in objectsGenerator(Medlem.objects.all()):
            medlem.emnekoder = ''