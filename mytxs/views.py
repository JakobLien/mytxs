import datetime
import random

from django.contrib import messages
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.forms import AuthenticationForm, SetPasswordForm, UserCreationForm
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q, F, IntegerField
from django.db.models.functions import Cast
from django.forms import inlineformset_factory, modelform_factory, modelformset_factory
from django.shortcuts import redirect, render, get_object_or_404

from mytxs.consts import bareKorKortTittel
from mytxs.models import Dekorasjon, DekorasjonInnehavelse, Kor, Logg, Medlem, Tilgang, Verv, VervInnehavelse
from mytxs.forms import BaseOptionForm, LoggFilterForm, MedlemFilterForm, OptionForm
from mytxs.utils.formAccess import disableForm, disableFormField, partiallyDisableFormset, partiallyDisableFormsetKor, setRequiredDropdownOptions
from mytxs.utils.formAddField import addDeleteCheckbox, addReverseM2M
from mytxs.utils.formUtils import prefixPresent, formsetArgs
from mytxs.utils.logAuthorUtils import logAuthorAndSave
from mytxs.utils.modelUtils import isStemmegruppeVervNavn, randomDistinct, vervInnehavelseAktiv, hovedStemmeGruppeVerv, stemmegruppeVerv, stemmegruppeVervRegex
from mytxs.utils.utils import downloadFile, getPaginatorPage, generateVCard

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

def registrer(request, medlemPK):
    medlem = get_object_or_404(Medlem, pk=medlemPK, user=None)

    userCreationForm = UserCreationForm(request.POST or None)

    if request.method == 'POST':
        if userCreationForm.is_valid():
            user = userCreationForm.save()
            auth_login(request, user)

            medlem.user = user
            medlem.save()
            messages.info(request, f'Opprettet bruker for {medlem}!')
            return redirect(medlem)

    return render(request, 'mytxs/register.html', {
        'registerForm': userCreationForm,
        'heading': 'MedlemPK: ' + str(medlemPK)
    })

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
def sjekkheftet(request, gruppe, undergruppe=None):
    grupper = bareKorKortTittel + ["jubileum", "sjekkhefTest"]
    grupperinger = {}
    # Gruperinger er visuelle grupperinger i sjekkheftet på samme side, klassisk stemmegrupper
    # gruppe argumentet og grupper under refererer til sider på denne siden, altså en for hvert kor++

    if kor := Kor.objects.filter(kortTittel=gruppe).first():
        request.undergrupper = [t.navn for t in Tilgang.objects.filter(
            kor=kor,
            sjekkheftetSynlig=True
        )]

        if tilgang := Tilgang.objects.filter(sjekkheftetSynlig=True, navn=undergruppe, kor=kor).first():
            request.queryset = Medlem.objects.distinct().filter(
                vervInnehavelseAktiv(),
                vervInnehavelse__verv__kor=kor,
                vervInnehavelse__verv__tilganger__pk=tilgang.id
            ).all()

            grupperinger = {tilgang.navn:
                request.queryset
            }
        else:
            request.queryset = Medlem.objects.distinct().filter(
                vervInnehavelseAktiv(),
                vervInnehavelse__verv__kor=kor
            ).all()
            if kor.kortTittel != 'KK':
                for stemmegruppe in Verv.objects.filter(hovedStemmeGruppeVerv(''), kor=kor):
                    grupperinger[stemmegruppe.navn] = request.queryset.filter(
                        vervInnehavelse__verv__navn__endswith=stemmegruppe.navn,
                        vervInnehavelse__verv__kor=kor
                    ).all()
            else:
                for stemmegruppe in 'SATB':
                    grupperinger[stemmegruppe] = request.queryset.filter(
                        vervInnehavelse__verv__navn__endswith=stemmegruppe,
                        vervInnehavelse__verv__kor=kor
                    ).all()

    elif gruppe == "jubileum":
        request.queryset = Medlem.objects.distinct().filter(
            vervInnehavelseAktiv(), 
            stemmegruppeVerv('vervInnehavelse__verv'),
            fødselsdato__isnull=False
        ).all()

        # Måten dette funke e at for å produser en index med tilsvarende sortering som
        # date_of_year (som ikke finnes i Django), gange vi måneden med 31, og legger på dagen.
        # Så må vi bare ta modulus 403 (den maksimale 12*31+31), også har vi det:)
        today = datetime.date.today()
        today = today.month*31 + today.day
        
        grupperinger = {"":
            request.queryset.order_by(Cast((F('fødselsdato__month') * 31 + F('fødselsdato__day') - today + 403), output_field=IntegerField()) % 403).all()
        }
        # Gud veit koffor serveren ikke ønske å tolke enten day eller month som en integer i utgangspunktet. Har ikke det problemet lokalt...

    elif gruppe == "sjekkhefTest":
        request.queryset = randomDistinct(
            Medlem.objects.filter(
                vervInnehavelseAktiv(),
                stemmegruppeVerv('vervInnehavelse__verv'),
                ~Q(bilde="")
            ), 20
        )

        return render(request, 'mytxs/sjekkhefTest.html', {
            'grupper': grupper,
            'heading': 'Sjekkheftet'
        })

    # Håndter vcard for de på denne siden dersom det var det
    if request.GET.get('vcard'):
        file_data = generateVCard(request.queryset.exclude(tlf=''))
        return downloadFile(f'{gruppe}.vcf', file_data)
    
    return render(request, 'mytxs/sjekkheftet.html', {
        'grupperinger': grupperinger, 
        'grupper': grupper,
        'gruppe': gruppe,
        'heading': 'Sjekkheftet'
    })

