
import os
from django.dispatch import receiver
from django.db.models.signals import post_delete, pre_save

from mytxs.models import Medlem

# https://stackoverflow.com/a/16041527
@receiver(post_delete, sender=Medlem)
def auto_delete_file_on_delete(sender, instance, **kwargs):
    """
    Deletes file from filesystem
    when corresponding `MediaFile` object is deleted.
    """

    if instance.bilde:
        if os.path.isfile(instance.bilde.path):
            os.remove(instance.bilde.path)

@receiver(pre_save, sender=Medlem)
def auto_delete_file_on_change(sender, instance, **kwargs):
    """
    Deletes old file from filesystem
    when corresponding `MediaFile` object is updated
    with new file.
    """
    if not instance.pk:
        return

    try:
        old_file = Medlem.objects.get(pk=instance.pk).bilde
    except Medlem.DoesNotExist:
        return

    new_file = instance.bilde
    if old_file and not old_file == new_file:
        if os.path.isfile(old_file.path):
            os.remove(old_file.path)
