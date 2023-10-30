import datetime

from django.contrib import messages
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import AuthenticationForm, SetPasswordForm, UserCreationForm
from django.db.models import Q, F, IntegerField
from django.db.models.functions import Cast
from django.forms import inlineformset_factory, modelform_factory, modelformset_factory
from django.shortcuts import redirect, render
from django.urls import reverse
from django.http import Http404 

from mytxs import consts
from mytxs.management.commands.transfer import transferByJWT
from mytxs.models import Dekorasjon, DekorasjonInnehavelse, Hendelse, Kor, Lenke, Logg, Medlem, MedlemQuerySet, Tilgang, Turne, Verv, VervInnehavelse, Oppmøte
from mytxs.forms import HendelseFilterForm, LoggFilterForm, MedlemFilterForm, NavnKorFilterForm, TurneFilterForm
from mytxs.utils.formAccess import addHelpText, disableBrukt, disableFields, disableFormMedlem, removeFields
from mytxs.utils.formAddField import addDeleteCheckbox, addReverseM2M
from mytxs.utils.lazyDropdown import lazyDropdown
from mytxs.utils.formUtils import filesIfPost, postIfPost, inlineFormsetArgs
from mytxs.utils.hashUtils import addHash, testHash
from mytxs.utils.logAuthorUtils import logAuthorAndSave, logAuthorInstance
from mytxs.utils.modelUtils import randomDistinct, vervInnehavelseAktiv, stemmegruppeVerv
from mytxs.utils.pagination import getPaginatedInlineFormSet, addPaginatorPage
from mytxs.utils.utils import downloadVCard
from mytxs.utils.viewUtils import downloadFile, harTilgang, redirectToInstance
from mytxs.utils.modelUtils import annotateInstance

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
            return redirect(request.get_full_path())
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


def overfør(request, jwt):
    medlem = transferByJWT(jwt)

    if not medlem:
        messages.error(request, 'Overføring feilet')
        redirect('login')

    messages.info(request, 'Data overført!')
    
    if not medlem.user:
        return redirect(addHash(reverse('registrer', args=[medlem.pk])))
    else:
        return redirect('login')


@login_required
def endrePassord(request):
    endrePassordForm = SetPasswordForm(user=request.user, data=request.POST or None)

    if request.method == 'POST':
        if endrePassordForm.is_valid():
            endrePassordForm.save()
            messages.info(request, 'Passord endret!')
            return redirect(request.get_full_path())

    return render(request, 'mytxs/endrePassord.html', {
        'endrePassordForm': endrePassordForm,
        'heading': 'Endre passord'
    })


