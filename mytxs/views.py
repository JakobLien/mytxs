import datetime
from urllib.parse import unquote

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
from mytxs.models import Dekorasjon, DekorasjonInnehavelse, Hendelse, Kor, Lenke, Logg, Medlem, Tilgang, Turne, Verv, VervInnehavelse, Oppmøte
from mytxs.forms import LoggFilterForm, MedlemFilterForm, NavnKorFilterForm, TurneFilterForm
from mytxs.utils.formAccess import disableBrukt, disableFields, disableForm, disableFormMedlem
from mytxs.utils.formAddField import addDeleteCheckbox, addReverseM2M
from mytxs.utils.lazyDropdown import lazyDropdown
from mytxs.utils.formUtils import filesIfPost, postIfPost, inlineFormsetArgs
from mytxs.utils.hashUtils import testHash, getHash
from mytxs.utils.logAuthorUtils import logAuthorAndSave, logAuthorInstance
from mytxs.utils.modelUtils import randomDistinct, vervInnehavelseAktiv, stemmegruppeVerv
from mytxs.utils.pagination import getPaginatedInlineFormSet, addPaginatorPage
from mytxs.utils.utils import downloadFile, generateVCard

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


def overfør(request, jwt):
    medlem = transferByJWT(jwt)

    messages.info(request, 'Data overført!')
    
    if not medlem.user:
        return redirect(reverse('registrer', args=[medlem.pk]) + '?hash=' + getHash(reverse('registrer', args=[medlem.pk])))
    else:
        return redirect('login')


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
    if (storkor := request.user.medlem.storkor) and storkor.kortTittel == 'TKS':
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
                stemmegruppeVerv('vervInnehavelse__verv'),
                vervInnehavelseAktiv(),
                vervInnehavelse__verv__kor=kor
            )
            if kor.kortTittel == 'KK':
                # Grupper KK på SATB
                for stemmegruppe in 'SATB':
                    grupperinger[stemmegruppe] = request.queryset.filter(
                        vervInnehavelse__verv__kor=kor, # Denne linjen ser dumt ut, men det må til
                        vervInnehavelse__verv__navn__endswith=stemmegruppe,
                    ).prefetchVervDekorasjonKor()
            else:
                # Grupper øverige kor på 1S, 2T osv
                for stemmegruppe in Verv.objects.filter(navn__in=consts.hovedStemmegrupper, kor=kor):
                    grupperinger[stemmegruppe.navn] = request.queryset.filter(
                        vervInnehavelse__verv__kor=kor, # Denne linjen ser dumt ut, men det må til
                        vervInnehavelse__verv__navn__endswith=stemmegruppe.navn,
                    ).prefetchVervDekorasjonKor()
    
    elif gruppe == 'søk':
        request.queryset = Medlem.objects.distinct().filter(
            vervInnehavelseAktiv(),
            stemmegruppeVerv('vervInnehavelse__verv')
        )

        medlemFilterForm = MedlemFilterForm(request.GET)

        request.queryset = medlemFilterForm.applyFilter(request.queryset)

        request.queryset = request.queryset.prefetchVervDekorasjonKor()

        return render(request, 'mytxs/sjekkheftetSøk.html', {
            'grupperinger': {'': request.queryset}, 
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

        request.queryset = request.queryset\
            .order_by(Cast((F('fødselsdato__month') * 31 + F('fødselsdato__day') - today + 403), output_field=IntegerField()) % 403)\
            .prefetchVervDekorasjonKor()

        grupperinger = {'':
            request.queryset
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
        content = generateVCard(request.queryset.exclude(tlf=''))
        return downloadFile(f'{gruppe}.vcf', content)
    
    return render(request, 'mytxs/sjekkheftet.html', {
        'grupperinger': grupperinger, 
        'grupper': grupper,
        'gruppe': gruppe,
        'heading': 'Sjekkheftet'
    })


@login_required()
@user_passes_test(lambda user : 'medlemListe' in user.medlem.navBarTilgang, redirect_field_name=None)
def medlemListe(request):
    request.queryset = request.user.medlem.sideTilgangQueryset(Medlem).distinct()

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
            disableForm(nyttMedlemForm)

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


@login_required()
def medlem(request, medlemPK):
    request.instance = Medlem.objects.filter(pk=medlemPK).first()

    if not request.instance:
        messages.error(request, 'Medlem ikke funnet')
        return redirect('medlemListe')

    if not request.user.medlem.harSideTilgang(request.instance):
        messages.error(request, f'Du har ikke tilgang til dette medlemmet')
        return redirect('medlemListe')
    
    if not request.user.medlem.redigerTilgangQueryset(Medlem).contains(request.instance):
        # Om du ikke har redigeringstilgang på medlemmet, skjul dataen demmers
        MedlemsDataForm = modelform_factory(Medlem, fields=['fornavn', 'mellomnavn', 'etternavn'])
    else:
        # Om du ikke har medlemsdata tilgangen, ikke vis død feltet
        if not request.user.medlem.tilganger.filter(navn='medlemsdata').exists():
            MedlemsDataForm = modelform_factory(Medlem, exclude=['user', 'gammeltMedlemsnummer', 'død'])
        else:
            MedlemsDataForm = modelform_factory(Medlem, exclude=['user', 'gammeltMedlemsnummer'])
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
        if 'notis' in medlemsDataForm.fields and not request.user.medlem.tilganger.filter(navn='medlemsdata').exists():
            disableFields(medlemsDataForm, 'notis')
    
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
            return redirect(request.instance)

    if not request.instance.user:
        request.registreringLink = request.get_host() + reverse('registrer', args=[request.instance.pk]) + '?hash=' + \
            getHash(reverse('registrer', args=[request.instance.pk]))

    return render(request, 'mytxs/medlem.html', {
        'forms': [medlemsDataForm], 
        'formsets': [vervInnehavelseFormset, dekorasjonInnehavelseFormset],
    })


# Ikke login_required her for å slippe gjennom kalender-apper som spør om iCal fila
def semesterplan(request, kor):
    # Håndter ical dersom det var det
    if request.GET.get('iCal'):
        content = Hendelse.objects.filter(kor__kortTittel=kor).generateICal()
        return downloadFile(f'{kor}.ics', content, content_type='text/calendar')
    # Manuel implementasjon av @login_required for å slippe gjennom iCal requests
    elif not request.user.is_authenticated:
        return redirect('login')

    if not request.user.medlem.aktiveKor.filter(kortTittel=kor).exists():
        messages.error(request, f'Du har ikke tilgang til andre kors kalender')
        return redirect(request.user.medlem)

    if request.GET.get('gammelt'):
        request.queryset = Hendelse.objects.filter(kor__kortTittel=kor)
    else:
        request.queryset = Hendelse.objects.filter(kor__kortTittel=kor, startDate__gte=datetime.datetime.today())
    
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
    
    if not testHash(request):
        messages.error(request, 'Feil eller manglende hash')
        return redirect('semesterplan', kor=hendelse.kor.kortTittel)
    
    request.instance = Oppmøte.objects.filter(medlem=request.user.medlem, hendelse=hendelse).first()
    
    if not request.instance:
        if not hendelse.getMedlemmer().contains(request.user.medlem):
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
    
    logAuthorInstance(request.instance, request.user.medlem)

    messages.info(request, f'Fravær ført med {request.instance.fravær} minutter forsentkomming!')
    
    return redirect('semesterplan', kor=hendelse.kor.kortTittel)


@login_required()
@user_passes_test(lambda user : 'hendelseListe' in user.medlem.navBarTilgang, redirect_field_name=None)
def hendelseListe(request):
    request.queryset = request.user.medlem.sideTilgangQueryset(Hendelse).distinct()

    NyHendelseForm = modelform_factory(Hendelse, fields=['navn', 'kor', 'kategori', 'startDate'])

    nyHendelseForm = NyHendelseForm(request.POST or None, prefix='nyttEvent')
    
    disableFormMedlem(request.user.medlem, nyHendelseForm)

    if request.method == 'POST':
        if nyHendelseForm.is_valid():
            logAuthorAndSave(nyHendelseForm, request.user.medlem)
            messages.info(request, f'{nyHendelseForm.instance} opprettet!')
            return redirect(nyHendelseForm.instance)

    addPaginatorPage(request)
    
    return render(request, 'mytxs/instanceListe.html', {
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
    OppmøteFormset = inlineformset_factory(Hendelse, Oppmøte, formset=getPaginatedInlineFormSet(request), exclude=[], extra=0, can_delete=False)

    HendelseForm = addDeleteCheckbox(HendelseForm)

    hendelseForm = HendelseForm(postIfPost(request, 'hendelse'), instance=request.instance, prefix='hendelse')
    oppmøteFormset = OppmøteFormset(postIfPost(request, 'oppmøte'), instance=request.instance, prefix='oppmøte')

    disableFormMedlem(request.user.medlem, hendelseForm)

    if disableFormMedlem(request.user.medlem, oppmøteFormset): 
        disableFields(oppmøteFormset, 'medlem')
        if not request.instance.varighet:
            disableFields(oppmøteFormset, 'fravær')

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

    if request.instance.startTime != None and abs(datetime.datetime.now() - request.instance.start).total_seconds() / 60 <= 30:
        request.egenFøringLink = f'https://zxing.org/w/chart?cht=qr&chs=350x350&chld=L&choe=UTF-8&chl=http://' + \
            request.get_host() + unquote(reverse('egenFøring', args=[request.instance.pk])) + '?hash=' + \
            getHash(reverse('egenFøring', args=[request.instance.pk]))

    return render(request, 'mytxs/hendelse.html', {
        'forms': [hendelseForm],
        'formsets': [oppmøteFormset],
    })


@login_required()
def lenker(request):
    request.queryset = Lenke.objects.distinct().filter(
        Q(kor__in=request.user.medlem.aktiveKor) | # Lenker fra kor man er i
        Q(kor__tilganger__in=request.user.medlem.tilganger.filter(navn='lenke')) # Lenker man kan endre på
    )

    # Om man er aktiv i minst et kor, hiv på Sangern sine lenker
    if request.user.medlem.aktiveKor.exists(): 
        request.queryset |= Lenke.objects.distinct().filter(kor__kortTittel='Sangern')

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
            return redirect('lenker')

    return render(request, 'mytxs/lenker.html', {
        'formsets': [lenkerFormset],
        'heading': 'Lenker',
    })


@login_required()
@user_passes_test(lambda user : 'vervListe' in user.medlem.navBarTilgang, redirect_field_name=None)
def vervListe(request):
    request.queryset = request.user.medlem.sideTilgangQueryset(Verv).distinct()

    vervFilterForm = NavnKorFilterForm(request.GET)

    request.queryset = vervFilterForm.applyFilter(request.queryset)

    # optionForm = OptionForm(request.GET, fields=['alleAlternativ'])

    # if not optionForm.is_valid():
    #     raise Exception('optionForm var ugyldig, ouf')

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
            return redirect(request.instance)
    
    return render(request, 'mytxs/instance.html', {
        'forms': [vervForm],
        'formsets': [vervInnehavelseFormset],
    })


@login_required()
@user_passes_test(lambda user : 'dekorasjonListe' in user.medlem.navBarTilgang, redirect_field_name=None)
def dekorasjonListe(request):
    request.queryset = request.user.medlem.sideTilgangQueryset(Dekorasjon).distinct()

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
            return redirect(request.instance)

    return render(request, 'mytxs/instance.html', {
        'forms': [dekorasjonForm],
        'formsets': [dekorasjonInnehavelseFormset]
    })


@login_required()
@user_passes_test(lambda user : 'tilgangListe' in user.medlem.navBarTilgang, redirect_field_name=None)
def tilgangListe(request):
    request.queryset = request.user.medlem.sideTilgangQueryset(Tilgang).distinct()

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
            return redirect(request.instance)
    
    return render(request, 'mytxs/instance.html', {
        'forms': [tilgangForm],
        # 'optionForm': optionForm
    })


@login_required()
@user_passes_test(lambda user : 'turneListe' in user.medlem.navBarTilgang, redirect_field_name=None)
def turneListe(request):
    request.queryset = request.user.medlem.sideTilgangQueryset(Turne).distinct()

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


@login_required()
def turne(request, kor, år, turneNavn):
    request.instance = Turne.objects.filter(kor__kortTittel=kor, start__year=år, navn=turneNavn).first()

    if not request.instance:
        messages.error(request, 'Turne ikke funnet')
        return redirect('turneListe')

    if not request.user.medlem.harSideTilgang(request.instance):
        messages.error(request, f'Du har ikke tilgang til denne turneen')
        return redirect('turneListe')
    
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
            return redirect(request.instance)

    return render(request, 'mytxs/instance.html', {
        'forms': [turneForm],
        # 'optionForm': optionForm
    })


@login_required()
@user_passes_test(lambda user : 'loggListe' in user.medlem.navBarTilgang, redirect_field_name=None)
def loggListe(request):
    request.queryset = request.user.medlem.sideTilgangQueryset(Logg).distinct()

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


@login_required()
def logg(request, loggPK):
    request.instance = Logg.objects.filter(pk=loggPK).first()

    if not request.user.medlem.harSideTilgang(request.instance):
        messages.error(request, f'Du har ikke tilgang til denne loggen')
        return redirect('loggListe')

    return render(request, 'mytxs/logg.html')
