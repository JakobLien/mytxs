from datetime import date
from django.conf import settings
from django.http import HttpResponse, HttpResponseNotFound, HttpResponseRedirect, HttpResponseForbidden
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test

from mytxs.models import Dekorasjon, DekorasjonInnehavelse, Kor, Medlem, Tilgang, Verv, VervInnehavelse

from .forms import MedlemsDataForm

from django.forms import inlineformset_factory, modelform_factory

from django import forms



# Create your views here.

def loginView(request):
    #question = get_object_or_404(Question, pk=question_id)
    return render(request, 'mytxs/login.html', {})

@login_required
def index(request):
    return render(request, 'mytxs/sub.html')

@login_required
def sjekkheftet(request, gruppe):
    if gruppe in [kor.kortTittel for kor in Kor.objects.all()]:
        gruppeMedlemmer = Medlem.objects.medlemmerMedTilgang(f'{gruppe}-aktiv')

    return render(request, 'mytxs/sjekkheftet.html', {
        'medlemmer': gruppeMedlemmer, 
        'grupper': [kor.kortTittel for kor in Kor.objects.all()],
    })

@login_required()
@user_passes_test(lambda user : 'medlemListe' in user.medlem.tilgangTilSider)
def medlemListe(request):
    alleMedlemmer = Medlem.objects.all()

    # TODO: Filtrer medlemmer

    return render(request, 'mytxs/medlemListe.html', {'medlemmer': alleMedlemmer})

# example URL params: http://127.0.0.1:8000/medlem/1?initialStart=2023-01-01&initialSlutt=2023-12-31
@login_required()
def medlem(request, pk):
    if pk != request.user.medlem.pk and 'medlem' not in request.user.medlem.tilgangTilSider:
        return HttpResponseRedirect(reverse('mytxs:index'))
    
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
    if request.method == 'POST':
        medlemsDataForm = MedlemsDataForm(request.POST, instance=Medlem.objects.get(pk=pk), prefix="medlemdata")
        vervInnehavelseFormset = VervInnehavelseFormset(request.POST, instance=Medlem.objects.get(pk=pk), prefix='vervInnehavelse')
        dekorasjonInnehavelseFormset = DekorasjonInnehavelseFormset(request.POST, instance=Medlem.objects.get(pk=pk), prefix='dekorasjonInnehavelse')
    else:
        medlemsDataForm = MedlemsDataForm(instance=Medlem.objects.get(pk=pk), prefix='medlemdata')
        vervInnehavelseFormset = VervInnehavelseFormset(instance=Medlem.objects.get(pk=pk), prefix='vervInnehavelse')
        dekorasjonInnehavelseFormset = DekorasjonInnehavelseFormset(instance=Medlem.objects.get(pk=pk), prefix='dekorasjonInnehavelse')

    # Disable medlemsDataForm
    if pk != request.user.medlem.pk and not request.user.medlem.harTilgang('medlemsregister'):
        for input in medlemsDataForm.fields.values():
            input.disabled = True

    # Disable vervInnehavelser de ikke skal kunne endre på
    dekorasjonOptions = Verv.objects.filter(kor__kortTittel__in=request.user.medlem.korForTilgang("vervInnehavelse"))
    for formet in vervInnehavelseFormset.forms:
        # if det ikkje e et nytt felt, og det e en vervinnehavelse brukeren ikke har lov til å endre på
        if formet.instance.pk is not None and not formet.instance.verv.kor.kortTittel in \
                request.user.medlem.korForTilgang("vervInnehavelse"):
            # Det eneste alternativet skal være det vervet som er der
            formet.fields['verv'].queryset = Verv.objects.filter(pk=formet.instance.verv.pk)

            # Disable det aktuelle formet i formsettet
            formet.fields['verv'].disabled = True
            formet.fields['start'].disabled = True
            formet.fields['slutt'].disabled = True
            formet.fields['DELETE'].disabled = True
        else:
            # Bare la brukeren velge blant verv de har kan endre på
            formet.fields['verv'].queryset = dekorasjonOptions
    
    # Disable dekorasjoninnehavelser
    dekorasjonOptions = Dekorasjon.objects.filter(kor__kortTittel__in=request.user.medlem.korForTilgang("dekorasjonInnehavelse"))
    for formet in dekorasjonInnehavelseFormset.forms:
        if formet.instance.pk is not None and not formet.instance.dekorasjon.kor.kortTittel in \
                request.user.medlem.korForTilgang("dekorasjonInnehavelse"):
            formet.fields['dekorasjon'].queryset = Dekorasjon.objects.filter(pk=formet.instance.dekorasjon.pk)

            formet.fields['verv'].disabled = True
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
        else:
            print(vervInnehavelseFormset.errors)

        if dekorasjonInnehavelseFormset.is_valid():
            dekorasjonInnehavelseFormset.save()

        return HttpResponseRedirect(reverse('mytxs:medlem', kwargs={'pk': pk}))

    return render(request, 'mytxs/medlem.html', {
        'medlemsDataForm': medlemsDataForm, 
        'vervInnehavelseFormset': vervInnehavelseFormset,
        'dekorasjonInnehavelseFormset': dekorasjonInnehavelseFormset
    })


