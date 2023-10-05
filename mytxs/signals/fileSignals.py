import os
from django.dispatch import receiver
from django.db.models.signals import post_delete, pre_save

from mytxs.models import Medlem

# Håndtering av opplastning og overskriving av bilder
# Gjør at ImageField lagres som nr i rett mappe
# https://stackoverflow.com/a/16041527
@receiver(post_delete, sender=Medlem)
def auto_delete_file_on_delete(sender, instance, **kwargs):
    'Slette Medlem bilde når medlemmet slettes'
    if instance.bilde:
        os.remove(instance.bilde.path)


@receiver(pre_save, sender=Medlem)
def auto_delete_file_on_change(sender, instance, **kwargs):
    '''
    Slette Medlem bilde fra filsystemet når de laste opp et nytt bilde.
    Om ikke dette gjøres får filnavnet (medlem.pk) ekstra characters på slutten,
    som ikke endre koss det funke for resten av appen, men ser stygt ut.
    '''
    try:
        gammeltBilde = Medlem.objects.get(pk=instance.pk).bilde
    except Medlem.DoesNotExist:
        return

    new_file = instance.bilde
    if gammeltBilde and not gammeltBilde == new_file:
        if os.path.isfile(gammeltBilde.path):
            os.remove(gammeltBilde.path)