@harTilgang
def sjekkheftet(request, gruppe, undergruppe=None):
    # Gruppe og undergruppe argumentene refererer til sider på sjekkheftet, altså en for hvert kor ++
    # Gruperinger er visuelle grupperinger i sjekkheftet på samme side, klassisk stemmegrupper. 
    grupperinger = {}

    if kor := Kor.objects.filter(kortTittel=gruppe).first():
        request.queryset = Medlem.objects.distinct().annotateKarantenekor(kor=kor)
        if tilgang := Tilgang.objects.filter(sjekkheftetSynlig=True, navn=undergruppe, kor=kor).first():
            # Om det e en tilgangsdefinert undergruppe vi ser på, f.eks. styret
            request.queryset = request.queryset.filter(
                vervInnehavelseAktiv(),
                vervInnehavelser__verv__kor=kor,
                vervInnehavelser__verv__tilganger=tilgang
            ).order_by(*Medlem._meta.ordering).prefetchVervDekorasjonKor()

            grupperinger = {'': request.queryset}
        else:
            # Om det e heile koret
            request.queryset = request.queryset.filter(
                stemmegruppeVerv('vervInnehavelser__verv'),
                vervInnehavelseAktiv(),
                vervInnehavelser__verv__kor=kor
            )
            if kor.stemmefordeling == 'SATB':
                # Grupper Knauskoret på SATB
                for stemmegruppe in 'SATB':
                    grupperinger[stemmegruppe] = request.queryset.filter(
                        vervInnehavelser__verv__kor=kor, # Denne linjen ser dumt ut, men det må til
                        vervInnehavelser__verv__navn__endswith=stemmegruppe,
                    ).order_by(*Medlem._meta.ordering).prefetchVervDekorasjonKor()
            else:
                # Grupper øverige kor på 1S, 2T osv
                for stemmegruppe in Verv.objects.filter(navn__in=consts.hovedStemmegrupper, kor=kor):
                    grupperinger[stemmegruppe.navn] = request.queryset.filter(
                        vervInnehavelser__verv__kor=kor, # Denne linjen ser dumt ut, men det må til
                        vervInnehavelser__verv__navn__endswith=stemmegruppe.navn,
                    ).order_by(*Medlem._meta.ordering).prefetchVervDekorasjonKor()

    elif gruppe == 'søk':
        request.queryset = Medlem.objects.distinct().annotateKarantenekor(storkor=True).filter(
            vervInnehavelseAktiv(),
            stemmegruppeVerv('vervInnehavelser__verv')
        )

        medlemFilterForm = MedlemFilterForm(request.GET)

        request.queryset = medlemFilterForm.applyFilter(request.queryset)\
            .order_by(*Medlem._meta.ordering).prefetchVervDekorasjonKor()

        if vCardRes := downloadVCard(request):
            return vCardRes

        return render(request, 'mytxs/sjekkheftetSøk.html', {
            'grupperinger': {'': request.queryset}, 
            'heading': 'Sjekkheftet',
            'filterForm': medlemFilterForm
        })

    elif gruppe == 'jubileum':
        request.queryset = Medlem.objects.distinct().annotateKarantenekor(storkor=True).annotate(
            sjekkhefteSynligFødselsdatoBit=F('sjekkhefteSynlig').bitand(1)
        ).filter(
            vervInnehavelseAktiv(), 
            stemmegruppeVerv('vervInnehavelser__verv'),
            fødselsdato__isnull=False,
            sjekkhefteSynligFødselsdatoBit__gte=1
        )

        # Måten dette funke e at for å produser en index med tilsvarende sortering som
        # date_of_year (som ikke finnes i Django), gange vi måneden med 31, og legger på dagen.
        # Så må vi bare ta modulus 403 (den maksimale 12*31+31), også har vi det:)
        today = datetime.date.today()
        today = today.month*31 + today.day

        request.queryset = request.queryset\
            .order_by(Cast((F('fødselsdato__month') * 31 + F('fødselsdato__day') - today + 403), output_field=IntegerField()) % 403)\
            .prefetchVervDekorasjonKor()

        grupperinger = {'': request.queryset}

    elif gruppe == 'sjekkhefTest':
        request.queryset = randomDistinct(
            Medlem.objects.filter(
                vervInnehavelseAktiv(),
                stemmegruppeVerv('vervInnehavelser__verv'),
                ~Q(bilde='')
            ), 20
        )

        return render(request, 'mytxs/sjekkhefTest.html', {
            'heading': 'Sjekkheftet'
        })

    if vCardRes := downloadVCard(request):
        return vCardRes

    return render(request, 'mytxs/sjekkheftet.html', {
        'grupperinger': grupperinger, 
        'heading': 'Sjekkheftet'
    })


