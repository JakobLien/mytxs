import datetime
from urllib.parse import unquote

from django.contrib import messages
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import AuthenticationForm, SetPasswordForm, UserCreationForm
from django.db.models import Q, F, IntegerField
from django.db.models.functions import Cast
from django.forms import inlineformset_factory, modelform_factory, modelformset_factory
from django.shortcuts import redirect, render, get_object_or_404
from django.urls import reverse
from django.http import Http404

from mytxs import consts
from mytxs.models import Dekorasjon, DekorasjonInnehavelse, Hendelse, Kor, Lenke, Logg, Medlem, Tilgang, Verv, VervInnehavelse, Oppmøte
from mytxs.forms import LoggFilterForm, MedlemFilterForm
from mytxs.utils.formAccess import disableForm, disableFields, partiallyDisableFormsetKor, setRequiredDropdownOptions
from mytxs.utils.formAddField import addDeleteCheckbox, addReverseM2M
from mytxs.utils.formFilter import applyLoggFilterForm, applyMedlemFilterForm
from mytxs.utils.formUtils import filesIfPost, postIfPost, formsetArgs
from mytxs.utils.hashUtils import testHash, getHash
from mytxs.utils.logAuthorUtils import logAuthorAndSave, logAuthorInstance
from mytxs.utils.modelUtils import randomDistinct, vervInnehavelseAktiv, hovedStemmeGruppeVerv, stemmegruppeVerv
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
            
                messages.info(request, 'Login successful')

                if request.GET.get('next'):
                    return redirect(request.GET.get('next'))
            return redirect('login')
        else:
            messages.error(request, 'Login failed')
    
    return render(request, 'mytxs/login.html', {
        'loginForm': AuthenticationForm
    })

def logout(request):
    auth_logout(request)
    return redirect('login')

def registrer(request, medlemPK):
    medlem = Medlem.objects.filter(pk=medlemPK, user=None).first()

    if not medlem or not testHash(request):
        raise Http404('No Medlem matches the given query.')

    userCreationForm = UserCreationForm(request.POST or None)

    if request.method == 'POST':
        if userCreationForm.is_valid():
            user = userCreationForm.save()
            auth_login(request, user)

            medlem.user = user
            medlem.save()
            messages.info(request, f'Opprettet bruker for {medlem}!')
            return redirect(medlem)

    return render(request, 'mytxs/registrer.html', {
        'registerForm': userCreationForm,
        'heading': 'MedlemPK: ' + str(medlemPK)
    })

@login_required
def endrePassord(request):
    endrePassordForm = SetPasswordForm(user=request.user, data=request.POST or None)

    if request.method == 'POST':
        if endrePassordForm.is_valid():
            endrePassordForm.save()
            messages.info(request, 'Passord endret!')
            return redirect('endrePassord')

    return render(request, 'mytxs/endrePassord.html', {
        'endrePassordForm': endrePassordForm,
        'heading': 'Endre passord'
    })


