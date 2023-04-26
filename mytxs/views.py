from datetime import date
import datetime
from django.conf import settings
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test

from mytxs.models import Dekorasjon, DekorasjonInnehavelse, Kor, Medlem, Tilgang, Verv, VervInnehavelse

from .forms import MedlemListeFilterForm, MedlemsDataForm

from django.forms import inlineformset_factory, modelform_factory

from django import forms

from django.db.models import Min, Q


# Create your views here.

def loginView(request):
    return render(request, 'mytxs/login.html', {})

@login_required
def index(request):
    return render(request, 'mytxs/sub.html')

@login_required
def sjekkheftet(request, gruppe):
    # Gruperinger er visuelle grupperinger i sjekkheftet, oftest stemmegrupper
    # gruppe argumentet og grupper under refererer til sider på denne siden, altså en for hvert kor
    grupperinger = {}

    if gruppe in [kor.kortTittel for kor in Kor.objects.all()]:
        kor = Kor.objects.get(kortTittel=gruppe)

        for stemmegruppe in kor.stemmegruppeVerv:
            grupperinger[stemmegruppe.navn] = Medlem.objects.filter(
                    vervInnehavelse__start__lte=datetime.date.today(),
                    vervInnehavelse__slutt__gte=datetime.date.today(),
                    vervInnehavelse__verv=stemmegruppe).all()

    return render(request, 'mytxs/sjekkheftet.html', {
        'grupperinger': grupperinger, 
        'grupper': [kor.kortTittel for kor in Kor.objects.all()],
    })

@login_required()
@user_passes_test(lambda user : 'medlemListe' in user.medlem.tilgangTilSider)
def medlemListe(request):
    medlemListeFilterForm = MedlemListeFilterForm(request.GET)

    stemmegruppeVerv = Verv.objects.filter(navn__in=["dirigent", "1S", "2S", "1A", "2A", "1T", "2T", "1B", "2B"])

    # Filtrer hvilket kor de er i
    if kor := request.GET.get('kor', ''):
        stemmegruppeVerv = stemmegruppeVerv.filter(tilganger__navn=f'{kor}-aktiv')

    stemmegruppeVervInnehavelser = VervInnehavelse.objects.filter(
        verv__in=stemmegruppeVerv
    )

    # Filtrer hvilken K der er i dette koret (potensielt småkor, så litt missvisende variabelnavn)
    if K := request.GET.get('K', ''):
        medlemmer = Medlem.objects\
            .annotate(firstVerv=Min("vervInnehavelse__start", filter=Q(vervInnehavelse__in=stemmegruppeVervInnehavelser)))\
            .filter(firstVerv__year=int(K))
    else:
        medlemmer = Medlem.objects.filter(vervInnehavelse__in=stemmegruppeVervInnehavelser).distinct()
    
    # Filtrer fullt navn
    if navn := request.GET.get('navn', ''):
        medlemmer = medlemmer.annotateFulltNavn().filter(fullt_navn__icontains=navn)

    # Filtrer dem som fortsatt e aktive
    if aktiv := request.GET.get('aktiv', ''):
        medlemmer = medlemmer.filter(vervInnehavelse__start__lte=datetime.date.today(),
                                    vervInnehavelse__slutt__gte=datetime.date.today(),
                                    vervInnehavelse__verv__in=stemmegruppeVerv)

    # Filtrer dem som e i en spesifik stemmegruppe (pr no når som helst i det koret)
    if stemmegruppe := request.GET.get('stemmegruppe', ''):
        medlemmer = medlemmer.filter(vervInnehavelse__verv__navn=stemmegruppe,
                                     vervInnehavelse__in=stemmegruppeVervInnehavelser)

    return render(request, 'mytxs/medlemListe.html', {
        'medlemListeFilterForm': medlemListeFilterForm,
        'medlemmer': medlemmer
    })