@harTilgang(querysetModel=Medlem)
def medlemListe(request):
    medlemFilterForm = MedlemFilterForm(request.GET)

    request.queryset = medlemFilterForm.applyFilter(request.queryset)

    NyttMedlemForm = modelform_factory(Medlem, fields=['fornavn', 'mellomnavn', 'etternavn'])

    nyttMedlemForm = NyttMedlemForm(request.POST or None, prefix='nyttMedlem', initial={
        'fornavn': '', 'mellomnavn': '', 'etternavn': ''
    })

    if disableFormMedlem(request.user.medlem, nyttMedlemForm):
        # Krev at man må ha tversAvKor tilgangen for å opprett nye medlemma. 
        # Om ikkje vil man ikkje ha tilgang til det nye medlemmet, siden det er uten kormedlemskap
        if not request.user.medlem.tilganger.filter(navn='tversAvKor').exists():
            disableFields(nyttMedlemForm)

    if request.method == 'POST':
        if nyttMedlemForm.is_valid():
            logAuthorAndSave(nyttMedlemForm, request.user.medlem)
            messages.info(request, f'{nyttMedlemForm.instance} opprettet!')
            return redirect(nyttMedlemForm.instance)
    
    addPaginatorPage(request)
    
    return render(request, 'mytxs/instanceListe.html', {
        'filterForm': medlemFilterForm,
        'heading': 'Medlemmer',
        'newForm': nyttMedlemForm
    })


@harTilgang(instanceModel=Medlem, extendAccess=lambda req: Medlem.objects.filter(pk=req.user.medlem.pk))
def medlem(request, medlemPK):
    if not request.user.medlem.redigerTilgangQueryset(Medlem).contains(request.instance) and request.user.medlem != request.instance:
        # Om du ikke har redigeringstilgang på medlemmet, skjul dataen demmers
        MedlemsDataForm = modelform_factory(Medlem, fields=['fornavn', 'mellomnavn', 'etternavn'])
    else:
        # Om du har tilgang ikke fordi det e deg sjølv, også vis gammeltMedlemsnummer og død feltan
        if request.user.medlem.redigerTilgangQueryset(Medlem, includeExtended=False).contains(request.instance):
            MedlemsDataForm = modelform_factory(Medlem, exclude=['user'])
        else:
            MedlemsDataForm = modelform_factory(Medlem, exclude=['user', 'gammeltMedlemsnummer', 'død'])
    VervInnehavelseFormset = inlineformset_factory(Medlem, VervInnehavelse, formset=getPaginatedInlineFormSet(request), **inlineFormsetArgs)
    DekorasjonInnehavelseFormset = inlineformset_factory(Medlem, DekorasjonInnehavelse, formset=getPaginatedInlineFormSet(request), **inlineFormsetArgs)

    MedlemsDataForm = addReverseM2M(MedlemsDataForm, 'turneer')

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

    if disableFormMedlem(request.user.medlem, medlemsDataForm):
        if 'gammeltMedlemsnummer' in medlemsDataForm.fields:
            disableFields(medlemsDataForm, 'gammeltMedlemsnummer')
        if 'notis' in medlemsDataForm.fields and not request.user.medlem.redigerTilgangQueryset(Medlem, includeExtended=False).contains(request.instance):
            disableFields(medlemsDataForm, 'notis')
        if 'sjekkhefteSynlig' in medlemsDataForm.fields and request.instance != request.user.medlem:
            disableFields(medlemsDataForm, 'sjekkhefteSynlig')
    
    disableFormMedlem(request.user.medlem, vervInnehavelseFormset)

    disableFormMedlem(request.user.medlem, dekorasjonInnehavelseFormset)

    if res := lazyDropdown(request, vervInnehavelseFormset, 'verv'):
        return res
    if res := lazyDropdown(request, dekorasjonInnehavelseFormset, 'dekorasjon'):
        return res

    if request.method == 'POST':
        if medlemsDataForm.is_valid():
            logAuthorAndSave(medlemsDataForm, request.user.medlem)
        if vervInnehavelseFormset.is_valid():
            logAuthorAndSave(vervInnehavelseFormset, request.user.medlem)
        if dekorasjonInnehavelseFormset.is_valid():
            logAuthorAndSave(dekorasjonInnehavelseFormset, request.user.medlem)
        if medlemsDataForm.is_valid() and vervInnehavelseFormset.is_valid() and dekorasjonInnehavelseFormset.is_valid():
            return redirectToInstance(request)

    if not request.instance.user:
        request.registreringLink = request.get_host() + addHash(reverse('registrer', args=[request.instance.pk]))

    return render(request, 'mytxs/medlem.html', {
        'forms': [medlemsDataForm], 
        'formsets': [vervInnehavelseFormset, dekorasjonInnehavelseFormset],
    })


