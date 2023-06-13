from django.dispatch import receiver
from django.db.models.signals import post_delete, post_save, m2m_changed

from mytxs.models import Dekorasjon, DekorasjonInnehavelse, Kor, Logg, LoggM2M, Tilgang, Verv, VervInnehavelse

from itertools import chain

from django.db.models.fields.related import RelatedField

from django.apps import apps

# Modifisert versjon av django.forms.models.model_to_dict delvis hentet herifra 
# https://stackoverflow.com/a/29088221/6709450 (#5)
# Forskjellen er at denne serialiserer ikke manyToMany relations, den tar med editable=False fields
# og erstatter den foreign keys med pk av tilsvarende logg instance, eller str representasjon av objektet
# når loggen ikke finens (som for Medlem loggs)
def to_dict(instance, fields=None, exclude=None):
    opts = instance._meta
    data = {}
    for field in chain(opts.concrete_fields, opts.private_fields):
        if fields is not None and field.name not in fields:
            continue
        if exclude and field.name in exclude:
            continue

        if isinstance(field, RelatedField):
            if logg := Logg.objects.getLoggFor(getattr(instance, field.name)):
                # Om det er en relasjon, lagre pk av den nyeste relaterte loggen (ikke av instansen)
                data[field.name] = logg.pk
            else:
                # Om vi ikke finn den relevante loggen, lagre string representasjon av objektet
                data[field.name] = str(getattr(instance, field.name))
        elif type(field.value_from_object(instance)) not in [str, int, float, bool, None]:
            # Om det ikke er en relasjon, men er et objekt, lagre string representasjon av objektet, f.eks. for Date
            data[field.name] = str(field.value_from_object(instance))
        else:
            # Ellers, lagre det som er naturlig.
            data[field.name] = field.value_from_object(instance)
    return data

@receiver(post_save, sender=Verv)
@receiver(post_save, sender=VervInnehavelse)
@receiver(post_save, sender=Dekorasjon)
@receiver(post_save, sender=DekorasjonInnehavelse)
@receiver(post_save, sender=Tilgang)
def log_create(sender, instance, created, **kwargs):
    if created:
        Logg.objects.create(
            model=sender.__name__,
            instancePK=instance.pk,
            change=Logg.CREATE,
            value=to_dict(instance),
            strRep=str(instance),
            kor=Kor.objects.korForInstance(instance)
        )
    else:
        Logg.objects.create(
            model=sender.__name__,
            instancePK=instance.pk,
            change=Logg.UPDATE,
            value=to_dict(instance),
            strRep=str(instance),
            kor=Kor.objects.korForInstance(instance)
        )

@receiver(post_delete, sender=Verv)
@receiver(post_delete, sender=VervInnehavelse)
@receiver(post_delete, sender=Dekorasjon)
@receiver(post_delete, sender=DekorasjonInnehavelse)
@receiver(post_delete, sender=Tilgang)
def log_delete(sender, instance, **kwargs):
    # This is deletion
    Logg.objects.create(
        model=sender.__name__,
        instancePK=instance.pk,
        change=Logg.DELETE,
        value=to_dict(instance),
        strRep=str(instance),
        kor=Kor.objects.korForInstance(instance)
    )


def makeM2MLogg(sender, action, fromPK, toPK):
    [fromModelName, fieldName] = sender._meta.object_name.split("_")

    fromModel = apps.get_model('mytxs', fromModelName)
    toModel = getattr(fromModel, fieldName).rel.model

    LoggM2M.objects.create(
        m2mName=sender._meta.object_name,
        fromLogg=Logg.objects.getLoggForModelPK(fromModel, fromPK),
        toLogg=Logg.objects.getLoggForModelPK(toModel, toPK),
        change=LoggM2M.CREATE if action == 'post_add' else LoggM2M.DELETE
    )

@receiver(m2m_changed, sender=Verv.tilganger.through)
def log_m2m_changed(sender, instance, action, reverse, model, pk_set, **kwargs):

    if action == 'post_add':
        for key in pk_set:
            if not reverse:
                makeM2MLogg(sender, action, instance.pk, key)
            else:
                makeM2MLogg(sender, action, key, instance.pk)

    elif action == 'post_remove':
        for key in pk_set:
            if not reverse:
                makeM2MLogg(sender, action, instance.pk, key)
            else:
                makeM2MLogg(sender, action, key, instance.pk)

    elif action == 'post_clear':
        for key in pk_set:
            if not reverse:
                makeM2MLogg(sender, action, instance.pk, key)
            else:
                makeM2MLogg(sender, action, key, instance.pk)
