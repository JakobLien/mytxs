import os

from django.apps import apps
from django.db.models.signals import post_delete, pre_save, post_save
from django.db.models import FileField

from mytxs.signals.logSignals import recieverWithModels

fileModels = [m for m in apps.get_models() if any(map(lambda f: isinstance(f, FileField), m._meta.get_fields()))]

# https://stackoverflow.com/a/16041527
@recieverWithModels(post_delete, senders=fileModels)
def deleteFileOnDelete(sender, instance, **kwargs):
    'Slette en fil når instansen i databasen slettes'
    for field in sender._meta.get_fields():
        if isinstance(field, FileField):
            if fil := getattr(instance, field.name):
                if os.path.isfile(fil.path):
                    os.remove(fil.path)


@recieverWithModels(pre_save, senders=fileModels)
def deleteFileOnReplace(sender, instance, **kwargs):
    'Slette gamle fila når en ny fil lastes opp, for å unngå random characters på slutten'
    for field in sender._meta.get_fields():
        if isinstance(field, FileField):
            try:
                gammelFil = getattr(sender.objects.get(pk=instance.pk), field.name)
            except sender.DoesNotExist:
                return

            if gammelFil and gammelFil != getattr(instance, field.name):
                if os.path.isfile(gammelFil.path):
                    os.remove(gammelFil.path)


@recieverWithModels(post_save, senders=fileModels)
def fixFileNames(sender, instance, created, **kwargs):
    '''
    Endre opplastede filnavn til pk dersom instansen opprettes samtidig som fila og instance.pk gir None -> "None.mp3". 
    Dette gjør e mest for å unngå kompleksitet rundt tillate navn, endring av navn osv. 
    '''
    if not created:
        return

    for field in sender._meta.get_fields():
        if not isinstance(field, FileField):
            continue

        fil = getattr(instance, field.name)

        if not fil:
            continue

        name = str(instance.pk) + ('' if '.' not in fil.name else '.' + fil.name.split('.')[-1])

        if os.path.split(fil.name)[-1] == name:
            continue

        # Endre navn på sjølve fila
        os.rename(fil.path, os.path.join(*os.path.split(fil.path)[:-1], name))

        # Endre pathen til fila i modellen
        fil.name = os.path.join(*os.path.split(fil.name)[:-1], name)

        instance.save()
