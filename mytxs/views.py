from datetime import date
import datetime
import json
from django.shortcuts import redirect, render, get_object_or_404
from django.urls import reverse

from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.forms import AuthenticationForm, SetPasswordForm
from django.contrib.auth.decorators import login_required, user_passes_test

from mytxs.models import Dekorasjon, DekorasjonInnehavelse, Kor, Logg, Medlem, Tilgang, Verv, VervInnehavelse

from .forms import BaseOptionForm, LoggFilterForm, MedlemFilterForm, OptionForm

from django.forms import inlineformset_factory, modelform_factory, modelformset_factory

from django.db.models import Min, Q, F

from mytxs.utils.formUtils import disableForm, disableFormField, partiallyDisableFormset, addReverseM2M, prefixPresent, addDeleteCheckbox, setRequiredDropdownOptions
from mytxs.utils.modelUtils import vervInnehavelseAktiv, hovedStemmeGruppeVerv, stemmeGruppeVerv, stemmeGruppeVervRegex
from mytxs.utils.logAuthor import logAuthorAndSave

from django.contrib import messages

import re

# Create your views here.

def login(request):
    if request.user.is_authenticated:
        return render(request, 'mytxs/base.html')

    loginForm = AuthenticationForm(data=request.POST)

    if request.method == 'POST':
        if loginForm.is_valid():
            user = loginForm.user_cache
            if user is not None:
                auth_login(request, user)

                # # Opprett et medlem til dem
                # Medlem.objects.get_or_create(
                #     user=request.user
                # )
            
                messages.info(request, "Login successful")

                if request.GET.get('next'):
                    return redirect(request.GET.get('next'))
            return redirect('login')
        else:
            messages.error(request, "Login failed")
    
    return render(request, 'mytxs/login.html', {
        'loginForm': AuthenticationForm
    })

def logout(request):
    auth_logout(request)
    return redirect('login')

@login_required
def endrePassord(request):
    endrePassordForm = SetPasswordForm(user=request.user, data=request.POST or None)

    if endrePassordForm.is_valid():
        messages.info(request, "Passord endret!")
        endrePassordForm.save()

    return render(request, 'mytxs/endrePassord.html', {
        'endrePassordForm': endrePassordForm,
        'heading': 'Endre passord'
    })


@login_required
def sjekkheftet(request, gruppe="TSS"):
    grupperinger = {}
    # Gruperinger er visuelle grupperinger i sjekkheftet, oftest stemmegrupper
    # gruppe argumentet og grupper under refererer til sider på denne siden, altså en for hvert kor

    if kor := Kor.objects.filter(kortTittel=gruppe).first():
        if kor.kortTittel != 'KK':
            for stemmegruppe in Verv.objects.filter(hovedStemmeGruppeVerv(''), kor=kor):
                grupperinger[stemmegruppe.navn] = Medlem.objects.filter(
                    vervInnehavelseAktiv(),
                    vervInnehavelse__verv__kor=kor, 
                    vervInnehavelse__verv__navn__endswith=stemmegruppe.navn
                ).all()
        else:
            for stemmegruppe in 'SATB':
                grupperinger[stemmegruppe] = Medlem.objects.filter(
                    vervInnehavelseAktiv(),
                    vervInnehavelse__verv__kor=kor, 
                    vervInnehavelse__verv__navn__endswith=stemmegruppe
                ).all()

    elif gruppe == "Jubileum":
        # Måten dette funke e at for å produser en index med tilsvarende sortering som
        # date_of_year (som ikke finnes i Django), gange vi måneden med 31, og legger på dagen.
        # Så må vi bare ta modulus 403 (den maksimale 12*31+31), også har vi det:)
        today = datetime.date.today()
        today = today.month*31 + today.day
        
        grupperinger = {"":
            Medlem.objects.distinct()
            .filter(vervInnehavelseAktiv(), fødselsdato__isnull=False, vervInnehavelse__verv__tilganger__navn='aktiv')
            .order_by((F('fødselsdato__month') * 31 + F('fødselsdato__day') - today + 403) % 403).all()
        }
    
    return render(request, 'mytxs/sjekkheftet.html', {
        'grupperinger': grupperinger, 
        'grupper': [kor.kortTittel for kor in Kor.objects.all()] + ["Jubileum"],
        'heading': 'Sjekkheftet'
    })