# example URL params: http://127.0.0.1:8000/medlem/1?initialStart=2023-01-01&initialSlutt=2023-12-31
@login_required()
def medlem(request, pk):
    if pk != request.user.medlem.pk and 'medlem' not in request.user.medlem.tilgangTilSider:
        return HttpResponseRedirect(reverse('index'))
    
    VervInnehavelseFormset = inlineformset_factory(Medlem, VervInnehavelse, exclude=[], extra=1, 
        widgets = {
            'start': forms.widgets.DateInput(attrs={'type': 'date'}),
            'slutt': forms.widgets.DateInput(attrs={'type': 'date'}),
        }
    )

    DekorasjonInnehavelseFormset = inlineformset_factory(Medlem, DekorasjonInnehavelse, exclude=[], extra=1, 
        widgets = {
            'start': forms.widgets.DateInput(attrs={'type': 'date'}),
        }
    )

    medlemsDataForm = MedlemsDataForm(request.POST or None, request.FILES or None, instance=Medlem.objects.get(pk=pk), prefix="medlemdata")
    vervInnehavelseFormset = VervInnehavelseFormset(request.POST or None, instance=Medlem.objects.get(pk=pk), prefix='vervInnehavelse')
    dekorasjonInnehavelseFormset = DekorasjonInnehavelseFormset(request.POST or None, instance=Medlem.objects.get(pk=pk), prefix='dekorasjonInnehavelse')

    # Disable medlemsDataForm
    if not(
        pk == request.user.medlem.pk or #Om det er deg selv
        f'{Medlem.objects.get(pk=pk).storkor}-medlemsdata' in request.user.medlem.tilganger #Om den som ser på har tilgang
    ):
        for input in medlemsDataForm.fields.values():
            input.disabled = True

    # Disable vervInnehavelser de ikke skal kunne endre på
    korForTilgang = [kor.kortTittel for kor in Kor.objects.all() if (kor.kortTittel + "-vervInnehavelse" in request.user.medlem.tilganger)]

    vervOptions = Verv.objects.filter(kor__kortTittel__in=korForTilgang)
    for formet in vervInnehavelseFormset.forms:
        # if det ikkje e et nytt felt, og det e en vervinnehavelse brukeren ikke har lov til å endre på
        if formet.instance.pk is not None and not formet.instance.verv.kor.kortTittel in korForTilgang:
            # Det eneste alternativet skal være det vervet som er der
            formet.fields['verv'].queryset = Verv.objects.filter(pk=formet.instance.verv.pk)

            # Disable det aktuelle formet i formsettet
            formet.fields['verv'].disabled = True
            formet.fields['start'].disabled = True
            formet.fields['slutt'].disabled = True
            formet.fields['DELETE'].disabled = True
        else:
            # Bare la brukeren velge blant verv de har kan endre på
            formet.fields['verv'].queryset = vervOptions
    
    # Disable dekorasjoninnehavelser
    korForTilgang = [kor.kortTittel for kor in Kor.objects.all() if kor.kortTittel + "-dekorasjonInnehavelse" in request.user.medlem.tilganger]

    dekorasjonOptions = Dekorasjon.objects.filter(kor__kortTittel__in=korForTilgang)
    for formet in dekorasjonInnehavelseFormset.forms:
        if formet.instance.pk is not None and not formet.instance.dekorasjon.kor.kortTittel in korForTilgang:
            formet.fields['dekorasjon'].queryset = Dekorasjon.objects.filter(pk=formet.instance.dekorasjon.pk)

            formet.fields['dekorasjon'].disabled = True
            formet.fields['start'].disabled = True
            formet.fields['DELETE'].disabled = True
        else:
            # Sett alternativan
            formet.fields['dekorasjon'].queryset = dekorasjonOptions

    # Denne må være her nede for å takle fraksjonelle tilganger, 
    # altså om fields er disabled må det vær det på POST requesten også, 
    # om ikkje bli formset.is_valid() aldri True fordi den "mangle fields" 
    if request.method == 'POST':
        # check whether it's valid:
        if medlemsDataForm.is_valid():
            medlemsDataForm.save()

        if vervInnehavelseFormset.is_valid():
            vervInnehavelseFormset.save()

        if dekorasjonInnehavelseFormset.is_valid():
            dekorasjonInnehavelseFormset.save()

        return HttpResponseRedirect(reverse('medlem', kwargs={'pk': pk}))

    return render(request, 'mytxs/medlem.html', {
        'medlemsDataForm': medlemsDataForm, 
        'vervInnehavelseFormset': vervInnehavelseFormset,
        'dekorasjonInnehavelseFormset': dekorasjonInnehavelseFormset
    })