@harTilgang(querysetModel=Hendelse)
def semesterplan(request, kor):
    if not request.user.medlem.aktiveKor.filter(kortTittel=kor).exists():
        messages.error(request, f'Du har ikke tilgang til andre kors kalender')
        return redirect(request.user.medlem)
    
    request.queryset = Hendelse.objects.filter(kor__kortTittel=kor)

    if not request.GET.get('gammelt'):
        request.queryset = request.queryset.filter(startDate__gte=datetime.datetime.today())

    request.iCalLink = 'http://' + request.get_host() + addHash(reverse('iCal', args=[kor, request.user.medlem.pk]))

    annotateInstance(request.user.medlem, MedlemQuerySet.annotateFravær, kor=kor)
    
    return render(request, 'mytxs/semesterplan.html', { 'medlem': request.user.medlem })


def iCal(request, kor, medlemPK):
    medlem = Medlem.objects.filter(pk=medlemPK).first()

    if not medlem:
        messages.error(request, f'Dette medlemmet finnes ikke.')
        return redirect('login')
    
    if not testHash(request):
        messages.error(request, 'Feil eller manglende hash')
        return redirect('login')
    
    if not medlem.aktiveKor.filter(kortTittel=kor).exists():
        messages.error(request, 'Du har ikke tilgang til dette korets kalender')
        return redirect('login')

    content = Hendelse.objects.filter(kor__kortTittel=kor, startDate__gte=datetime.datetime.today()-datetime.timedelta(days=90)).generateICal(medlemPK)
    return downloadFile(f'MyTXS-{kor}.ics', content, content_type='text/calendar')


@harTilgang(instanceModel=Oppmøte, lookupToArgNames={'medlem__pk': 'medlemPK', 'hendelse__pk': 'hendelsePK'}, 
    extendAccess=lambda req: Oppmøte.objects.filter(medlem__pk=req.user.medlem.pk))
def meldFravær(request, medlemPK, hendelsePK):
    OppmøteForm = modelform_factory(Oppmøte, fields=['melding', 'ankomst', 'gyldig', 'fravær'])

    oppmøteForm = OppmøteForm(request.POST or None, instance=request.instance, prefix='oppmøte')

    disableFormMedlem(request.user.medlem, oppmøteForm)

    if not request.user.medlem.redigerTilgangQueryset(Oppmøte, includeExtended=False).contains(request.instance):
        disableFields(oppmøteForm, 'gyldig', 'fravær')

    if request.method == 'POST':
        if oppmøteForm.is_valid():
            logAuthorAndSave(oppmøteForm, request.user.medlem)
            return redirectToInstance(request)

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
    
    if not testHash(request):
        messages.error(request, 'Feil eller manglende hash')
        return redirect('semesterplan', kor=hendelse.kor.kortTittel)
    
    request.instance = Oppmøte.objects.filter(medlem=request.user.medlem, hendelse=hendelse).first()
    
    if not request.instance:
        if not hendelse.medlemmer.contains(request.user.medlem):
            messages.error(request, 'Du er ikke blant de som skal føres fravær på')
            return redirect('semesterplan', kor=hendelse.kor.kortTittel)
        else:
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
    
    request.instance.save() # Ikke fjern meg!
    logAuthorInstance(request.instance, request.user.medlem)

    messages.info(request, f'Fravær ført med {request.instance.fravær} minutter forsentkomming!')
    
    return redirect('semesterplan', kor=hendelse.kor.kortTittel)


@harTilgang
def fraværListe(request, kor):
    request.queryset = Medlem.objects.filterIkkePermitert(kor=Kor.objects.get(kortTittel=kor))
    
    request.queryset = request.queryset.annotateFravær(kor=kor)

    request.queryset = request.queryset.order_by(*Medlem._meta.ordering)
    
    return render(request, 'mytxs/fraværListe.html', {
        'heading': 'Fravær'
    })