@login_required()
@user_passes_test(lambda user : 'medlemListe' in user.medlem.navBarTilgang, redirect_field_name=None)
def medlemListe(request):
    medlemFilterForm = MedlemFilterForm(request.GET)

    stemmegruppeVerv = Verv.objects.filter(stemmeGruppeVerv('') | Q(navn='dirigent'))

    if not medlemFilterForm.is_valid():
        raise Exception("Søkeformet var ugyldig, ouf")

    # Filtrer stemmegruppeVerv hvilket kor de er i
    if kor := medlemFilterForm.cleaned_data['kor']:
        stemmegruppeVerv = stemmegruppeVerv.filter(tilganger__navn='aktiv', tilganger__kor=kor)

        KVerv=Verv.objects.filter(kor__kortTittel=kor).filter(stemmeGruppeVerv('') | Q(navn='dirigent'))
    else:
        KVerv=Verv.objects.filter(stemmeGruppeVerv('') | Q(navn='dirigent'))
    
    medlemmer = Medlem.objects.distinct()

    # Annotating må skje oppi her, FØR vi filtrere bort stemmegruppeVerv (som kan inneholde deres første verv)
    # se https://docs.djangoproject.com/en/4.2/topics/db/aggregation/#order-of-annotate-and-filter-clauses
    if medlemFilterForm.cleaned_data['K']:
        medlemmer = medlemmer.annotate(
            firstKVerv=Min(
                "vervInnehavelse__start", 
                filter=Q(vervInnehavelse__verv__in=KVerv)
            )
        )

    # Filtrer dem som e i en spesifik stemmegruppe
    if stemmegruppe := medlemFilterForm.cleaned_data['stemmegruppe']:
        print(stemmegruppe)

        stemmegruppeVerv = stemmegruppeVerv.filter(
            navn__endswith=stemmegruppe,
        )

    # Skaff alle tilsvarende stemmegruppeVervInnehavelser
    stemmegruppeVervInnehavelser = VervInnehavelse.objects.filter(
        verv__in=stemmegruppeVerv
    )

    # Filtrer hvilken dato vi ser på
    if dato := medlemFilterForm.cleaned_data['dato']:
        stemmegruppeVervInnehavelser = stemmegruppeVervInnehavelser.filter(
            start__lte=dato,
            slutt__gte=dato
        )

    # Skaff alle tilsvarende medlemmer gitt disse stemmegruppevervene
    medlemmer = medlemmer.filter(vervInnehavelse__in=stemmegruppeVervInnehavelser)

    # Filtrer hvilken K der er i dette koret (potensielt småkor, så litt missvisende variabelnavn)
    if K := medlemFilterForm.cleaned_data['K']:
        medlemmer = medlemmer.filter(firstKVerv__year=K)
    
    # Filtrer fullt navn
    if navn := medlemFilterForm.cleaned_data['navn']:
        medlemmer = medlemmer.annotateFulltNavn().filter(fullt_navn__icontains=navn)

    return render(request, 'mytxs/instanceListe.html', {
        'filterForm': medlemFilterForm,
        'instanceListe': medlemmer,
        'heading': 'Medlemliste'
    })


