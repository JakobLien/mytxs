from pathlib import Path
import subprocess
import re

from django.conf import settings
from django.contrib.staticfiles.management.commands.runserver import Command as RunServerCommand
from django.utils import autoreload
from django.utils.autoreload import autoreload_started


class Command(RunServerCommand):
    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            '--tw',
            action='store_true',
            help='Run Django development server with StatReloader running tailwindcss on relevant changes',
        )

    def repoRoot(self):
        return Path(__file__).parent.parent.parent.parent

    def runCommandOnChange(self, regexPath, command, preventReload=False):
        def callback(sender: autoreload.StatReloader, file_path, **kwargs):
            pathFromRepoRoot = str(file_path).replace(str(self.repoRoot()), '')
            if re.fullmatch(regexPath, pathFromRepoRoot):
                print(file_path, 'changed, running command.\n$', command)
                subprocess.Popen(command.split(' '))
                return preventReload
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
                r'/mytxs/(templates/.*|static/mytxs/(inputStyles\.css|static/mytxs/.*\.js))',
                'tailwindcss --cwd mytxs -i static/mytxs/inputStyles.css -o static/mytxs/styles.css --minify',
                preventReload=True
            )

            self.runCommandOnChange(
                r'/docs/index\.html',
                'tailwindcss --cwd docs -o styles.css --minify',
                preventReload=True
            )

        super().handle(*args, **options)