@login_required
@user_passes_test(lambda user : user.medlem.navBar.get('fraværListe'), redirect_field_name=None)
def fravær(request, kor, medlemPK):
    medlem = Medlem.objects.get(pk=medlemPK)

    request.queryset = Hendelse.objects.filter(kor__kortTittel=kor)

    if not request.GET.get('gammelt'):
        request.queryset = request.queryset.filter(startDate__gte=datetime.datetime.today())

    annotateInstance(medlem, MedlemQuerySet.annotateFravær, kor)
    
    return render(request, 'mytxs/semesterplan.html', {
        'medlem': medlem,
        'heading': f'Semesterplan for {medlem}',
        'skipFraværLink': True
    })


@harTilgang(querysetModel=Hendelse)
def hendelseListe(request):
    hendelseFilterForm = HendelseFilterForm(request.GET)

    request.queryset = hendelseFilterForm.applyFilter(request.queryset)

    NyHendelseForm = modelform_factory(Hendelse, fields=['navn', 'kor', 'kategori', 'startDate'])

    nyHendelseForm = NyHendelseForm(request.POST or None, prefix='nyHendelse')
    
    disableFormMedlem(request.user.medlem, nyHendelseForm)

    if request.method == 'POST':
        if nyHendelseForm.is_valid():
            logAuthorAndSave(nyHendelseForm, request.user.medlem)
            messages.info(request, f'{nyHendelseForm.instance} opprettet!')
            return redirect(nyHendelseForm.instance)

    addPaginatorPage(request)
    
    return render(request, 'mytxs/instanceListe.html', {
        'filterForm': hendelseFilterForm,
        'newForm': nyHendelseForm,
        'heading': 'Hendelser'
    })


@harTilgang(instanceModel=Hendelse)
def hendelse(request, hendelsePK):
    HendelseForm = modelform_factory(Hendelse, exclude=['kor'])
    if not request.GET.get('alleOppmøter'):
        OppmøteFormset = inlineformset_factory(Hendelse, Oppmøte, exclude=[], extra=0, can_delete=True, formset=getPaginatedInlineFormSet(request))
    else:
        OppmøteFormset = inlineformset_factory(Hendelse, Oppmøte, exclude=[], extra=0, can_delete=True)

    HendelseForm = addDeleteCheckbox(HendelseForm)

    hendelseForm = HendelseForm(postIfPost(request, 'hendelse'), instance=request.instance, prefix='hendelse')
    oppmøteFormset = OppmøteFormset(postIfPost(request, 'oppmøte'), instance=request.instance, prefix='oppmøte')

    disableFormMedlem(request.user.medlem, hendelseForm)

    if disableFormMedlem(request.user.medlem, oppmøteFormset): 
        disableFields(oppmøteFormset, 'medlem')
        if not request.instance.varighet:
            disableFields(oppmøteFormset, 'fravær')

        addHelpText(oppmøteFormset, 'DELETE', helpText=\
            'Dette medlemmet skal ifølge stemmegruppeverv og permisjon ikke være på denne hendelsen. '+
            'Følgelig hadde oppmøtet vært slettet automatisk om de ikke hadde en fraværsmelding eller en fraværsføring.')        
        for form in oppmøteFormset.forms:
            if form.instance.medlem in oppmøteFormset.instance.medlemmer:
                # Dette er et medlem som egentlig ikke har stemmegrupper/permisjon kombinasjon 
                # til å ha dette opmøtet, men vi vil ikke automatisk slette dataen på oppmøtet heller.
                removeFields(form, 'DELETE')
    else:
        removeFields(oppmøteFormset, 'DELETE')

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
            return redirectToInstance(request)

    if request.instance.startTime != None and abs(datetime.datetime.now() - request.instance.start).total_seconds() / 60 <= 30:
        request.egenFøringLink = consts.qrCodeLinkPrefix + 'http://' + request.get_host() + addHash(reverse('egenFøring', args=[request.instance.pk]))

    return render(request, 'mytxs/hendelse.html', {
        'forms': [hendelseForm],
        'formsets': [oppmøteFormset],
    })