@login_required()
def medlem(request, pk):
    request.instance = Medlem.objects.get(pk=pk)

    if not request.instance:
        messages.error(request, 'Medlem ikke funnet')
        return redirect('medlemListe')

    if not request.user.medlem.harSideTilgang(request.instance):
        messages.error(request, f'Du har ikke tilgang til {request.instance}')
        return redirect('medlemListe')
    
    # Lag FormsetFactories
    MedlemsDataForm = modelform_factory(Medlem, exclude=['user'])
    VervInnehavelseFormset = inlineformset_factory(Medlem, VervInnehavelse, exclude=[], extra=1)
    DekorasjonInnehavelseFormset = inlineformset_factory(Medlem, DekorasjonInnehavelse, exclude=[], extra=1)

    medlemsDataForm = MedlemsDataForm(
        prefixPresent(request.POST, 'medlemdata'), 
        prefixPresent(request.FILES, 'medlemdata'), 
        instance=request.instance, 
        prefix="medlemdata"
    )
    vervInnehavelseFormset = VervInnehavelseFormset(
        prefixPresent(request.POST, 'vervInnehavelse'), 
        instance=request.instance, 
        prefix='vervInnehavelse'
    )
    dekorasjonInnehavelseFormset = DekorasjonInnehavelseFormset(
        prefixPresent(request.POST, 'dekorasjonInnehavelse'), 
        instance=request.instance, 
        prefix='dekorasjonInnehavelse'
    )

    # Disable medlemsDataForm: Om det ikkje e deg sjølv, eller noen du har tilgang til 
    # (alle med medlemsdata tilgangen kan redigere folk som ikke har et storkor)
    if  not (request.instance == request.user.medlem or
        request.user.medlem.tilganger.filter(navn='medlemsdata', kor=request.instance.storkor).exists() or
        (request.user.medlem.tilganger.filter(navn='medlemsdata').exists() and not request.instance.storkor)):
        disableForm(medlemsDataForm)

    # Disable vervInnehavelser
    partiallyDisableFormset(
        vervInnehavelseFormset,
        Kor.objects.filter(tilganger__in=request.user.medlem.tilganger.filter(navn='vervInnehavelse')),
        'verv'
    )

    # Disable dekorasjonInnehavelser
    partiallyDisableFormset(
        dekorasjonInnehavelseFormset,
        Kor.objects.filter(tilganger__in=request.user.medlem.tilganger.filter(navn='dekorasjonInnehavelse')),
        'dekorasjon'
    )

    if request.method == 'POST':
        if medlemsDataForm.is_valid():
            # IKKE LOGG ENDRINGER PÅ MEDLEMSDATA PGA GDPR!!!
            medlemsDataForm.save()
            return redirect(request.instance)
        if vervInnehavelseFormset.is_valid():
            logAuthorAndSave(vervInnehavelseFormset, request.user.medlem)
            return redirect(request.instance)
        if dekorasjonInnehavelseFormset.is_valid():
            logAuthorAndSave(dekorasjonInnehavelseFormset, request.user.medlem)
            return redirect(request.instance)

    return render(request, 'mytxs/instance.html', {
        'forms': [medlemsDataForm], 
        'formsets': [vervInnehavelseFormset, dekorasjonInnehavelseFormset]
    })


@login_required()
@user_passes_test(lambda user : 'vervListe' in user.medlem.navBarTilgang, redirect_field_name=None)
def vervListe(request):
    NyttVervForm = modelform_factory(Verv, fields=['navn', 'kor'])

    optionForm = OptionForm(request.GET, fields=['alleAlternativ'])

    if not optionForm.is_valid():
        raise Exception("optionForm var ugyldig, ouf")
    
    request.queryset = request.user.medlem.tilgangQueryset(Verv, optionForm.cleaned_data['alleAlternativ'])

    nyttVervForm = NyttVervForm(request.POST or None, prefix="nyttVerv")
    
    # Set kor alternativene
    setRequiredDropdownOptions(nyttVervForm, 'kor', Kor.objects.filter(tilganger__in=request.user.medlem.tilganger.filter(navn='verv')))

    if request.method == 'POST':
        if nyttVervForm.is_valid():
            if re.match(stemmeGruppeVervRegex, nyttVervForm.cleaned_data['navn']):
                messages.error(request, 'Kan ikke opprette stemmegruppeverv')
                return redirect('vervListe')
            logAuthorAndSave(nyttVervForm, request.user.medlem)
            messages.info(request, f'{nyttVervForm.instance} opprettet!')
            return redirect(nyttVervForm.instance)
    
    return render(request, 'mytxs/instanceListe.html', {
        'newForm': nyttVervForm,
        'instanceListe': request.queryset,
        'heading': 'Vervliste',
        'optionForm': optionForm
    })


