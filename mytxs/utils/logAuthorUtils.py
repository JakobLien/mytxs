from django.utils import timezone

from mytxs.models import Logg

# For å sette author på endringer

def logAuthorInstance(instance, author, pk=None):
    """ Pr no ser e ikkje koss en save ikke kan generer et log objekt, 
        men i tilfelle hive vi på sammenligning av timestampen.
        Så sjølv om noen e inne på django admin og redigere noe, og
        noen andre tilfeldigvis gjør en save på samme objekt som ikke endrer noe, 
        må det ha vært innad samme minutt for å feilaktig sette author. 
    """
    if log := Logg.objects.filter(
            instancePK=pk or instance.pk,
            model=type(instance).__name__,
            author__isnull=True,
            timeStamp__gte=timezone.now() - timezone.timedelta(minutes=1)
    ).order_by('-timeStamp').first():
        log.author = author
        log.save()

def logAuthorAndSave(form, author):
    """Adds author and saves the form
    
    Dette er en litt sammensatt funksjon som løser følgende problem:
    1. form argumentet skal kunne være formsets, altså ta høyde for det
    2. form (eller formset.forms[].instance.pk) kan være satt eller ikke, siden
    om vi oppretter noe nytt er den satt etter save, og om vi sletter er den
    satt før save. """

    if not hasattr(form, 'forms'):
        # Om dette er et form (form.instance.pk er pk) 
        pk=False
        if form.instance.pk:
            pk = form.instance.pk
        form.save()
        logAuthorInstance(form.instance, author, pk=pk if pk else form.instance.pk)
    else:
        # Om dette er et formset (form.forms.intance.forms har pk)
        pk = [form.instance.pk for form in form.forms]
        form.save()
        for i in range(len(form.forms)):
            logAuthorInstance(form.forms[i].instance, author, pk=pk[i] or form.forms[i].instance.pk)