@login_required()
@user_passes_test(lambda user : 'vervListe' in user.medlem.tilgangTilSider)
def vervListe(request):
    NyttVervForm = modelform_factory(Verv, exclude=['tilganger'])

    if request.method == 'POST':
        nyttVervForm = NyttVervForm(request.POST)
        if nyttVervForm.is_valid():
            nyttVervForm.save()
        return HttpResponseRedirect(reverse('mytxs:vervListe'))

    nyttVervForm = NyttVervForm()

    if not request.user.medlem.harTilgang('verv-create'):
        for input in nyttVervForm.fields.values():
            input.disabled = True


    return render(request, 'mytxs/vervListe.html', {
        'verv': Verv.objects.filter(kor__kortTittel__in=
            request.user.medlem.korForTilgang("vervInnehavelse")).all(),
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

    if request.method == 'POST':
        innehavelseFormset = VervInnehavelseFormset(request.POST, instance=instance, prefix='vervInnehavelse')
        tilgangFormset = VervTilgangFormset(request.POST, instance=instance, prefix='tilgangInnehavelse')

        if innehavelseFormset.is_valid():
            innehavelseFormset.save()
        if tilgangFormset.is_valid():
            tilgangFormset.save()
        return HttpResponseRedirect(reverse('mytxs:verv', kwargs={'kor': kor, 'vervNavn': vervNavn}))


    # # Sette initial values for datoer fra url
    # initialPeriode = {}
    # if start := request.GET.get('initialStart', ''):
    #     initialPeriode['start'] = start
    # if slutt := request.GET.get('initialSlutt', ''):
    #     initialPeriode['slutt'] = slutt

    innehavelseFormset = VervInnehavelseFormset(instance=instance, prefix='vervInnehavelse')#, initial=[initialPeriode])
    tilgangFormset = VervTilgangFormset(instance=instance, prefix='tilgangInnehavelse')

    if not request.user.medlem.harTilgang(f'{kor}-vervInnehavelse'):
        for formet in innehavelseFormset.forms:
            for input in formet.fields.values():
                input.disabled = True
    if not request.user.medlem.harTilgang('tilgang'):
        for formet in tilgangFormset.forms:
            for input in formet.fields.values():
                input.disabled = True


    return render(request, 'mytxs/verv.html', {'innehavelseFormset': innehavelseFormset, 'tilgangFormset': tilgangFormset})


@login_required()
@user_passes_test(lambda user : 'tilgangListe' in user.medlem.tilgangTilSider)
def tilgangListe(request):
    return render(request, 'mytxs/tilgangListe.html', {'tilganger': Tilgang.objects.all()})

@login_required()
@user_passes_test(lambda user : 'tilgang' in user.medlem.tilgangTilSider)
def tilgang(request, tilgangNavn):
    TilgangVervFormset = inlineformset_factory(Tilgang, Verv.tilganger.through, exclude=[], extra=1)

    instance=Tilgang.objects.get(navn=tilgangNavn)

    if request.method == 'POST':
        formset = TilgangVervFormset(request.POST, instance=instance)

        # check whether it's valid:
        if formset.is_valid():

            #print(formset)
            formset.save()
            
            return HttpResponseRedirect(reverse('mytxs:tilgang', kwargs={'tilgangNavn': tilgangNavn}))

    formset = TilgangVervFormset(instance=instance)

    if not request.user.medlem.harTilgang('tilgang'):
        for formet in formset.forms:
            for input in formet.fields.values():
                input.disabled = True

    return render(request, 'mytxs/tilgang.html', {'formset': formset})


@login_required()
@user_passes_test(lambda user : 'dekorasjonListe' in user.medlem.tilgangTilSider)
def dekorasjonListe(request):
    NyDekorasjonForm = modelform_factory(Dekorasjon, exclude=[])

    if request.method == 'POST':
        nyDekorasjonForm = NyDekorasjonForm(request.POST)
        if nyDekorasjonForm.is_valid():
            nyDekorasjonForm.save()
        return HttpResponseRedirect(reverse('mytxs:dekorasjonListe'))

    nyDekorasjonForm = NyDekorasjonForm()

    if not request.user.medlem.harTilgang('dekorasjon-create'):
        for input in nyDekorasjonForm.fields.values():
            input.disabled = True


    return render(request, 'mytxs/dekorasjonListe.html', {
        'dekorasjoner': Dekorasjon.objects.filter(kor__kortTittel__in=
            request.user.medlem.korForTilgang("dekorasjonInnehavelse")).all(),
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

    if request.method == 'POST':
        innehavelseFormset = DekorasjonInnehavelseFormset(request.POST, instance=instance, prefix='dekorasjonInnehavelse')

        if innehavelseFormset.is_valid():
            innehavelseFormset.save()
        return HttpResponseRedirect(reverse('mytxs:dekorasjon', kwargs={'kor': kor, 'dekorasjonNavn': dekorasjonNavn}))

    innehavelseFormset = DekorasjonInnehavelseFormset(instance=instance, prefix='dekorasjonInnehavelse')

    if not request.user.medlem.harTilgang(f'{kor}-dekorasjonInnehavelse'):
        for formet in innehavelseFormset.forms:
            for input in formet.fields.values():
                input.disabled = True

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
        return HttpResponseRedirect(reverse('mytxs:index'))
    else:
        # Return an 'invalid login' error message.
        return HttpResponseRedirect(reverse('mytxs:login') + '?loginFail=t')
        # return render(request, reverse, {
        #     'error_message': "You didn't select a choice.",
        # })

def logoutEndpoint(request):
    logout(request)
    return HttpResponseRedirect(reverse('mytxs:login'))