@login_required()
def verv(request, kor, vervNavn):
    request.instance = Verv.objects.filter(kor__kortTittel=kor, navn=vervNavn).first()

    if not request.instance:
        messages.error(request, 'Verv ikke funnet')
        return redirect('vervListe')

    if not request.user.medlem.harSideTilgang(request.instance):
        messages.error(request, f'Du har ikke tilgang til {request.instance}')
        return redirect('vervListe')

    VervForm = modelform_factory(Verv, fields=['navn', 'tilganger'])
    VervInnehavelseFormset = inlineformset_factory(Verv, VervInnehavelse, exclude=[], extra=1)

    VervForm = addDeleteCheckbox(VervForm)
    
    vervForm = VervForm(prefixPresent(request.POST, 'vervForm'), instance=request.instance, prefix='vervForm')
    vervInnehavelseFormset = VervInnehavelseFormset(prefixPresent(request.POST, 'vervInnehavelse'), instance=request.instance, prefix='vervInnehavelse')
    
    # Disable vervForm dersom de ikke tilgang eller om det er stemmegruppeverv
    if not (request.user.medlem.tilganger.filter(navn='verv', kor=request.instance.kor).exists()):
        disableFormField(vervForm, 'navn', 'delete')
    elif request.instance.stemmegruppeVerv:
        disableFormField(vervForm, 'navn', 'delete', helpText='Selv ikke de med tilgang kan endre på stemmegruppeverv')

    # Disable vervInnehavelseFormset
    if not request.user.medlem.tilganger.filter(navn='vervInnehavelse', kor=request.instance.kor):
        disableForm(vervInnehavelseFormset)

    # Disable tilgang options
    vervForm.fields['tilganger'].setEnableQuerysetKor(
        Kor.objects.filter(tilganger__in=request.user.medlem.tilganger.filter(navn='tilgang')),
        request.instance.tilganger.all()
    )

    if request.method == 'POST':
        if vervForm.is_valid():
            if not request.instance.stemmegruppeVerv and re.match(stemmeGruppeVervRegex, vervForm.cleaned_data['navn']):
                messages.error(request, 'Kan ikke endre navn til stemmegruppeverv')
                return redirect(request.instance)
            logAuthorAndSave(vervForm, request.user.medlem)
            if vervForm.cleaned_data['delete']:
                messages.info(request, f'{vervForm.instance} slettet')
                return redirect('vervListe')
            return redirect(request.instance)
        if vervInnehavelseFormset.is_valid():
            logAuthorAndSave(vervInnehavelseFormset, request.user.medlem)
            return redirect(request.instance)

    return render(request, 'mytxs/instance.html', {
        'forms': [vervForm],
        'formsets': [vervInnehavelseFormset]
    })



@login_required()
@user_passes_test(lambda user : 'dekorasjonListe' in user.medlem.navBarTilgang, redirect_field_name=None)
def dekorasjonListe(request):
    request.queryset = request.user.medlem.tilgangQueryset(Dekorasjon)

    NyDekorasjonForm = modelform_factory(Dekorasjon, fields=['navn', 'kor'])

    nyDekorasjonForm = NyDekorasjonForm(request.POST or None, prefix="nyDekorasjon")
    
    # Set kor alternativene
    setRequiredDropdownOptions(nyDekorasjonForm, 'kor', Kor.objects.filter(tilganger__in=request.user.medlem.tilganger.filter(navn='dekorasjon')))

    if request.method == 'POST':
        if nyDekorasjonForm.is_valid():
            logAuthorAndSave(nyDekorasjonForm, request.user.medlem)
            messages.info(request, f'{nyDekorasjonForm.instance} opprettet!')
            return redirect(nyDekorasjonForm.instance)

    return render(request, 'mytxs/instanceListe.html', {
        'instanceListe': request.queryset,
        'newForm': nyDekorasjonForm,
        'heading': 'Dekorasjonliste'
    })


