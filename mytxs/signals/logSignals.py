from django.apps import apps
from django.dispatch import receiver
from django.db.models import ManyToManyField
from django.db.models.fields.related import RelatedField
from django.db.models.signals import post_delete, post_save, m2m_changed

from mytxs.models import Logg, LoggM2M, Medlem
from mytxs import consts

from itertools import chain

# Modifisert versjon av django.forms.models.model_to_dict delvis hentet herifra 
# https://stackoverflow.com/a/29088221/6709450 (#5)
# Forskjellen er at denne serialiserer ikke manyToMany relations, den tar med editable=False fields,
# og den erstatter foreign keys med pk av tilsvarende logg instance, eller str representasjon av objektet
# når loggen ikke finens (som for User loggs)
def to_dict(instance, fields=None, exclude=None):
    opts = instance._meta
    data = {}
    for field in chain(opts.concrete_fields, opts.private_fields):
        if fields is not None and field.name not in fields:
            continue
        if exclude and field.name in exclude:
            continue

        if field.name == 'strRep':
            # Ikke lagre strRep feltet i loggen
            continue

        if isinstance(field, RelatedField):
            if getattr(instance, field.name) and (logg := Logg.objects.getLoggFor(getattr(instance, field.name))):
                # Om det er en relasjon, lagre pk av den nyeste relaterte loggen (ikke av instansen)
                data[field.name] = logg.pk
            else:
                # Om vi ikke finn den relevante loggen, lagre string representasjon av objektet
                data[field.name] = str(getattr(instance, field.name))
        elif type(instance) == Medlem:
            # Om det e et medlem skal vi bare lagre relasjoner + fornavn, mellomnavn og etternavn
            if field.name in ['fornavn', 'mellomnavn', 'etternavn']:
                data[field.name] = field.value_from_object(instance)
        elif field.choices != None:
            # Håndter choice fields
            data[field.name] = getattr(instance, f'get_{field.name}_display')()
        elif type(field.value_from_object(instance)) not in [str, int, float, bool, None]:
            # Om det ikke er en relasjon, men er et objekt, lagre string representasjon av objektet, f.eks. for Date
            data[field.name] = str(field.value_from_object(instance))
        else:
            # Ellers, lagre det som er naturlig.
            data[field.name] = field.value_from_object(instance)
    return data


def didChange(instance):
    'Gitt en instance sjekker denne om noe er endret siden nyeste logg. Dette er vanskelig for related fields.'
    lastLogg = Logg.objects.getLoggFor(instance)

    newDict = to_dict(instance)

    if newDict == lastLogg.value:
        # Om de er like er det garantert samme logg
        return False

    model = type(instance)
    
    if set(newDict.keys()) != set(lastLogg.value.keys()):
        # Om de har ulike keys e det garantert ulike loggs
        # Denne codepathen er sansynligvis feil bruk av funksjonen, men viktig for korrekthet
        return True

    # Ellers, gå over alle keys i logg.value
    for key, value in newDict.items():
        if isinstance(model._meta.get_field(key), RelatedField):
            # For related fields: Sjekk om loggen den peker på har ulik pk
            if not isinstance(value, int) or not isinstance(lastLogg.value.get(key), int):
                # Om det e te en modell vi ikke logge lagres det istedet en str representasjon av objektet
                # Om enten av disse ikkje er en int, så sammenlign de direkte istedet. Slik blir det lagret
                # om str representasjonen av det andre objektet endrer seg (fordi det andre objektet endret seg)
                # eller om vi bytta fra str representasjon til faktisk objekt, eller omvendt. 
                if value != lastLogg.value.get(key):
                    return True
                continue
            if Logg.objects.get(pk=value).instancePK != Logg.objects.get(pk=lastLogg.value.get(key)).instancePK:
                return True
        else:
            # Sjekk om verdien er ulik
            if value != lastLogg.value.get(key):
                return True
    
    return False


def recieverWithModels(signal, senders=consts.getLoggedModels()):
    '''
    Denne funksjonen tar inn en liste av models, og er ekvivalent med å skrive mange @reciever statements, typ:
    ``` @receiver(post_delete, sender=Verv)
        @receiver(post_delete, sender=VervInnehavelse)
        @receiver(post_delete, sender=Dekorasjon)
        @receiver(post_delete, sender=DekorasjonInnehavelse)
        @receiver(post_delete, sender=Tilgang)```
    
    Defaulten er consts.getLoggedModels()
    '''
    def _decorator(func):
        for model in senders:
            func = receiver(signal, sender=model)(func)
        return func
    return _decorator


@recieverWithModels(post_save)
def log_post_save(sender, instance, created, **kwargs):
    if created:
        # This is creation
        Logg.objects.create(
            model=sender.__name__,
            instancePK=instance.pk,
            change=Logg.CREATE,
            value=to_dict(instance),
            strRep=str(instance),
            kor=instance.kor
        )
    else:
        # This is change
        if not didChange(instance):
            # Dersom ingenting endra seg, ikkje lag en ny logg
            return

        Logg.objects.create(
            model=sender.__name__,
            instancePK=instance.pk,
            change=Logg.UPDATE,
            value=to_dict(instance),
            strRep=str(instance),
            kor=instance.kor
        )


@recieverWithModels(post_delete)
def log_post_delete(sender, instance, **kwargs):
    # This is deletion
    Logg.objects.create(
        model=sender.__name__,
        instancePK=instance.pk,
        change=Logg.DELETE,
        value=to_dict(instance),
        strRep=str(instance),
        kor=instance.kor
    )


def makeM2MLogg(sender, action, fromPK, toPK):
    '''
    Makes an m2m logg given 
    - sender: a m2mfield.through
    - action: one of 'post_add', 'post_remove' and 'post_clear'
    - fromPK: The pk of the source model
    - toPK: The pk of the target model
    '''
    [fromModelName, fieldName] = sender._meta.object_name.split('_')

    fromModel = apps.get_model('mytxs', fromModelName)
    toModel = getattr(fromModel, fieldName).rel.model

    LoggM2M.objects.create(
        m2mName=sender._meta.object_name,
        fromLogg=Logg.objects.getLoggForModelPK(fromModel, fromPK),
        toLogg=Logg.objects.getLoggForModelPK(toModel, toPK),
        change=LoggM2M.CREATE if action == 'post_add' else LoggM2M.DELETE
    )


# Skaff en liste av alle m2m fields .through, der vi logge både kilde og target modell
m2mFields = []
for model in consts.getLoggedModels():
    for field in model._meta.get_fields():
        if isinstance(field, ManyToManyField) and field.related_model in consts.getLoggedModels():
            m2mFields.append(getattr(model, field.name).through)


@recieverWithModels(m2m_changed, senders=m2mFields)
def log_m2m_changed(sender, instance, action, reverse, model, pk_set, **kwargs):
    if action in ('post_add', 'post_remove', 'post_clear'):
        for key in pk_set:
            if not reverse:
                makeM2MLogg(sender, action, instance.pk, key)
            else:
                makeM2MLogg(sender, action, key, instance.pk)