@login_required()
def lenker(request):
    if request.user.medlem.aktiveKor.exists():
        request.queryset = Lenke.objects.distinct().filter(
            Q(kor__in=request.user.medlem.aktiveKor) | Q(kor__kortTittel='Sangern'), 
            synlig=True
        )
    else:
        request.queryset = Lenke.objects.none()

    # Om man ikke har tilgang til å redigere noen lenker, bare render her uten formsettet
    if not request.user.medlem.tilganger.filter(navn='lenke').exists():
        return render(request, 'mytxs/lenker.html', {
            'heading': 'Lenker',
        })

    LenkerFormset = modelformset_factory(Lenke, exclude=[], can_delete=True, extra=1)

    lenkerFormset = LenkerFormset(postIfPost(request, 'lenker'), prefix='lenker', 
        queryset=Lenke.objects.filter(kor__tilganger__in=request.user.medlem.tilganger.filter(navn='lenke')))

    disableFormMedlem(request.user.medlem, lenkerFormset)

    if request.method == 'POST':
        if lenkerFormset.is_valid():
            logAuthorAndSave(lenkerFormset, request.user.medlem)
            return redirect(request.get_full_path())

    return render(request, 'mytxs/lenker.html', {
        'formsets': [lenkerFormset],
        'heading': 'Lenker',
        'qrCodeLinkPrefix': consts.qrCodeLinkPrefix
    })


def lenkeRedirect(request, kor, lenkeNavn):
    if lenke := Lenke.objects.filter(kor__kortTittel=kor, navn=lenkeNavn, redirect=True).first():
        return redirect(lenke.lenke)
    messages.error(request, 'Lenke ikke funnet')
    return redirect('login')


@harTilgang(querysetModel=Verv)
def vervListe(request):
    vervFilterForm = NavnKorFilterForm(request.GET)

    request.queryset = vervFilterForm.applyFilter(request.queryset)

    NyttVervForm = modelform_factory(Verv, fields=['navn', 'kor'])

    nyttVervForm = NyttVervForm(request.POST or None, prefix='nyttVerv')
    
    disableFormMedlem(request.user.medlem, nyttVervForm)

    if request.method == 'POST':
        if nyttVervForm.is_valid():
            logAuthorAndSave(nyttVervForm, request.user.medlem)
            messages.info(request, f'{nyttVervForm.instance} opprettet!')
            return redirect(nyttVervForm.instance)
    
    addPaginatorPage(request)
    
    return render(request, 'mytxs/instanceListe.html', {
        'filterForm': vervFilterForm,
        'newForm': nyttVervForm,
        'heading': 'Verv',
    })


@harTilgang(instanceModel=Verv, lookupToArgNames={'kor__kortTittel': 'kor', 'navn': 'vervNavn'})
def verv(request, kor, vervNavn):
    VervForm = modelform_factory(Verv, exclude=['kor', 'bruktIKode'])
    VervInnehavelseFormset = inlineformset_factory(Verv, VervInnehavelse, formset=getPaginatedInlineFormSet(request), **inlineFormsetArgs)

    VervForm = addDeleteCheckbox(VervForm)

    VervForm = addReverseM2M(VervForm, 'tilganger')

    vervForm = VervForm(postIfPost(request, 'vervForm'), instance=request.instance, prefix='vervForm')
    vervInnehavelseFormset = VervInnehavelseFormset(postIfPost(request, 'vervInnehavelse'), instance=request.instance, prefix='vervInnehavelse')

    if disableFormMedlem(request.user.medlem, vervForm):
        disableBrukt(vervForm)
    
    disableFormMedlem(request.user.medlem, vervInnehavelseFormset)

    if res := lazyDropdown(request, vervInnehavelseFormset, 'medlem'):
        return res

    if request.method == 'POST':
        if vervForm.is_valid():
            logAuthorAndSave(vervForm, request.user.medlem)
            if vervForm.cleaned_data['DELETE']:
                messages.info(request, f'{vervForm.instance} slettet')
                return redirect('vervListe')
        if vervInnehavelseFormset.is_valid():
            logAuthorAndSave(vervInnehavelseFormset, request.user.medlem)
        
        if vervForm.is_valid() and vervInnehavelseFormset.is_valid():
            return redirectToInstance(request)
    
    return render(request, 'mytxs/instance.html', {
        'forms': [vervForm],
        'formsets': [vervInnehavelseFormset],
    })


