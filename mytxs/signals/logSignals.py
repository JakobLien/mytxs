from django.dispatch import receiver
from django.db.models.signals import post_delete, pre_save, post_save, m2m_changed

from mytxs.models import Dekorasjon, DekorasjonInnehavelse, Kor, Logg, Tilgang, Verv, VervInnehavelse

import json

from django.forms.models import model_to_dict

from itertools import chain

from django.core import serializers

# # Modifisert versjon av django.forms.models.model_to_dict hentet herifra
# # https://stackoverflow.com/a/29088221/6709450
# # Forskjellen er at denne serialiserer manyToMany relations som en liste, som automatisk kan konverteres til JSON
# def to_dict(instance, fields=None, exclude=None):
#     opts = instance._meta
#     data = {}
#     for field in chain(opts.concrete_fields, opts.private_fields):
#         if fields is not None and field.name not in fields:
#             continue
#         if exclude and field.name in exclude:
#             continue
#         data[field.name] = field.value_from_object(instance)
#     for field in opts.many_to_many:
#         if fields is not None and field.name not in fields:
#             continue
#         if exclude and field.name in exclude:
#             continue
#         data[field.name] = [i.id for i in field.value_from_object(instance)]
#     return data

@receiver(post_save, sender=Verv)
@receiver(post_save, sender=VervInnehavelse)
@receiver(post_save, sender=Dekorasjon)
@receiver(post_save, sender=DekorasjonInnehavelse)
@receiver(post_save, sender=Tilgang)
def log_create(sender, instance, created, **kwargs):
    # This is not incorporated into pre_save to make the 
    # resulting json object include a set id

    if created:
        print(f'log_create: {instance}')

        Logg.objects.create(
            model=sender.__name__,
            instancePK=instance.pk,
            change=Logg.CREATE_CHANGE,
            value=json.loads(serializers.serialize("jsonl", [instance])),
            kor=getattr(instance, 'kor', None)
        )
    else:
        print(f'log_update: {instance}')

        Logg.objects.create(
            model=sender.__name__,
            instancePK=instance.pk,
            change=Logg.UPDATE_CHANGE,
            value=json.loads(serializers.serialize("jsonl", [instance])),
            kor=getattr(instance, 'kor', None)
        )

@receiver(post_delete, sender=Verv)
@receiver(post_delete, sender=VervInnehavelse)
@receiver(post_delete, sender=Dekorasjon)
@receiver(post_delete, sender=DekorasjonInnehavelse)
@receiver(post_delete, sender=Tilgang)
def log_delete(sender, instance, **kwargs):
    print(f'log_delete: {instance}')

    # This is deletion
    Logg.objects.create(
        model=sender.__name__,
        instancePK=instance.pk,
        change=Logg.DELETE_CHANGE,
        value=json.loads(serializers.serialize("jsonl", [instance])),
        kor=getattr(instance, 'kor', None)
    )

# def logSave(oldInstance, newInstance):
#     # Å importer Logging modellen hadd vært circular import
#     Logging = apps.get_model('mytxs', 'Logging')

#     Logging.objects.create(
#         model=type(newInstance).__name__,
#         instancePK=newInstance.pk,
#         value=serializers.serialize("jsonl", [newInstance])
#     )

# def logDelete(instance):
#     # Å importer Logging modellen hadd vært circular import
#     Logging = apps.get_model('mytxs', 'Logging')

#     Logging.objects.create(
#         model=type(instance).__name__,
#         instancePK=instance.pk,
#         value=serializers.serialize("jsonl", [instance])
#     )




# Fiks så logs har rett relations

# Pr no produsere vi logs ved å override save og delete methods i utils/log.py
# Dette fikse ikkje at relasjoner på logsa er korrekt, så gjør det her
# Må altså gitt alle mulige argument, gå inn og fiks at relasjonan stemme

@receiver(m2m_changed, sender=Verv.tilganger.through)
def log_m2m_changed(sender, instance, action, reverse, model, pk_set, **kwargs):

    #print(f'{sender} {instance} {action} {reverse} {model} {pk_set}')

    # TODO: Om vi bare lagre sender med keys i rett rekkefølge har vi det:)

    if action == 'post_add':
        for key in pk_set:
            if not reverse:
                print(f'Adding {instance.pk} {key}')
            else:
                print(f'Adding {key} {instance.pk} ')

    elif action == 'post_remove':
        for key in pk_set:
            if not reverse:
                print(f'Removing {instance.pk} {key}')
            else:
                print(f'Removing {key} {instance.pk} ')

    elif action == 'post_clear':
        print(f'Clearing {instance.pk} {pk_set}')


        #     log = Logging.objects.filter(
        #         model=sender._meta.auto_created.__name__, 
        #         instancePK=instance.pk
        #     ).order_by('-timeStamp').first()


        #     print(log.newValue)

        #     log.newValue = to_dict(instance)

        #     print(log.newValue)

        #     log.save()

        #     # Dette printe forskjellen e treng. 
        #     # print(f'log_m2m_changed: {to_dict(instance)}')
        #     # print(f'{sender} {instance} {action} {reverse} {model}')

        # else:
        #     print(f'YIKES: {instance}')
