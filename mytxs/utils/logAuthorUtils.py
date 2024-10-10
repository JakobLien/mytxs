from django.db.models import ManyToManyField, ManyToManyRel
from django.db.models import Q
from django.forms import BaseFormSet
from django.utils import timezone

from mytxs import consts
from mytxs.models import Logg, LoggM2M
from mytxs.utils.modelUtils import strToModels

# For å sette author på endringer

def logAuthorInstance(instance, author, pk=None):
    '''
    Pr no ser e ikkje koss en save ikke kan generer et log objekt, 
    men i tilfelle hive vi på sammenligning av timestampen.
    Så sjølv om noen e inne på django admin og redigere noe, og
    noen andre tilfeldigvis gjør en save på samme objekt som ikke endrer noe, 
    må det ha vært innad samme minutt for å feilaktig sette author. 
    '''
    if logg := Logg.objects.filter(
        instancePK=pk or instance.pk,
        model=type(instance).__name__,
        author__isnull=True,
        timeStamp__gte=timezone.now() - timezone.timedelta(minutes=1)
    ).order_by('-timeStamp').first():
        logg.author = author
        logg.save()

    # Også logg author på M2M relasjona, Merk at vi ofte opprette M2M uten å opprette 
    # loggs for M2M uten å opprette loggs for noen av de relaterte objektene. 
    for field in type(instance)._meta.get_fields():
        if (
            (isinstance(field, ManyToManyField) or isinstance(field, ManyToManyRel)) and 
            type(instance) in strToModels(consts.loggedModelNames) and field.related_model in strToModels(consts.loggedModelNames)
        ):
            lastLogg = Logg.objects.getLoggFor(instance)

            for M2Mlogg in LoggM2M.objects.filter(
                Q(fromLogg=lastLogg) | Q(toLogg=lastLogg),
                author__isnull=True,
                timeStamp__gte=timezone.now() - timezone.timedelta(minutes=1)
            ):
                M2Mlogg.author = author
                M2Mlogg.save()


def logAuthorAndSave(form, author):
    '''
    Adds author and saves the form
    
    Dette er en litt sammensatt funksjon som løser følgende problem:
    1. form argumentet skal kunne være formsets, altså ta høyde for det
    2. form (eller formset.forms[].instance.pk) kan være satt eller ikke, siden
    om vi oppretter noe nytt er den satt etter save, og om vi sletter er den
    satt før save. 
    '''

    if not isinstance(form, BaseFormSet):
        # Om dette er et form (form.instance.pk er pk)
        if type(form.instance) not in strToModels(consts.loggedModelNames):
            form.save()
            return

        pk=False
        if form.instance.pk:
            pk = form.instance.pk
        form.save()
        logAuthorInstance(form.instance, author, pk=pk if pk else form.instance.pk)
    else:
        # Om dette er et formset (form.forms.intance.forms har pk)

        # For inlineformset_factory er form.instance den relaterte modellen, 
        # ikke modellen de formset.forms er.
        if form.queryset.model not in strToModels(consts.loggedModelNames):
            form.save()
            return
        
        pks = [form.instance.pk for form in form.forms]
        form.save()
        for i in range(len(form.forms)):
            logAuthorInstance(form.forms[i].instance, author, pk=pks[i] or form.forms[i].instance.pk)