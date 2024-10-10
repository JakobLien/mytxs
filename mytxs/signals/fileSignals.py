import os
from django.apps import apps
from django.db.models.signals import post_delete, pre_save
from django.db.models import FileField

from mytxs.models import Medlem
from mytxs.signals.logSignals import recieverWithModels

fileModels = [m for m in apps.get_models() if any(map(lambda f: isinstance(f, FileField), m._meta.get_fields()))]

# https://stackoverflow.com/a/16041527
@recieverWithModels(post_delete, senders=fileModels)
def auto_delete_file_on_delete(sender, instance, **kwargs):
    'Slette en fil når instansen i databasen slettes'
    for field in sender._meta.get_fields():
        if isinstance(field, FileField):
            if fil := getattr(instance, field.name):
                if os.path.isfile(fil.path):
                    os.remove(fil.path)

@recieverWithModels(pre_save, senders=fileModels)
def auto_delete_file_on_change(sender, instance, **kwargs):
    'Slette gamle fila når en ny fil lastes opp, for å unngå random characters på slutten'
    for field in sender._meta.get_fields():
        if isinstance(field, FileField):
            try:
                gammelFil = getattr(Medlem.objects.get(pk=instance.pk), field.name)
            except sender.DoesNotExist:
                return

            if gammelFil and gammelFil != getattr(instance, field.name):
                if os.path.isfile(gammelFil.path):
                    os.remove(gammelFil.path)