@login_required()
@user_passes_test(lambda user : 'medlemListe' in user.medlem.navBarTilgang, redirect_field_name=None)
def medlemListe(request):
    request.queryset = request.user.medlem.tilgangQueryset(Medlem)

    medlemFilterForm = MedlemFilterForm(request.GET)

    if not medlemFilterForm.is_valid():
        raise Exception("Søkeformet var ugyldig, ouf")
    
    # Filtrer på kor
    sgVerv = Verv.objects.filter(stemmegruppeVerv(''))
    if kor := medlemFilterForm.cleaned_data['kor']:
        sgVerv = sgVerv.filter(kor=kor)
    
    # Filtrer på karantenekor
    if K := medlemFilterForm.cleaned_data['K']:
        request.queryset = request.queryset.annotateKarantenekor(
            kor=kor or None
        )
        request.queryset = request.queryset.filter(K=K)
    
    # Filtrer på stemmegruppe
    if stemmegruppe := medlemFilterForm.cleaned_data['stemmegruppe']:
        sgVerv = sgVerv.filter(navn__iendswith=stemmegruppe)

    # Filtrer på dato de hadde dette vervet
    if dato := medlemFilterForm.cleaned_data['dato']:
        request.queryset = request.queryset.filter(
            vervInnehavelseAktiv(dato=dato),
            vervInnehavelse__verv__in=sgVerv
        )
    elif kor or stemmegruppe or K:
        # Denne elif-en er nødvendig for å få med folk som ikke har et kor
        request.queryset = request.queryset.filter(
            Q(vervInnehavelse__verv__in=sgVerv)
        )

    # Filtrer fullt navn
    if navn := medlemFilterForm.cleaned_data['navn']:
        request.queryset = request.queryset.annotateFulltNavn()
        request.queryset = request.queryset.filter(fulltNavn__icontains=navn)

    NyttMedlemForm = modelform_factory(Medlem, fields=['fornavn', 'mellomnavn', 'etternavn'])

    nyttMedlemForm = NyttMedlemForm(request.POST or None, prefix="nyttMedlem", initial={
        'fornavn': '', 'mellomnavn': '', 'etternavn': ''
    })

    if not request.user.medlem.tilganger.filter(navn='medlemsdata'):
        disableForm(nyttMedlemForm)

    if request.method == 'POST':
        if nyttMedlemForm.is_valid():
            logAuthorAndSave(nyttMedlemForm, request.user.medlem)
            messages.info(request, f'{nyttMedlemForm.instance} opprettet!')
            return redirect(nyttMedlemForm.instance)
    
    return render(request, 'mytxs/instanceListe.html', {
        'filterForm': medlemFilterForm,
        'paginatorPage': getPaginatorPage(request),
        'heading': 'Medlemliste',
        'newForm': nyttMedlemForm
    })