@login_required()
@user_passes_test(lambda user : 'vervListe' in user.medlem.tilgangTilSider)
def vervListe(request):
    NyttVervForm = modelform_factory(Verv, exclude=['tilganger'])

    nyttVervForm = NyttVervForm(request.POST or None)

    if not 'verv-create' in request.user.medlem.tilganger:
        for input in nyttVervForm.fields.values():
            input.disabled = True

    if request.method == 'POST':
        if nyttVervForm.is_valid():
            nyttVervForm.save()
        return HttpResponseRedirect(reverse('vervListe'))

    korForTilgang = [kor.kortTittel for kor in Kor.objects.all() if kor.kortTittel + "-vervInnehavelse" in request.user.medlem.tilganger]

    return render(request, 'mytxs/vervListe.html', {
        'verv': Verv.objects.filter(kor__kortTittel__in=korForTilgang).all(),
        'nyttVervForm': nyttVervForm
    })

@login_required()
@user_passes_test(lambda user : 'verv' in user.medlem.tilgangTilSider)
def verv(request, kor, vervNavn):

    VervInnehavelseFormset = inlineformset_factory(Verv, VervInnehavelse, exclude=[], extra=1, widgets = {
            'start': forms.widgets.DateInput(attrs={'type': 'date'}),
            'slutt': forms.widgets.DateInput(attrs={'type': 'date'})
    })

    VervTilgangFormset = inlineformset_factory(Verv, Tilgang.verv.through, exclude=[], extra=1)

    instance=Verv.objects.get(kor=Kor.objects.get(kortTittel=kor), navn=vervNavn)

    innehavelseFormset = VervInnehavelseFormset(request.POST or None, instance=instance, prefix='vervInnehavelse')
    tilgangFormset = VervTilgangFormset(request.POST or None, instance=instance, prefix='tilgangInnehavelse')

    # # Sette initial values for datoer fra url
    # initialPeriode = {}
    # if start := request.GET.get('initialStart', ''):
    #     initialPeriode['start'] = start
    # if slutt := request.GET.get('initialSlutt', ''):
    #     initialPeriode['slutt'] = slutt

    if not f'{kor}-vervInnehavelse' in request.user.medlem.tilganger:
        for formet in innehavelseFormset.forms:
            for input in formet.fields.values():
                input.disabled = True
    if not 'tilgang' in request.user.medlem.tilganger:
        for formet in tilgangFormset.forms:
            for input in formet.fields.values():
                input.disabled = True

    if request.method == 'POST':
        if innehavelseFormset.is_valid():
            innehavelseFormset.save()
        if tilgangFormset.is_valid():
            tilgangFormset.save()
        return HttpResponseRedirect(reverse('verv', kwargs={'kor': kor, 'vervNavn': vervNavn}))

    return render(request, 'mytxs/verv.html', {'innehavelseFormset': innehavelseFormset, 'tilgangFormset': tilgangFormset})


@login_required()
@user_passes_test(lambda user : 'tilgangListe' in user.medlem.tilgangTilSider)
def tilgangListe(request):
    return render(request, 'mytxs/tilgangListe.html', {'tilganger': Tilgang.objects.all()})