@harTilgang(querysetModel=Dekorasjon)
def dekorasjonListe(request):
    dekorasjonFilterForm = NavnKorFilterForm(request.GET)

    request.queryset = dekorasjonFilterForm.applyFilter(request.queryset)

    NyDekorasjonForm = modelform_factory(Dekorasjon, fields=['navn', 'kor'])

    nyDekorasjonForm = NyDekorasjonForm(request.POST or None, prefix='nyDekorasjon')
    
    disableFormMedlem(request.user.medlem, nyDekorasjonForm)

    if request.method == 'POST':
        if nyDekorasjonForm.is_valid():
            logAuthorAndSave(nyDekorasjonForm, request.user.medlem)
            messages.info(request, f'{nyDekorasjonForm.instance} opprettet!')
            return redirect(nyDekorasjonForm.instance)

    addPaginatorPage(request)
    
    return render(request, 'mytxs/instanceListe.html', {
        'filterForm': dekorasjonFilterForm,
        'newForm': nyDekorasjonForm,
        'heading': 'Dekorasjoner'
    })


@harTilgang(instanceModel=Dekorasjon, lookupToArgNames={'kor__kortTittel': 'kor', 'navn': 'dekorasjonNavn'})
def dekorasjon(request, kor, dekorasjonNavn):
    DekorasjonForm = modelform_factory(Dekorasjon, exclude=['kor'])
    DekorasjonInnehavelseFormset = inlineformset_factory(Dekorasjon, DekorasjonInnehavelse, formset=getPaginatedInlineFormSet(request), **inlineFormsetArgs)

    DekorasjonForm = addDeleteCheckbox(DekorasjonForm)

    dekorasjonForm = DekorasjonForm(postIfPost(request, 'dekorasjonForm'), instance=request.instance, prefix='dekorasjonForm')
    dekorasjonInnehavelseFormset = DekorasjonInnehavelseFormset(postIfPost(request, 'dekorasjonInnehavelse'), instance=request.instance, prefix='dekorasjonInnehavelse')

    disableFormMedlem(request.user.medlem, dekorasjonForm)
    disableFormMedlem(request.user.medlem, dekorasjonInnehavelseFormset)

    if res := lazyDropdown(request, dekorasjonInnehavelseFormset, 'medlem'):
        return res

    if request.method == 'POST':
        if dekorasjonForm.is_valid():
            logAuthorAndSave(dekorasjonForm, request.user.medlem)
            if dekorasjonForm.cleaned_data['DELETE']:
                messages.info(request, f'{dekorasjonForm.instance} slettet')
                return redirect('dekorasjonListe')
        if dekorasjonInnehavelseFormset.is_valid():
            logAuthorAndSave(dekorasjonInnehavelseFormset, request.user.medlem)

        if dekorasjonForm.is_valid() and dekorasjonInnehavelseFormset.is_valid():
            return redirectToInstance(request)

    return render(request, 'mytxs/instance.html', {
        'forms': [dekorasjonForm],
        'formsets': [dekorasjonInnehavelseFormset]
    })