@login_required()
def medlem(request, pk):
    request.instance = Medlem.objects.filter(pk=pk).first()

    if not request.instance:
        messages.error(request, 'Medlem ikke funnet')
        return redirect('medlemListe')

    if not request.user.medlem.harSideTilgang(request.instance):
        messages.error(request, f'Du har ikke tilgang til dette medlemmet')
        return redirect('medlemListe')
    
    # Lag FormsetFactories
    MedlemsDataForm = modelform_factory(Medlem, exclude=['user'])
    VervInnehavelseFormset = inlineformset_factory(Medlem, VervInnehavelse, **formsetArgs)
    DekorasjonInnehavelseFormset = inlineformset_factory(Medlem, DekorasjonInnehavelse, **formsetArgs)

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
        request.user.medlem.tilganger.filter(navn='medlemsdata', kor=request.instance.storkor or None).exists() or
        request.user.medlem.tilganger.filter(navn='medlemsdata').exists() and not request.instance.storkor):
        disableForm(medlemsDataForm)

    # Disable vervInnehavelser
    partiallyDisableFormsetKor(
        vervInnehavelseFormset,
        Kor.objects.filter(tilganger__in=request.user.medlem.tilganger.filter(navn='vervInnehavelse')),
        'verv'
    )

    # Disable dekorasjonInnehavelser
    partiallyDisableFormsetKor(
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

    return render(request, 'mytxs/medlem.html', {
        'forms': [medlemsDataForm], 
        'formsets': [vervInnehavelseFormset, dekorasjonInnehavelseFormset]
    })


@login_required()
@user_passes_test(lambda user : 'vervListe' in user.medlem.navBarTilgang, redirect_field_name=None)
def vervListe(request):
    NyttVervForm = modelform_factory(Verv, fields=['navn', 'kor'])

    # optionForm = OptionForm(request.GET, fields=['alleAlternativ'])

    # if not optionForm.is_valid():
    #     raise Exception("optionForm var ugyldig, ouf")
    
    request.queryset = request.user.medlem.tilgangQueryset(Verv)#, optionForm.cleaned_data['alleAlternativ'])

    nyttVervForm = NyttVervForm(request.POST or None, prefix="nyttVerv")
    
    # Set kor alternativene
    setRequiredDropdownOptions(nyttVervForm, 'kor', Kor.objects.filter(tilganger__in=request.user.medlem.tilganger.filter(navn='verv')))

    if request.method == 'POST':
        if nyttVervForm.is_valid():
            if isStemmegruppeVervNavn(nyttVervForm.cleaned_data['navn']):
                messages.error(request, 'Kan ikke opprette stemmegruppeverv')
                return redirect('vervListe')
            logAuthorAndSave(nyttVervForm, request.user.medlem)
            messages.info(request, f'{nyttVervForm.instance} opprettet!')
            return redirect(nyttVervForm.instance)
    
    return render(request, 'mytxs/instanceListe.html', {
        'newForm': nyttVervForm,
        'paginatorPage': getPaginatorPage(request),
        'heading': 'Vervliste',
        #'optionForm': optionForm
    })


@login_required()
def verv(request, kor, vervNavn):
    request.instance = Verv.objects.filter(kor__kortTittel=kor, navn=vervNavn).first()

    if not request.instance:
        messages.error(request, 'Verv ikke funnet')
        return redirect('vervListe')

    if not request.user.medlem.harSideTilgang(request.instance):
        messages.error(request, f'Du har ikke tilgang til dette vervet')
        return redirect('vervListe')

    VervForm = modelform_factory(Verv, fields=['navn', 'tilganger'])
    VervInnehavelseFormset = inlineformset_factory(Verv, VervInnehavelse, **formsetArgs)

    VervForm = addDeleteCheckbox(VervForm)
    
    vervForm = VervForm(prefixPresent(request.POST, 'vervForm'), instance=request.instance, prefix='vervForm')
    vervInnehavelseFormset = VervInnehavelseFormset(prefixPresent(request.POST, 'vervInnehavelse'), instance=request.instance, prefix='vervInnehavelse')
    
    # Disable vervForm dersom de ikke tilgang eller om det er stemmegruppeverv
    if not (request.user.medlem.tilganger.filter(navn='verv', kor=request.instance.kor).exists()):
        disableFormField(vervForm, 'navn', 'DELETE')
    elif request.instance.stemmegruppeVerv:
        disableFormField(vervForm, 'navn', 'DELETE', helpText='Selv ikke de med tilgang kan endre på stemmegruppeverv')

    # Disable vervInnehavelseFormset
    if not request.user.medlem.tilganger.filter(navn='vervInnehavelse', kor=request.instance.kor):
        disableForm(vervInnehavelseFormset)

    # # Disable vervInnehavelseFormset
    # partiallyDisableFormset(
    #     vervInnehavelseFormset,
    #     Medlem.objects.filter(
    #         stemmegruppeVerv('vervInnehavelse__verv'), 
    #         vervInnehavelse__verv__kor__tilganger__in=request.user.medlem.tilganger.filter(navn='vervInnehavelse')
    #     ),
    #     'medlem'
    # )
    
    # Sett tilgang options (kan fjerne men ikke legge til andre kors tilganger)
    vervForm.fields['tilganger'].queryset = vervForm.fields['tilganger'].queryset.filter(
        Q(kor=request.instance.kor) | Q(verv__pk=request.instance.pk)
    ).distinct()

    # Disable tilgang options
    # vervForm.fields['tilganger'].setEnableQuerysetKor(
    #     Kor.objects.filter(tilganger__in=request.user.medlem.tilganger.filter(navn='tilgang')),
    #     request.instance.tilganger.all()
    # )

    if request.method == 'POST':
        if vervForm.is_valid():
            if not request.instance.stemmegruppeVerv and isStemmegruppeVervNavn(vervForm.cleaned_data['navn']):
                messages.error(request, 'Kan ikke endre navn til stemmegruppeverv')
                return redirect(request.instance)
            logAuthorAndSave(vervForm, request.user.medlem)
            if vervForm.cleaned_data['DELETE']:
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
        'paginatorPage': getPaginatorPage(request),
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
        messages.error(request, f'Du har ikke tilgang til denne dekorasjonen')
        return redirect('dekorasjonListe')

    DekorasjonForm = modelform_factory(Dekorasjon, exclude=['kor'])
    DekorasjonInnehavelseFormset = inlineformset_factory(Dekorasjon, DekorasjonInnehavelse, **formsetArgs)

    DekorasjonForm = addDeleteCheckbox(DekorasjonForm)

    dekorasjonForm = DekorasjonForm(prefixPresent(request.POST, 'dekorasjonForm'), instance=request.instance, prefix='dekorasjonForm')
    dekorasjonInnehavelseFormset = DekorasjonInnehavelseFormset(prefixPresent(request.POST, 'dekorasjonInnehavelse'), instance=request.instance, prefix='dekorasjonInnehavelse')

    # Disable dekorasjonForm
    if not request.user.medlem.tilganger.filter(navn='dekorasjon', kor=request.instance.kor).exists():
        disableForm(dekorasjonForm)

    # Disable dekorasjonInnehavelseFormset
    if not request.user.medlem.tilganger.filter(navn='dekorasjonInnehavelse', kor=request.instance.kor):
        disableForm(dekorasjonInnehavelseFormset)

    # # Disable dekorasjonInnehavelseFormset
    # partiallyDisableFormset(
    #     dekorasjonInnehavelseFormset,
    #     Medlem.objects.filter(
    #         stemmegruppeVerv('vervInnehavelse__verv'), 
    #         vervInnehavelse__verv__kor__tilganger__in=request.user.medlem.tilganger.filter(navn='dekorasjonInnehavelse')
    #     ),
    #     'medlem'
    # )


    if request.method == 'POST':
        if dekorasjonForm.is_valid():
            logAuthorAndSave(dekorasjonForm, request.user.medlem)
            if dekorasjonForm.cleaned_data['DELETE']:
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
        'paginatorPage': getPaginatorPage(request),
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
        messages.error(request, f'Du har ikke tilgang til denne tilgangen')
        return redirect('tilgangListe')
    
    # optionForm = OptionForm(request.GET, fields=['alleAlternativ'])

    # if not optionForm.is_valid():
    #     raise Exception("optionForm var ugyldig, ouf")
    
    TilgangForm = modelform_factory(Tilgang, exclude=['kor'])

    TilgangForm = addReverseM2M(TilgangForm, 'verv')

    TilgangForm = addDeleteCheckbox(TilgangForm)

    tilgangForm = TilgangForm(request.POST or None, instance=request.instance)

    # # Gjør så den bare vise samme kor eller selected, dersom vi ikke bruke alleAlternativ
    # if not optionForm.cleaned_data['alleAlternativ']:
    tilgangForm.fields['verv'].queryset = tilgangForm.fields['verv'].queryset.filter(
        Q(kor=request.instance.kor) | Q(tilganger__pk=request.instance.pk)
    ).distinct()

    # Disable brukt feltet
    disableFormField(tilgangForm, 'brukt')
    
    # Disable navn om brukt
    if request.instance.brukt:
        disableFormField(tilgangForm, 'navn', 'DELETE', helpText='Selv ikke de med tilgang kan endre på en brukt tilgang')
    
    if request.method == 'POST':
        if tilgangForm.is_valid():
            logAuthorAndSave(tilgangForm, request.user.medlem)
            if tilgangForm.cleaned_data['DELETE']:
                messages.info(request, f'{tilgangForm.instance} slettet')
                return redirect('tilgangListe')
            return redirect(request.instance)
    
    return render(request, 'mytxs/instance.html', {
        'forms': [tilgangForm],
        # 'optionForm': optionForm
    })


@login_required()
@user_passes_test(lambda user : 'loggListe' in user.medlem.navBarTilgang, redirect_field_name=None)
def loggListe(request):
    # GET forms skal tydeligvis ikkje ha 'or None' for å få is_valid() uten url params ¯\_(ツ)_/¯
    loggFilterForm = LoggFilterForm(request.GET) #TODO

    if not loggFilterForm.is_valid():
        raise Exception("Søkeformet var ugyldig, ouf")
    
    request.queryset = request.queryset = request.user.medlem.tilgangQueryset(Logg)

    if kor := loggFilterForm.cleaned_data['kor']:
        request.queryset = request.queryset.filter(kor=kor)

    if model := loggFilterForm.cleaned_data['model']:
        request.queryset = request.queryset.filter(model=model)

    if author := loggFilterForm.cleaned_data['author']:
        request.queryset = request.queryset.filter(author=author)

    if pk := loggFilterForm.cleaned_data['pk']:
        request.queryset = request.queryset.filter(instancePK=pk)

    if start := loggFilterForm.cleaned_data['start']:
        request.queryset = request.queryset.filter(timeStamp__date__gte=start)

    if slutt := loggFilterForm.cleaned_data['slutt']:
        request.queryset = request.queryset.filter(timeStamp__date__lte=slutt)
    
    return render(request, 'mytxs/instanceListe.html', {
        'filterForm': loggFilterForm,
        'paginatorPage': getPaginatorPage(request),
        'heading': 'Loggliste'
    })


@login_required()
def logg(request, pk):
    request.instance = Logg.objects.filter(pk=pk).first()

    if not request.user.medlem.harSideTilgang(request.instance):
        messages.error(request, f'Du har ikke tilgang til denne loggen')
        return redirect('loggListe')

    return render(request, 'mytxs/logg.html')
