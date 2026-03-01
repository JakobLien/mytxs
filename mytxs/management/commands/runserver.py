from pathlib import Path
import subprocess
import re

from django.conf import settings
from django.contrib.staticfiles.management.commands.runserver import Command as RunServerCommand
from django.utils import autoreload
from django.utils.autoreload import autoreload_started


class Command(RunServerCommand):
    help = "Run Django development server with Tailwind CSS watch mode"

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            '--tw',
            action='store_true',
            help='Automatisk oppdater styles.css filer når relevante filer endres.',
        )

    def repoRoot(self):
        return Path(__file__).parent.parent.parent.parent

    def runCommandOnChange(self, regexPath, command):
        def callback(sender: autoreload.StatReloader, file_path, **kwargs):
            pathFromRepoRoot = str(file_path).replace(str(self.repoRoot()), '')
            if re.fullmatch(regexPath, pathFromRepoRoot): # Sjekk om vi faktisk må kjør tailwind.
                subprocess.Popen(command.split(' '))
                autoreload.trigger_reload(file_path)
            return None # Don't suppress other handlers
        autoreload.file_changed.connect(callback)

    def handle(self, *args, **options):
        if settings.DEBUG and options['tw']:
            # Vi treng å legg til en par ekstra filer manuelt. 
            def watchExtra(sender: autoreload.StatReloader, **kwargs):
                sender.extra_files.add(self.repoRoot() / 'docs/index.html')
                sender.extra_files.add(self.repoRoot() / 'mytxs/static/mytxs/inputStyles.css')
                sender.watch_dir(self.repoRoot() / 'mytxs/static/mytxs', '**/*.js')
            autoreload_started.connect(watchExtra)

            self.runCommandOnChange(
                '/mytxs/(templates/.*|static/mytxs/(inputStyles\.css|static/mytxs/.*\.js))',
                'tailwindcss --cwd mytxs -i static/mytxs/inputStyles.css -o static/mytxs/styles.css --minify'
            )

            self.runCommandOnChange(
                '/docs/index\.html',
                'tailwindcss --cwd docs -o styles.css --minify'
            )

        super().handle(*args, **options)