@harTilgang(querysetModel=Tilgang)
def tilgangListe(request):
    NyTilgangForm = modelform_factory(Tilgang, fields=['navn', 'kor'])

    nyTilgangForm = NyTilgangForm(request.POST or None, prefix='nyTilgang')
    
    disableFormMedlem(request.user.medlem, nyTilgangForm)

    if request.method == 'POST':
        if nyTilgangForm.is_valid():
            logAuthorAndSave(nyTilgangForm, request.user.medlem)
            messages.info(request, f'{nyTilgangForm.instance} opprettet!')
            return redirect(nyTilgangForm.instance)

    addPaginatorPage(request)
    
    return render(request, 'mytxs/instanceListe.html', {
        'newForm': nyTilgangForm,
        'heading': 'Tilganger'
    })


@harTilgang(instanceModel=Tilgang, lookupToArgNames={'kor__kortTittel': 'kor', 'navn': 'tilgangNavn'})
def tilgang(request, kor, tilgangNavn):
    TilgangForm = modelform_factory(Tilgang, exclude=['kor', 'bruktIKode'])

    TilgangForm = addDeleteCheckbox(TilgangForm)

    tilgangForm = TilgangForm(request.POST or None, instance=request.instance)

    if disableFormMedlem(request.user.medlem, tilgangForm):
        disableBrukt(tilgangForm)

    if request.method == 'POST':
        if tilgangForm.is_valid():
            logAuthorAndSave(tilgangForm, request.user.medlem)
            if tilgangForm.cleaned_data['DELETE']:
                messages.info(request, f'{tilgangForm.instance} slettet')
                return redirect('tilgangListe')
            return redirectToInstance(request)
    
    return render(request, 'mytxs/instance.html', {
        'forms': [tilgangForm],
    })


@harTilgang(querysetModel=Turne)
def turneListe(request):
    turneFilterForm = TurneFilterForm(request.GET)

    request.queryset = turneFilterForm.applyFilter(request.queryset)

    NyTurneForm = modelform_factory(Turne, fields=['navn', 'kor', 'start'])

    nyTurneForm = NyTurneForm(request.POST or None, prefix='nyTurne')
    
    disableFormMedlem(request.user.medlem, nyTurneForm)

    if request.method == 'POST':
        if nyTurneForm.is_valid():
            logAuthorAndSave(nyTurneForm, request.user.medlem)
            messages.info(request, f'{nyTurneForm.instance} opprettet!')
            return redirect(nyTurneForm.instance)

    addPaginatorPage(request)
    
    return render(request, 'mytxs/instanceListe.html', {
        'filterForm': turneFilterForm,
        'newForm': nyTurneForm,
        'heading': 'Turneer'
    })


@harTilgang(instanceModel=Turne, lookupToArgNames={'kor__kortTittel': 'kor', 'start__year': 'år', 'navn': 'turneNavn'})
def turne(request, kor, år, turneNavn):
    TurneForm = modelform_factory(Turne, exclude=['kor'])

    TurneForm = addDeleteCheckbox(TurneForm)

    turneForm = TurneForm(request.POST or None, instance=request.instance)

    disableFormMedlem(request.user.medlem, turneForm)

    if request.method == 'POST':
        if turneForm.is_valid():
            logAuthorAndSave(turneForm, request.user.medlem)
            if turneForm.cleaned_data['DELETE']:
                messages.info(request, f'{turneForm.instance} slettet')
                return redirect('turneListe')
            return redirectToInstance(request)

    return render(request, 'mytxs/instance.html', {
        'forms': [turneForm],
    })


@harTilgang(querysetModel=Logg)
def loggListe(request):
    loggFilterForm = LoggFilterForm(request.GET)

    request.queryset = loggFilterForm.applyFilter(request.queryset)

    addPaginatorPage(request)
    
    return render(request, 'mytxs/instanceListe.html', {
        'filterForm': loggFilterForm,
        'heading': 'Logger'
    })


@login_required()
def loggRedirect(request, modelName, instancePK):
    return redirect(Logg.objects.getLoggForModelPK(modelName, instancePK))


@harTilgang(instanceModel=Logg)
def logg(request, loggPK):
    return render(request, 'mytxs/logg.html')