@login_required()
@user_passes_test(lambda user : 'tilgang' in user.medlem.tilgangTilSider)
def tilgang(request, tilgangNavn):
    TilgangVervFormset = inlineformset_factory(Tilgang, Verv.tilganger.through, exclude=[], extra=1)

    formset = TilgangVervFormset(request.POST or None, instance=Tilgang.objects.get(navn=tilgangNavn))

    if not 'tilgang' in request.user.medlem.tilganger:
        for formet in formset.forms:
            for input in formet.fields.values():
                input.disabled = True

    if request.method == 'POST':
        if formset.is_valid():
            formset.save()
            return HttpResponseRedirect(reverse('tilgang', kwargs={'tilgangNavn': tilgangNavn}))

    return render(request, 'mytxs/tilgang.html', {'formset': formset})


@login_required()
@user_passes_test(lambda user : 'dekorasjonListe' in user.medlem.tilgangTilSider)
def dekorasjonListe(request):
    NyDekorasjonForm = modelform_factory(Dekorasjon, exclude=[])

    nyDekorasjonForm = NyDekorasjonForm(request.POST or None)

    if not 'dekorasjon-create' in request.user.medlem.tilganger:
        for input in nyDekorasjonForm.fields.values():
            input.disabled = True
    
    if request.method == 'POST':
        if nyDekorasjonForm.is_valid():
            nyDekorasjonForm.save()
        return HttpResponseRedirect(reverse('dekorasjonListe'))

    korForTilgang = [kor.kortTittel for kor in Kor.objects.all() if kor.kortTittel + "-dekorasjonInnehavelse" in request.user.medlem.tilganger]

    return render(request, 'mytxs/dekorasjonListe.html', {
        'dekorasjoner': Dekorasjon.objects.filter(kor__kortTittel__in=korForTilgang).all(),
        'nyDekorasjonForm': nyDekorasjonForm
    })


@login_required()
@user_passes_test(lambda user : 'dekorasjon' in user.medlem.tilgangTilSider)
def dekorasjon(request, kor, dekorasjonNavn):

    DekorasjonInnehavelseFormset = inlineformset_factory(Dekorasjon, DekorasjonInnehavelse, exclude=[], extra=1, widgets = {
            'start': forms.widgets.DateInput(attrs={'type': 'date'}),
            'slutt': forms.widgets.DateInput(attrs={'type': 'date'})
    })

    instance=Dekorasjon.objects.get(kor=Kor.objects.get(kortTittel=kor), navn=dekorasjonNavn)

    innehavelseFormset = DekorasjonInnehavelseFormset(request.POST or None, instance=instance, prefix='dekorasjonInnehavelse')

    if not f'{kor}-dekorasjonInnehavelse' in request.user.medlem.tilganger:
        for formet in innehavelseFormset.forms:
            for input in formet.fields.values():
                input.disabled = True

    if request.method == 'POST':
        if innehavelseFormset.is_valid():
            innehavelseFormset.save()
        return HttpResponseRedirect(reverse('dekorasjon', kwargs={'kor': kor, 'dekorasjonNavn': dekorasjonNavn}))

    return render(request, 'mytxs/dekorasjon.html', {'innehavelseFormset': innehavelseFormset})






# Form endpoints

def loginEndpoint(request):
    username = request.POST['username']
    password = request.POST['password']
    user = authenticate(request, username=username, password=password)
    if user is not None:
        login(request, user)
        
        Medlem.objects.get_or_create(
            user=request.user, defaults={"navn": request.user.username}
        )

        # Redirect to a success page.
        return HttpResponseRedirect(reverse('index'))
    else:
        # Return an 'invalid login' error message.
        return HttpResponseRedirect(reverse('login') + '?loginFail=t')
        # return render(request, reverse, {
        #     'error_message': "You didn't select a choice.",
        # })

def logoutEndpoint(request):
    logout(request)
    return HttpResponseRedirect(reverse('login'))