@login_required()
def dekorasjon(request, kor, dekorasjonNavn):
    request.instance = Dekorasjon.objects.filter(kor__kortTittel=kor, navn=dekorasjonNavn).first()

    if not request.instance:
        messages.error(request, 'Dekorasjon ikke funnet')
        return redirect('dekorasjonListe')

    if not request.user.medlem.harSideTilgang(request.instance):
        messages.error(request, f'Du har ikke tilgang til {request.instance}')
        return redirect('dekorasjonListe')

    DekorasjonForm = modelform_factory(Dekorasjon, exclude=['kor'])
    DekorasjonInnehavelseFormset = inlineformset_factory(Dekorasjon, DekorasjonInnehavelse, exclude=[], extra=1)

    DekorasjonForm = addDeleteCheckbox(DekorasjonForm)

    dekorasjonForm = DekorasjonForm(prefixPresent(request.POST, 'dekorasjonForm'), instance=request.instance, prefix='dekorasjonForm')
    dekorasjonInnehavelseFormset = DekorasjonInnehavelseFormset(prefixPresent(request.POST, 'dekorasjonInnehavelse'), instance=request.instance, prefix='dekorasjonInnehavelse')

    # Disable dekorasjonForm
    if not request.user.medlem.tilganger.filter(navn='dekorasjon', kor=request.instance.kor).exists():
        disableForm(dekorasjonForm)

    # Disable dekorasjonInnehavelseFormset
    if not request.user.medlem.tilganger.filter(navn='dekorasjonInnehavelse', kor=request.instance.kor):
        disableForm(dekorasjonInnehavelseFormset)

    if request.method == 'POST':
        if dekorasjonForm.is_valid():
            logAuthorAndSave(dekorasjonForm, request.user.medlem)
            if dekorasjonForm.cleaned_data['delete']:
                messages.info(request, f'{dekorasjonForm.instance} slettet')
                return redirect('dekorasjonListe')
            return redirect(request.instance)
        if dekorasjonInnehavelseFormset.is_valid():
            logAuthorAndSave(dekorasjonInnehavelseFormset, request.user.medlem)
            return redirect(request.instance)

    return render(request, 'mytxs/instance.html', {
        'forms': [dekorasjonForm],
        'formsets': [dekorasjonInnehavelseFormset]
    })


@login_required()
@user_passes_test(lambda user : 'tilgangListe' in user.medlem.navBarTilgang, redirect_field_name=None)
def tilgangListe(request):
    request.queryset = request.user.medlem.tilgangQueryset(Tilgang)

    NyTilgangForm = modelform_factory(Tilgang, fields=['navn', 'kor'])

    nyTilgangForm = NyTilgangForm(request.POST or None, prefix="nyTilgang")
    
    # Set kor alternativene
    setRequiredDropdownOptions(nyTilgangForm, 'kor', Kor.objects.filter(tilganger__in=request.user.medlem.tilganger.filter(navn='tilgang')))

    if request.method == 'POST':
        if nyTilgangForm.is_valid():
            logAuthorAndSave(nyTilgangForm, request.user.medlem)
            messages.info(request, f'{nyTilgangForm.instance} opprettet!')
            return redirect(nyTilgangForm.instance)

    return render(request, 'mytxs/instanceListe.html', {
        'instanceListe': request.queryset,
        'newForm': nyTilgangForm,
        'heading': 'Tilgangliste'
    })