@login_required
def sjekkheftet(request, gruppe, undergruppe=None):
    # Gruperinger er visuelle grupperinger i sjekkheftet på samme side, klassisk stemmegrupper gruppe 
    # argumentet og grupper under refererer til sider på sjekkheftet, altså en for hvert kor også litt ekstra
    korGrupper = consts.bareKorKortTittel
    if request.user.medlem.storkor.kortTittel == 'TKS':
        korGrupper = consts.bareKorKortTittelTKSRekkefølge
    grupper = korGrupper + ['søk', 'jubileum', 'sjekkhefTest']

    grupperinger = {}

    if kor := Kor.objects.filter(kortTittel=gruppe).first():
        # Om det e et kor
        request.undergrupper = [t.navn for t in Tilgang.objects.filter(
            kor=kor,
            sjekkheftetSynlig=True
        )]

        if tilgang := Tilgang.objects.filter(sjekkheftetSynlig=True, navn=undergruppe, kor=kor).first():
            # Om det e en tilgangsdefinert undergruppe vi ser på, f.eks. styret
            request.queryset = Medlem.objects.distinct().filter(
                vervInnehavelseAktiv(),
                vervInnehavelse__verv__kor=kor,
                vervInnehavelse__verv__tilganger=tilgang
            ).all()

            grupperinger = {tilgang.navn:
                request.queryset
            }
        else:
            # Om det e heile koret
            request.queryset = Medlem.objects.distinct().filter(
                vervInnehavelseAktiv(),
                vervInnehavelse__verv__kor=kor
            )
            if kor.kortTittel == 'KK':
                # Grupper KK på SATB
                for stemmegruppe in 'SATB':
                    grupperinger[stemmegruppe] = request.queryset.filter(
                        vervInnehavelse__verv__navn__endswith=stemmegruppe,
                        vervInnehavelse__verv__kor=kor
                    ).all()
            else:
                # Grupper øverige kor på 1S, 2T osv
                for stemmegruppe in Verv.objects.filter(hovedStemmeGruppeVerv(''), kor=kor):
                    grupperinger[stemmegruppe.navn] = request.queryset.filter(
                        vervInnehavelse__verv__navn__endswith=stemmegruppe.navn,
                        vervInnehavelse__verv__kor=kor
                    ).all()
    
    elif gruppe == 'søk':
        request.queryset = Medlem.objects.distinct().filter(
            vervInnehavelseAktiv(),
            stemmegruppeVerv('vervInnehavelse__verv')
        )

        medlemFilterForm = MedlemFilterForm(request.GET)

        request.queryset = applyMedlemFilterForm(medlemFilterForm, request.queryset)

        return render(request, 'mytxs/sjekkheftetSøk.html', {
            'grupperinger': {'': request.queryset.all()}, 
            'grupper': grupper,
            'gruppe': gruppe,
            'heading': 'Sjekkheftet',
            'filterForm': medlemFilterForm
        })

    elif gruppe == 'jubileum':
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
        
        grupperinger = {'':
            request.queryset.order_by(Cast((F('fødselsdato__month') * 31 + F('fødselsdato__day') - today + 403), output_field=IntegerField()) % 403).all()
        }
        # Gud veit koffor serveren ikke ønske å tolke enten day eller month som en integer i utgangspunktet. Har ikke det problemet lokalt...

    elif gruppe == 'sjekkhefTest':
        request.queryset = randomDistinct(
            Medlem.objects.filter(
                vervInnehavelseAktiv(),
                stemmegruppeVerv('vervInnehavelse__verv'),
                ~Q(bilde='')
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

    request.queryset = applyMedlemFilterForm(medlemFilterForm, request.queryset)

    NyttMedlemForm = modelform_factory(Medlem, fields=['fornavn', 'mellomnavn', 'etternavn'])

    nyttMedlemForm = NyttMedlemForm(request.POST or None, prefix='nyttMedlem', initial={
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
        'heading': 'Medlemmer',
        'newForm': nyttMedlemForm
    })


@login_required()
def medlem(request, medlemPK):
    request.instance = Medlem.objects.filter(pk=medlemPK).first()

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
        postIfPost(request, 'medlemdata'), 
        filesIfPost(request, 'medlemdata'), 
        instance=request.instance, 
        prefix='medlemdata'
    )
    vervInnehavelseFormset = VervInnehavelseFormset(
        postIfPost(request, 'vervInnehavelse'), 
        instance=request.instance, 
        prefix='vervInnehavelse'
    )
    dekorasjonInnehavelseFormset = DekorasjonInnehavelseFormset(
        postIfPost(request, 'dekorasjonInnehavelse'), 
        instance=request.instance, 
        prefix='dekorasjonInnehavelse'
    )

    # Disable medlemsDataForm: Om det ikkje e deg sjølv, eller noen du har tilgang til 
    # (alle med medlemsdata tilgangen kan redigere folk som ikke har et storkor)
    if not (request.instance == request.user.medlem or
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
            logAuthorAndSave(medlemsDataForm, request.user.medlem)
        if vervInnehavelseFormset.is_valid():
            logAuthorAndSave(vervInnehavelseFormset, request.user.medlem)
        if dekorasjonInnehavelseFormset.is_valid():
            logAuthorAndSave(dekorasjonInnehavelseFormset, request.user.medlem)
        if medlemsDataForm.is_valid() and vervInnehavelseFormset.is_valid() and dekorasjonInnehavelseFormset.is_valid():
            return redirect(request.instance)

    kwargs = {}

    if not request.instance.user:
        kwargs['registreringLink'] = request.get_host() + reverse('registrer', args=[request.instance.pk]) + '?hash=' + \
            getHash(reverse('registrer', args=[request.instance.pk]))

    return render(request, 'mytxs/medlem.html', {
        'forms': [medlemsDataForm], 
        'formsets': [vervInnehavelseFormset, dekorasjonInnehavelseFormset],
        **kwargs
    })


@login_required()
def semesterplan(request, kor):
    if not request.user.medlem.kor.filter(kortTittel=kor).exists():
        messages.error(request, f'Du har ikke tilgang til andre kors kalender')
        return redirect(request.user.medlem)

    if request.GET.get('gammelt') or request.GET.get('iCal'):
        request.queryset = Hendelse.objects.filter(kor__kortTittel=kor)
    else:
        request.queryset = Hendelse.objects.filter(kor__kortTittel=kor, startDate__gte=datetime.datetime.today())

    # Håndter ical dersom det var det
    if request.GET.get('iCal'):
        file_data = request.queryset.generateICal()
        return downloadFile(f'{kor}.ics', file_data)
    
    return render(request, 'mytxs/semesterplan.html')

@login_required()
def meldFravær(request, hendelsePK):
    hendelse = Hendelse.objects.filter(pk=hendelsePK).first()

    if not hendelse:
        messages.error(request, 'Hendelse ikke funnet')
        return redirect('semesterplan', kor=hendelse.kor.kortTittel)

    if not hendelse.getMedlemmer().filter(pk=request.user.medlem.pk).exists():
        messages.error(request, 'Du er ikke blant de som skal føres fravær på')
        return redirect('semesterplan', kor=hendelse.kor.kortTittel)

    request.instance = Oppmøte.objects.filter(medlem=request.user.medlem, hendelse=hendelse).first()

    if not request.instance:
        messages.error(request, 'Ditt oppmøte finnes ikke selv om det burde det, meld fra om dette!')
        return redirect('semesterplan', kor=hendelse.kor.kortTittel)

    OppmøteForm = modelform_factory(Oppmøte, fields=['melding', 'ankomst', 'gyldig', 'fravær'])

    oppmøteForm = OppmøteForm(request.POST or None, instance=request.instance, prefix='oppmøte')

    disableFields(oppmøteForm, 'gyldig', 'fravær')

    if request.method == 'POST':
        if oppmøteForm.is_valid():
            logAuthorAndSave(oppmøteForm, request.user.medlem)
            return redirect('meldFravær', hendelsePK)

    return render(request, 'mytxs/instance.html', {
        'forms': [oppmøteForm],
        'formsets': []
    })


@login_required()
def egenFøring(request, hendelsePK):
    hendelse = Hendelse.objects.filter(pk=hendelsePK).first()

    if not hendelse:
        messages.error(request, 'Hendelse ikke funnet')
        return redirect('semesterplan', kor=hendelse.kor.kortTittel)
    
    if hendelse.varighet == None:
        messages.error(request, 'Kan ikke føre fravær på hendelser uten varighet')
        return redirect('semesterplan', kor=hendelse.kor.kortTittel)
    
    if not hendelse.getMedlemmer().filter(pk=request.user.medlem.pk).exists():
        messages.error(request, 'Du er ikke blant de som skal føres fravær på')
        return redirect('semesterplan', kor=hendelse.kor.kortTittel)
    
    if not testHash(request):
        messages.error(request, 'Feil eller manglende hash')
        return redirect('semesterplan', kor=hendelse.kor.kortTittel)
    
    # get_or_create bare at man ikke lagre det

    request.instance = Oppmøte.objects.filter(medlem=request.user.medlem, hendelse=hendelse).first()
    
    if not request.instance:
        messages.error(request, 'Ditt oppmøte finnes ikke selv om det burde det, meld fra om dette!')
        return redirect('semesterplan', kor=hendelse.kor.kortTittel)
    
    if abs(datetime.datetime.now() - hendelse.start).total_seconds() / 60 > 30 or datetime.datetime.now() > hendelse.slutt:
        messages.error(request, 'For sent eller tidlig å føre fravær selv')
        return redirect('semesterplan', kor=hendelse.kor.kortTittel)

    if request.instance.fravær:
        messages.info(request, f'Fravær allerede ført med {request.instance.fravær} minutter forsentkomming!')
        return redirect('semesterplan', kor=hendelse.kor.kortTittel)

    request.instance.fravær = int(max(
        (min(hendelse.slutt, datetime.datetime.now()) - hendelse.start).total_seconds() / 60, 
        0
    ))

    request.instance.save()
    
    logAuthorInstance(request.instance, request.user.medlem)

    messages.info(request, f'Fravær ført med {request.instance.fravær} minutter forsentkomming!')
    
    return redirect('semesterplan', kor=hendelse.kor.kortTittel)

@login_required()
def lenker(request):
    request.queryset = Lenke.objects.distinct().filter(
        Q(kor__in=request.user.medlem.kor) | # Lenker fra kor man er i
        Q(kor__tilganger__in=request.user.medlem.tilganger.filter(navn='lenke')) # Lenker man kan endre på
    )

    if request.user.medlem.kor.exists(): # Om man er minst et kor, hiv på Sangern sine lenker
        request.queryset |= Lenke.objects.distinct().filter(kor__kortTittel='Sangern')

    LenkerFormset = modelformset_factory(Lenke, exclude=[], can_delete=True, extra=1)

    lenkerFormset = LenkerFormset(postIfPost(request, 'lenker'), prefix='lenker', 
        queryset=Lenke.objects.filter(kor__tilganger__in=request.user.medlem.tilganger.filter(navn='lenke')))

    # Set kor alternativene
    setRequiredDropdownOptions(lenkerFormset, 'kor', Kor.objects.filter(tilganger__in=request.user.medlem.tilganger.filter(navn='lenke')))

    if request.method == 'POST':
        if lenkerFormset.is_valid():
            logAuthorAndSave(lenkerFormset, request.user.medlem)
            return redirect('lenker')
    
    return render(request, 'mytxs/lenker.html', {
        'formsets': [lenkerFormset],
        'heading': 'Lenker',
    })

@login_required()
@user_passes_test(lambda user : 'vervListe' in user.medlem.navBarTilgang, redirect_field_name=None)
def vervListe(request):
    NyttVervForm = modelform_factory(Verv, fields=['navn', 'kor'])

    # optionForm = OptionForm(request.GET, fields=['alleAlternativ'])

    # if not optionForm.is_valid():
    #     raise Exception('optionForm var ugyldig, ouf')
    
    request.queryset = request.user.medlem.tilgangQueryset(Verv)#, optionForm.cleaned_data['alleAlternativ'])

    nyttVervForm = NyttVervForm(request.POST or None, prefix='nyttVerv')
    
    # Set kor alternativene
    setRequiredDropdownOptions(nyttVervForm, 'kor', Kor.objects.filter(tilganger__in=request.user.medlem.tilganger.filter(navn='verv')))

    if request.method == 'POST':
        if nyttVervForm.is_valid():
            logAuthorAndSave(nyttVervForm, request.user.medlem)
            messages.info(request, f'{nyttVervForm.instance} opprettet!')
            return redirect(nyttVervForm.instance)
    
    return render(request, 'mytxs/instanceListe.html', {
        'newForm': nyttVervForm,
        'paginatorPage': getPaginatorPage(request),
        'heading': 'Verv',
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
    
    vervForm = VervForm(postIfPost(request, 'vervForm'), instance=request.instance, prefix='vervForm')
    vervInnehavelseFormset = VervInnehavelseFormset(postIfPost(request, 'vervInnehavelse'), instance=request.instance, prefix='vervInnehavelse')
    
    # Disable vervForm dersom de ikke tilgang eller om det er stemmegruppeverv
    if not (request.user.medlem.tilganger.filter(navn='verv', kor=request.instance.kor).exists()):
        disableFields(vervForm, 'navn', 'DELETE')
    if request.instance.bruktIKode:
        disableFields(vervForm, 'navn', 'DELETE', helpText='Selv ikke de med tilgang kan endre på et brukt verv')

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
    vervForm.fields['tilganger'].setEnableQuerysetKor(
        Kor.objects.filter(tilganger__in=request.user.medlem.tilganger.filter(navn='tilgang')),
        request.instance.tilganger.all()
    )

    if request.method == 'POST':
        if vervForm.is_valid():
            logAuthorAndSave(vervForm, request.user.medlem)
            if vervForm.cleaned_data['DELETE']:
                messages.info(request, f'{vervForm.instance} slettet')
                return redirect('vervListe')
        if vervInnehavelseFormset.is_valid():
            logAuthorAndSave(vervInnehavelseFormset, request.user.medlem)
        
        if vervForm.is_valid() and vervInnehavelseFormset.is_valid():
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

    nyDekorasjonForm = NyDekorasjonForm(request.POST or None, prefix='nyDekorasjon')
    
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
        'heading': 'Dekorasjoner'
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

    dekorasjonForm = DekorasjonForm(postIfPost(request, 'dekorasjonForm'), instance=request.instance, prefix='dekorasjonForm')
    dekorasjonInnehavelseFormset = DekorasjonInnehavelseFormset(postIfPost(request, 'dekorasjonInnehavelse'), instance=request.instance, prefix='dekorasjonInnehavelse')

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
        if dekorasjonInnehavelseFormset.is_valid():
            logAuthorAndSave(dekorasjonInnehavelseFormset, request.user.medlem)

        if dekorasjonForm.is_valid() and dekorasjonInnehavelseFormset.is_valid():
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

    nyTilgangForm = NyTilgangForm(request.POST or None, prefix='nyTilgang')
    
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
        'heading': 'Tilganger'
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
    #     raise Exception('optionForm var ugyldig, ouf')
    
    TilgangForm = modelform_factory(Tilgang, exclude=['kor', 'bruktIKode'])

    TilgangForm = addReverseM2M(TilgangForm, 'verv')

    TilgangForm = addDeleteCheckbox(TilgangForm)

    tilgangForm = TilgangForm(request.POST or None, instance=request.instance)

    # # Gjør så den bare vise samme kor eller selected, dersom vi ikke bruke alleAlternativ
    # if not optionForm.cleaned_data['alleAlternativ']:
    tilgangForm.fields['verv'].queryset = tilgangForm.fields['verv'].queryset.filter(
        Q(kor=request.instance.kor) | Q(tilganger__pk=request.instance.pk)
    ).distinct()

    # Disable navn og DELETE om brukt
    if request.instance.bruktIKode:
        disableFields(tilgangForm, 'navn', 'DELETE', helpText='Selv ikke de med tilgang kan endre på en brukt tilgang')
    
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
    loggFilterForm = LoggFilterForm(request.GET)

    request.queryset = request.user.medlem.tilgangQueryset(Logg)

    request.queryset = applyLoggFilterForm(loggFilterForm, request.queryset)

    return render(request, 'mytxs/instanceListe.html', {
        'filterForm': loggFilterForm,
        'paginatorPage': getPaginatorPage(request),
        'heading': 'Logger'
    })


@login_required()
def logg(request, loggPK):
    request.instance = Logg.objects.filter(pk=loggPK).first()

    if not request.user.medlem.harSideTilgang(request.instance):
        messages.error(request, f'Du har ikke tilgang til denne loggen')
        return redirect('loggListe')

    return render(request, 'mytxs/logg.html')


@login_required()
@user_passes_test(lambda user : 'hendelseListe' in user.medlem.navBarTilgang, redirect_field_name=None)
def hendelseListe(request):
    request.queryset = request.user.medlem.tilgangQueryset(Hendelse)

    NyHendelseForm = modelform_factory(Hendelse, fields=['navn', 'kor', 'kategori', 'startDate'])

    nyHendelseForm = NyHendelseForm(request.POST or None, prefix='nyttEvent')
    
    # Set kor alternativene
    setRequiredDropdownOptions(nyHendelseForm, 'kor', Kor.objects.filter(tilganger__in=request.user.medlem.tilganger.filter(navn='semesterplan')))

    if request.method == 'POST':
        if nyHendelseForm.is_valid():
            logAuthorAndSave(nyHendelseForm, request.user.medlem)
            messages.info(request, f'{nyHendelseForm.instance} opprettet!')
            return redirect(nyHendelseForm.instance)

    return render(request, 'mytxs/instanceListe.html', {
        'paginatorPage': getPaginatorPage(request),
        'newForm': nyHendelseForm,
        'heading': 'Hendelser'
    })

@login_required()
def hendelse(request, hendelsePK):
    request.instance = Hendelse.objects.filter(pk=hendelsePK).first()

    if not request.instance:
        messages.error(request, 'Hendelse ikke funnet')
        return redirect('hendelseListe')
    
    if not request.user.medlem.harSideTilgang(request.instance):
        messages.error(request, f'Du har ikke tilgang til denne hendelsen')
        return redirect('hendelseListe')
    
    HendelseForm = modelform_factory(Hendelse, exclude=['kor'])
    OppmøteFormset = inlineformset_factory(Hendelse, Oppmøte, exclude=[], extra=0)

    HendelseForm = addDeleteCheckbox(HendelseForm)

    hendelseForm = HendelseForm(postIfPost(request, 'hendelse'), instance=request.instance, prefix='hendelse')
    oppmøteFormset = OppmøteFormset(postIfPost(request, 'oppmøte'), instance=request.instance, prefix='oppmøte')

    if not request.user.medlem.tilganger.filter(navn='semesterplan', kor=request.instance.kor).exists():
        disableForm(hendelseForm)

    if not request.user.medlem.tilganger.filter(navn='fravær', kor=request.instance.kor).exists():
        disableForm(oppmøteFormset)
    elif not request.instance.varighet:
        disableFields(oppmøteFormset, 'fravær')

    if request.GET.get('qrKode'):
        file_data = request.queryset.generateICal()
        return downloadFile(f'{hendelse.kor.kortTittel}.ics', file_data)

    if request.method == 'POST':
        # Rekkefølgen her e viktig for at bruker skal kunne slette oppmøter nødvendig for å flytte hendelse på en submit:)
        if oppmøteFormset.is_valid():
            logAuthorAndSave(oppmøteFormset, request.user.medlem)
        if hendelseForm.is_valid():
            logAuthorAndSave(hendelseForm, request.user.medlem)
            if hendelseForm.cleaned_data['DELETE']:
                messages.info(request, f'{hendelseForm.instance} slettet')
                return redirect('hendelseListe')
        # Formsets som har lengde 0 er tydeligvis invalid, så for at ting ska funk slik man forvente må vi hiv på denne sjekken
        # Særlig viktig fordi her e det lett å end opp med ingen oppmøter spørs på når man tar det (pga permisjon o.l.)
        if hendelseForm.is_valid() and (oppmøteFormset.is_valid() or len(oppmøteFormset.forms) == 0):
            return redirect(request.instance)
    
    kwargs = {}

    if request.instance.startTime != None and abs(datetime.datetime.now() - request.instance.start).total_seconds() / 60 <= 30:
        kwargs['egenFøringLink'] = f'https://zxing.org/w/chart?cht=qr&chs=350x350&chld=L&choe=UTF-8&chl=http://' + \
            request.get_host() + unquote(reverse('egenFøring', args=[request.instance.pk])) + '?hash=' + \
            getHash(reverse('egenFøring', args=[request.instance.pk]))

    return render(request, 'mytxs/hendelse.html', {
        'forms': [hendelseForm],
        'formsets': [oppmøteFormset],
        **kwargs
    })