@login_required()
def tilgang(request, kor, tilgangNavn):
    request.instance = Tilgang.objects.filter(kor__kortTittel=kor, navn=tilgangNavn).first()

    if not request.instance:
        messages.error(request, 'Tilgang ikke funnet')
        return redirect('tilgangListe')

    if not request.user.medlem.harSideTilgang(request.instance):
        messages.error(request, f'Du har ikke tilgang til {request.instance}')
        return redirect('tilgangListe')
    
    optionForm = OptionForm(request.GET, fields=['alleAlternativ'])

    if not optionForm.is_valid():
        raise Exception("optionForm var ugyldig, ouf")
    
    TilgangForm = modelform_factory(Tilgang, exclude=['kor'])

    TilgangForm = addReverseM2M(TilgangForm, 'verv')

    TilgangForm = addDeleteCheckbox(TilgangForm)

    tilgangForm = TilgangForm(request.POST or None, instance=request.instance)

    # Gjør så den bare vise samme kor eller selected, dersom vi ikke bruke alleAlternativ
    if not optionForm.cleaned_data['alleAlternativ']:
        tilgangForm.fields['verv'].queryset = tilgangForm.fields['verv'].queryset.filter(
            Q(kor=request.instance.kor) | Q(tilganger__pk=request.instance.pk)
        ).distinct()

    # Disable brukt feltet
    disableFormField(tilgangForm, 'brukt')
    
    # Disable navn om brukt
    if request.instance.brukt:
        disableFormField(tilgangForm, 'navn', 'delete', helpText='Selv ikke de med tilgang kan endre på en brukt tilgang')
    
    if request.method == 'POST':
        if tilgangForm.is_valid():
            logAuthorAndSave(tilgangForm, request.user.medlem)
            if tilgangForm.cleaned_data['delete']:
                messages.info(request, f'{tilgangForm.instance} slettet')
                return redirect('tilgangListe')
            return redirect(request.instance)
    
    return render(request, 'mytxs/instance.html', {
        'forms': [tilgangForm],
        'optionForm': optionForm
    })


@login_required()
@user_passes_test(lambda user : 'loggListe' in user.medlem.navBarTilgang, redirect_field_name=None)
def loggListe(request):
    # GET forms skal tydeligvis ikkje ha 'or None' for å få is_valid() uten url params ¯\_(ツ)_/¯
    loggFilterForm = LoggFilterForm(request.GET) #TODO

    loggFilterForm.fields['model'].choices = loggFilterForm.fields['model'].choices + [(i, i) for i in [
        'VervInnehavelse', 'Verv', 'DekorasjonInnehavelse', 'Dekorasjon', 'Tilgang'
    ]]

    if not loggFilterForm.is_valid():
        raise Exception("Søkeformet var ugyldig, ouf")
    
    logg = Logg.objects.all()

    if kor := loggFilterForm.cleaned_data['kor']:
        logg = logg.filter(kor=kor)

    if model := loggFilterForm.cleaned_data['model']:
        logg = logg.filter(model=model)

    if author := loggFilterForm.cleaned_data['author']:
        logg = logg.filter(author=author)

    if pk := loggFilterForm.cleaned_data['pk']:
        logg = logg.filter(instancePK=pk)

    if start := loggFilterForm.cleaned_data['start']:
        logg = logg.filter(timeStamp__date__gte=start)

    if slutt := loggFilterForm.cleaned_data['slutt']:
        logg = logg.filter(timeStamp__date__lte=slutt)
    
    return render(request, 'mytxs/instanceListe.html', {
        'filterForm': loggFilterForm,
        'instanceListe': logg,
        'heading': 'Loggliste'
    })


@login_required()
def logg(request, pk):
    request.instance = Logg.objects.get(pk=pk)

    if not request.user.medlem.harSideTilgang(request.instance):
        messages.error(request, f'Du har ikke tilgang til {request.instance}')
        return redirect('loggListe')

    LoggForm = modelform_factory(Logg, exclude=['value'])

    loggForm = LoggForm(instance=request.instance)

    disableForm(loggForm)

    lastLog = Logg.objects.filter(
        instancePK=request.instance.instancePK,
        model=request.instance.model,
        timeStamp__lt=request.instance.timeStamp
    ).order_by('-timeStamp').first()

    nextLog = Logg.objects.filter(
        instancePK=request.instance.instancePK,
        model=request.instance.model,
        timeStamp__gt=request.instance.timeStamp
    ).order_by('timeStamp').first()

    return render(request, 'mytxs/logg.html', {
        'lastLog': lastLog,
        'nextLog': nextLog,
        'loggForm': loggForm,
        'value': json.dumps(request.instance.value, indent=4),
        'actual': request.instance.getActual()
    })
