import datetime
import json
import csv
import os

from django import forms
from django.contrib import messages
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm, SetPasswordForm
from django.contrib.auth.models import User as AuthUser
from django.core import mail
from django.db.models import Q, F, IntegerField, Prefetch, Case, When
from django.db.models.functions import Cast
from django.forms import inlineformset_factory, modelform_factory, modelformset_factory
from django.http import FileResponse, HttpResponse, HttpResponseForbidden, HttpResponseNotFound
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache

from mytxs import consts
from mytxs.fields import intToBitList
from mytxs.forms import HendelseFilterForm, LoggFilterForm, MedlemFilterForm, NavnKorFilterForm, ShareCalendarForm, TurneFilterForm, VervFilterForm, OppmøteFilterForm
from mytxs.management.commands.transfer import transferByJWT
from mytxs.models import Dekorasjon, DekorasjonInnehavelse, Hendelse, Kor, Lenke, Logg, Medlem, MedlemQuerySet, Tilgang, Turne, Verv, VervInnehavelse, Oppmøte
from mytxs.utils.formAccess import addHelpText, disableBrukt, disableFields, disableFormMedlem, removeFields
from mytxs.utils.formAddField import addDeleteCheckbox, addDeleteUserCheckbox, addHendelseMedlemmer, addReverseM2M
from mytxs.utils.googleCalendar import getOrCreateAndShareCalendar
from mytxs.utils.lazyDropdown import lazyDropdown
from mytxs.utils.formUtils import filesIfPost, postIfPost, dekorasjonInlineFormsetArgs, vervInlineFormsetArgs
from mytxs.utils.hashUtils import addHash, testHash
from mytxs.utils.modelUtils import inneværendeSemester, korLookup, qBool, randomDistinct, stemmegruppeOrdering, vervInnehavelseAktiv, stemmegruppeVerv, annotateInstance
from mytxs.utils.pagination import getPaginatedInlineFormSet, addPaginatorPage
from mytxs.utils.downloadUtils import downloadFile, downloadICal, downloadVCard
from mytxs.utils.utils import getHalvårStart
from mytxs.utils.viewUtils import HttpResponseUnauthorized, harFilTilgang, harTilgang, redirectToInstance

# Create your views here.

def serve(request, path):
    if not request.user.is_authenticated:
        return HttpResponseUnauthorized()
    
    if not harFilTilgang(request.user.medlem, path):
        return HttpResponseForbidden()

    try:
        return FileResponse(open('uploads/'+path, 'rb'))
    except FileNotFoundError:
        return HttpResponseNotFound()


@never_cache # For å fiks csrf feil med QR kode scanning. 
def login(request):
    if request.user.is_authenticated:
        return render(request, 'mytxs/base.html')

    loginForm = AuthenticationForm(data=request.POST)

    if request.method == 'POST':
        if loginForm.is_valid():
            user = loginForm.user_cache
            if user is not None:
                auth_login(request, user)
                messages.info(request, 'Login successful')
                user.medlem.innlogginger += 1
                user.medlem.save()
                if request.GET.get('next'):
                    return redirect(request.GET.get('next'))
                if request.user.medlem.storkorNavn():
                    return redirect('semesterplan', request.user.medlem.storkorNavn())
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
        raise HttpResponseNotFound('No Medlem matches the given query.')

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

    medlem.overførtData = True
    medlem.save()

    messages.info(request, 'Data overført!')
    
    if not medlem.user:
        return redirect(addHash(reverse('registrer', args=[medlem.pk])))
    else:
        return redirect('login')


@login_required
def endreLogin(request):
    EndreBrukernavnForm = modelform_factory(AuthUser, fields=['username'])
    endreBrukernavnForm = EndreBrukernavnForm(postIfPost(request, 'brukernavn'), instance=request.user, prefix='brukernavn')

    endrePassordForm = SetPasswordForm(data=postIfPost(request, 'passord'), user=request.user, prefix='passord')

    if request.method == 'POST':
        if endreBrukernavnForm.is_valid():
            endreBrukernavnForm.save()
            messages.info(request, 'Brukernavn endret!')
        if endrePassordForm.is_valid():
            endrePassordForm.save()
            messages.info(request, 'Passord endret!')
        if endreBrukernavnForm.is_valid() or endrePassordForm.is_valid():
            return redirect(request.get_full_path())

    return render(request, 'mytxs/endreLogin.html', {
        'endreBrukernavnForm': endreBrukernavnForm,
        'endrePassordForm': endrePassordForm,
        'heading': 'Endre brukernavn/passord'
    })


@harTilgang
def sjekkheftet(request, side, underside=None):
    if side == 'søk':
        request.queryset = Medlem.objects.distinct().annotateKarantenekor(storkor=True).filter(
            vervInnehavelseAktiv(),
            stemmegruppeVerv('vervInnehavelser__verv')
        )

        medlemFilterForm = MedlemFilterForm(request.GET)

        request.queryset = medlemFilterForm.applyFilter(request.queryset)\
            .order_by(*Medlem._meta.ordering).annotatePublic().sjekkheftePrefetch(kor=None)

        if request.GET.get('vcard'):
            return downloadVCard(request.queryset)

        return render(request, 'mytxs/sjekkheftetSøk.html', {
            'grupperinger': {'': request.queryset}, 
            'heading': 'Sjekkheftet',
            'filterForm': medlemFilterForm
        })
    
    if side == 'kart':
        request.medlemMapData = json.dumps([{
            'navn': medlem.navn,
            'boCord': medlem.boAdresseCord() if medlem.public__boAdresse else None,
            'foreldreCord': medlem.foreldreAdresseCord() if medlem.public__foreldreAdresse else None,
            'storkorNavn': medlem.storkorNavn(),
            'pk': medlem.pk
        } for medlem in Medlem.objects.distinct().filter(
            vervInnehavelseAktiv(),
            stemmegruppeVerv('vervInnehavelser__verv')
        ).annotatePublic().exclude(public__boAdresse__isnull=True, public__foreldreAdresse__isnull=True)])

        return render(request, 'mytxs/sjekkhefteKart.html')

    if side == 'sjekkhefTest':
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
    
    # Gruperinger er visuelle grupperinger i sjekkheftet på samme side, klassisk stemmegrupper. 
    grupperinger = {}
    if kor := Kor.objects.filter(navn=side).first():
        request.queryset = Medlem.objects.distinct().order_by(*Medlem._meta.ordering).annotateKarantenekor(
            kor=kor if kor.navn != consts.Kor.Sangern else None
        )

        if tilgang := Tilgang.objects.filter(sjekkheftetSynlig=True, navn=underside, kor=kor).first():
            # Om det e en tilgangsdefinert undergruppe vi ser på, f.eks. styret
            request.queryset = request.queryset.filter(
                vervInnehavelseAktiv(),
                vervInnehavelser__verv__kor=kor,
                vervInnehavelser__verv__tilganger=tilgang
            ).annotatePublic(
                overrideVisible=request.user.medlem.tilganger.filter(navn=consts.Tilgang.sjekkhefteSynlig, kor=kor).exists()
            ).sjekkheftePrefetch(kor=kor)

            grupperinger = {'': request.queryset}
        else:
            # Om det e heile koret
            request.queryset = request.queryset.filter(
                stemmegruppeVerv('vervInnehavelser__verv', includeUkjentStemmegruppe=False, includeDirr=True),
                vervInnehavelseAktiv(),
                vervInnehavelser__verv__kor=kor
            ).annotatePublic(
                overrideVisible=request.user.medlem.tilganger.filter(navn=consts.Tilgang.sjekkhefteSynlig, kor=kor).exists()
            ).annotateStemmegruppe(kor, includeDirr=True)

            if kor.navn not in consts.bareSmåkorNavn:
                request.queryset = request.queryset.annotateKor(annotationNavn='småkor', korAlternativ=consts.bareSmåkorNavn, aktiv=True)
            
            request.queryset = request.queryset.sjekkheftePrefetch(kor=kor)

            grupperinger = {key: [] for key in ['Dirigent'] + kor.stemmegrupper() }
            for medlem in request.queryset:
                grupperinger[medlem.stemmegruppe].append(medlem)

    elif side == 'jubileum':
        request.queryset = Medlem.objects.distinct().annotateKarantenekor(storkor=True).annotatePublic().filter(
            vervInnehavelseAktiv(), 
            stemmegruppeVerv('vervInnehavelser__verv'),
            public__fødselsdato__isnull=False
        )

        # Måten dette funke e at for å produser en index med tilsvarende sortering som
        # date_of_year (som ikke finnes i Django), gange vi måneden med 31, og legger på dagen.
        # Så må vi bare ta modulus 403 (den maksimale 12*31+31), også har vi det:)
        today = datetime.date.today()
        today = today.month*31 + today.day

        request.queryset = request.queryset\
            .order_by(Cast((F('fødselsdato__month') * 31 + F('fødselsdato__day') - today + 403), output_field=IntegerField()) % 403)\
            .sjekkheftePrefetch(kor=None)

        grupperinger = {'': request.queryset}

    elif side == 'fellesEmner':
        for emne in request.user.medlem.emnekoder.split():
            emne = emne.strip(',')
            medlem = Medlem.objects.filter(
                emnekoder__icontains=emne
            ).sjekkheftePrefetch(kor=None).annotatePublic()

            grupperinger[emne.upper()] = medlem

        return render(request, 'mytxs/fellesEmner.html', {
            'heading': 'Sjekkheftet', 'grupperinger': grupperinger
        })

    if request.GET.get('vcard'):
        return downloadVCard(request.queryset)

    return render(request, 'mytxs/sjekkheftet.html', {
        'grupperinger': grupperinger, 
        'heading': 'Sjekkheftet'
    })


@harTilgang(querysetModel=Medlem)
def medlemListe(request):
    medlemFilterForm = MedlemFilterForm(request.GET, request=request)

    request.queryset = medlemFilterForm.applyFilter(request.queryset)

    NyttMedlemForm = modelform_factory(Medlem, fields=['fornavn', 'mellomnavn', 'etternavn'])

    nyttMedlemForm = NyttMedlemForm(request.POST or None, prefix='nyttMedlem', initial={
        'fornavn': '', 'mellomnavn': '', 'etternavn': ''
    })

    if disableFormMedlem(request.user.medlem, nyttMedlemForm):
        # Krev at man må ha tversAvKor tilgangen for å opprett nye medlemma. 
        # Om ikkje vil man ikkje ha tilgang til det nye medlemmet, siden det er uten kormedlemskap
        if not request.user.medlem.tilganger.filter(navn=consts.Tilgang.tversAvKor).exists():
            disableFields(nyttMedlemForm)

    if request.method == 'POST':
        if nyttMedlemForm.is_valid():
            nyttMedlemForm.save()
            messages.info(request, f'{nyttMedlemForm.instance} opprettet!')
            return redirect(nyttMedlemForm.instance)
    
    addPaginatorPage(request)
    
    return render(request, 'mytxs/instanceListe.html', {
        'filterForm': medlemFilterForm,
        'newForm': nyttMedlemForm
    })


@harTilgang(instanceModel=Medlem, extendAccess=lambda req: Medlem.objects.filter(pk=req.user.medlem.pk))
def medlem(request, medlemPK):
    if request.GET.get('loggInnSom') and request.user.is_superuser:
        auth_login(request, request.instance.user)
        return redirect(request.path)
    
    if not request.user.medlem.redigerTilgangQueryset(Medlem).contains(request.instance) and request.user.medlem != request.instance:
        # Om du ikke har redigeringstilgang på medlemmet, skjul dataen demmers
        MedlemsDataForm = modelform_factory(Medlem, fields=['fornavn', 'mellomnavn', 'etternavn'])
    elif request.user.medlem.redigerTilgangQueryset(Medlem, includeExtended=False).contains(request.instance):
        # Om du har tilgang ikke fordi det e deg sjølv, også vis gammeltMedlemsnummer og død feltan
        MedlemsDataForm = addDeleteUserCheckbox(modelform_factory(Medlem, exclude=['user']))
    else:
        MedlemsDataForm = modelform_factory(Medlem, exclude=['user', 'gammeltMedlemsnummer', 'død'])
    VervInnehavelseFormset = inlineformset_factory(Medlem, VervInnehavelse, formset=getPaginatedInlineFormSet(request), **vervInlineFormsetArgs)
    DekorasjonInnehavelseFormset = inlineformset_factory(Medlem, DekorasjonInnehavelse, formset=getPaginatedInlineFormSet(request), **dekorasjonInlineFormsetArgs)

    MedlemsDataForm = addReverseM2M(MedlemsDataForm, 'turneer')

    medlemsDataForm = MedlemsDataForm(
        postIfPost(request, 'medlemdata'), 
        filesIfPost(request, 'medlemdata'), 
        instance=request.instance, 
        prefix='medlemdata'
    )
    vervInnehavelseFormset = VervInnehavelseFormset(
        postIfPost(request, 'vervInnehavelser'), 
        instance=request.instance, 
        prefix='vervInnehavelser'
    )
    dekorasjonInnehavelseFormset = DekorasjonInnehavelseFormset(
        postIfPost(request, 'dekorasjonInnehavelser'), 
        instance=request.instance, 
        prefix='dekorasjonInnehavelser'
    )

    if request.instance.storkorNavn() == 'TKS' or request.instance.aktiveKor.filter(navn=consts.Kor.TSS):
        removeFields(medlemsDataForm, 'ønskerVårbrev')

    if disableFormMedlem(request.user.medlem, medlemsDataForm):
        if 'gammeltMedlemsnummer' in medlemsDataForm.fields:
            disableFields(medlemsDataForm, 'gammeltMedlemsnummer')
        if 'notis' in medlemsDataForm.fields and not request.user.medlem.redigerTilgangQueryset(Medlem, includeExtended=False).contains(request.instance):
            disableFields(medlemsDataForm, 'notis')
    
    disableFormMedlem(request.user.medlem, vervInnehavelseFormset)

    disableFormMedlem(request.user.medlem, dekorasjonInnehavelseFormset)

    if res := lazyDropdown(request, vervInnehavelseFormset, 'verv'):
        return res
    if res := lazyDropdown(request, dekorasjonInnehavelseFormset, 'dekorasjon'):
        return res

    if request.method == 'POST':
        if medlemsDataForm.is_valid():
            medlemsDataForm.save()
        if vervInnehavelseFormset.is_valid():
            vervInnehavelseFormset.save()
        if dekorasjonInnehavelseFormset.is_valid():
            dekorasjonInnehavelseFormset.save()
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
    if not request.user.medlem.aktiveKor.filter(navn=kor).exists():
        messages.error(request, f'Du har ikke tilgang til andre kors kalender')
        return redirect(request.user.medlem)
    
    if request.GET.get('jobbvakter'):
        if hendelsePK := request.GET.get('toggle'):
            hendelse = Hendelse.objects.filter(pk=hendelsePK).first()
            if not hendelse:
                messages.error(request, f'Fant ikke hendelse med pk {hendelsePK}.')
                return redirect(request.path+'?jobbvakter=True')
            
            oppmeldt = Oppmøte.objects.filter(medlem=request.user.medlem, hendelse=hendelse).exists()
            if hendelse.undergruppeAntall and (not hendelse.undergruppeAntall <= hendelse.oppmøter.count() or oppmeldt):
                if oppmeldt:
                    Oppmøte.objects.filter(hendelse=hendelse, medlem=request.user.medlem).delete()
                else:
                    Oppmøte.objects.create(hendelse=hendelse, medlem=request.user.medlem, ankomst=hendelse.defaultAnkomst)
            else:
                messages.error(request, f'Du kan ikke meldes på/av hendelsen med pk {hendelsePK}.')

            return redirect(request.path+'?jobbvakter=True')

        request.queryset = Hendelse.objects.filter(
            kategori=Hendelse.UNDERGRUPPE,
            kor__navn__in=[consts.Kor.Sangern, kor] if kor in consts.bareStorkorNavn else [kor],
            startDate__gte=getHalvårStart(),
            navn__regex=r'\[(.* )*#[0-9]+( .*)*\]' # Regex for firkantparentes med et hashtag tall ledd separert med mellomrom
        ).prefetch_related('oppmøter__medlem')

        for hendelse in request.queryset:
            # For å gjør det lettar i templaten, og for å gjør det raskt (uten fleir queries)
            hendelse.full = hendelse.undergruppeAntall <= hendelse.oppmøter.count()
            hendelse.påmeldt = any([o.medlem == request.user.medlem for o in hendelse.oppmøter.all()])

        return render(request, 'mytxs/jobbvakter.html')

    shareCalendarForm = ShareCalendarForm(postIfPost(request, 'shareCalendar'), prefix='shareCalendar')

    if request.method == 'POST':
        if shareCalendarForm.is_valid():
            getOrCreateAndShareCalendar(kor, request.user.medlem, shareCalendarForm.cleaned_data['gmail'])
            return redirect(request.get_full_path())

    request.queryset = request.user.medlem.getHendelser(kor)

    if not request.GET.get('gammelt'):
        request.queryset = request.queryset.filter(startDate__gte=datetime.datetime.today())

    if request.GET.get('utenUndergruppe'):
        request.queryset = request.queryset.exclude(kategori=Hendelse.UNDERGRUPPE)

    request.iCalLink = 'http://' + request.get_host() + addHash(reverse('iCal', args=[kor, request.user.medlem.pk]))

    annotateInstance(request.user.medlem, MedlemQuerySet.annotateFravær, kor=kor)
    
    return render(request, 'mytxs/semesterplan.html', { 
        'medlem': request.user.medlem,
        'shareCalendarForm': shareCalendarForm
    })


def iCal(request, kor, medlemPK):
    medlem = Medlem.objects.filter(pk=medlemPK).first()

    if not medlem:
        messages.error(request, f'Dette medlemmet finnes ikke.')
        return redirect('login')
    
    if not testHash(request):
        messages.error(request, 'Feil eller manglende hash')
        return redirect('login')
    
    if not medlem.aktiveKor.filter(navn=kor).exists():
        messages.error(request, 'Du har ikke tilgang til dette korets kalender')
        return redirect('login')

    return downloadICal(medlem, kor)


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
            oppmøteForm.save()
            return redirectToInstance(request)

    return render(request, 'mytxs/instance.html', {
        'forms': [oppmøteForm],
        'formsets': []
    })


@login_required
def egenFøring(request, hendelsePK):
    hendelse = Hendelse.objects.filter(pk=hendelsePK, kategori=Hendelse.OBLIG).first()

    if not hendelse:
        messages.error(request, 'Hendelse ikke funnet')
        return redirect('semesterplan', kor=hendelse.kor.navn)
    
    if hendelse.varighet == None:
        messages.error(request, 'Kan ikke føre fravær på hendelser uten varighet')
        return redirect('semesterplan', kor=hendelse.kor.navn)
    
    if not testHash(request):
        messages.error(request, 'Feil eller manglende hash')
        return redirect('semesterplan', kor=hendelse.kor.navn)
    
    request.instance = Oppmøte.objects.filter(medlem=request.user.medlem, hendelse=hendelse).first()
    
    if not request.instance:
        messages.error(request, 'Du er ikke blant de som skal føres fravær på')
        return redirect('semesterplan', kor=hendelse.kor.navn)
    
    if abs(datetime.datetime.now() - hendelse.start).total_seconds() / 60 > 30 or datetime.datetime.now() > hendelse.slutt:
        messages.error(request, 'For sent eller tidlig å føre fravær selv')
        return redirect('semesterplan', kor=hendelse.kor.navn)

    if request.instance.fravær != None:
        messages.info(request, f'Oppmøte allerede ført med {request.instance.fravær} minutter forsentkomming!')
        return redirect('semesterplan', kor=hendelse.kor.navn)

    request.instance.fravær = int(max(
        (min(hendelse.slutt, datetime.datetime.now()) - hendelse.start).total_seconds() / 60, 
        0
    ))
    
    request.instance.save() # Ikke fjern meg!

    messages.info(request, f'Oppmøte ført med {request.instance.fravær} minutter forsentkomming!')
    
    return redirect('semesterplan', kor=hendelse.kor.navn)


@harTilgang
def fraværSide(request, side, underside=None):
    if side == 'søknader':
        oppmøteFilterForm = OppmøteFilterForm(request.GET, request=request)

        request.queryset = request.user.medlem.sideTilgangQueryset(Oppmøte).distinct()

        request.queryset = oppmøteFilterForm.applyFilter(request.queryset)

        addPaginatorPage(request)

        return render(request, 'mytxs/instanceListe.html', {
            'filterForm': oppmøteFilterForm
        })

    if side == 'oversikt' or side == 'statistikk':
        request.queryset = Medlem.objects.filter(
            vervInnehavelseAktiv(),
            stemmegruppeVerv('vervInnehavelser__verv', includeDirr=True),
            korLookup(underside, 'vervInnehavelser__verv__kor'),
        ).annotateFravær(
            kor=underside, 
            heleSemesteret=bool(request.GET.get('heleSemesteret'))
        ).annotatePermisjon(kor=underside).filter(permisjon=False)

    if side == 'oversikt':
        request.queryset = request.queryset.order_by(*Medlem._meta.ordering)
        return render(request, 'mytxs/fraværListe.html')
    
    if side == 'statistikk':
        medlemmer = request.queryset.annotateKarantenekor(kor=underside).annotateStemmegruppe(kor=underside)\
            .annotateKor(annotationNavn="aktivtSmåkorNavn", korAlternativ=consts.bareSmåkorNavn, aktiv=True)\
            .annotateKor(annotationNavn="småkorNavn", korAlternativ=consts.bareSmåkorNavn, aktiv=False)

        class FraværGruppe:
            def __init__(self, navn):
                self._navn = navn
                self.medlemmer = []

            @property
            def navn(self):
                return f'{self._navn} ({len(self.medlemmer)})'

            @property
            def gyldigFravær(self):
                return sum([m.gyldigFravær for m in self.medlemmer])/len(self.medlemmer)
            
            @property
            def ugyldigFravær(self):
                return sum([m.ugyldigFravær for m in self.medlemmer])/len(self.medlemmer)
        
            @property
            def umeldtFravær(self):
                return sum([m.umeldtFravær for m in self.medlemmer])/len(self.medlemmer)
        
            @property
            def hendelseVarighet(self):
                return sum([m.hendelseVarighet for m in self.medlemmer])/len(self.medlemmer)
        
        fraværGrupper = {}

        for stemmegruppe in Kor.objects.get(navn=underside).stemmegrupper():
            fraværGrupper[stemmegruppe] = FraværGruppe(stemmegruppe)

        for karantenekor in medlemmer.values_list('karantenekor', flat=True).order_by('karantenekor'):
            fraværGrupper[karantenekor] = FraværGruppe('K'+str(karantenekor-2000 if karantenekor >= 2000 else karantenekor))

        for småkorNavn in consts.småkorForStorkor.get(underside, []):
            fraværGrupper[småkorNavn] = FraværGruppe(småkorNavn)
            fraværGrupper['Eks ' + småkorNavn] = FraværGruppe('Eks ' + småkorNavn)

        for medlem in medlemmer:
            fraværGrupper[medlem.karantenekor].medlemmer.append(medlem)

            if medlem.stemmegruppe != None:
                fraværGrupper[medlem.stemmegruppe].medlemmer.append(medlem)
            
            if medlem.aktivtSmåkorNavn in fraværGrupper:
                fraværGrupper[medlem.aktivtSmåkorNavn].medlemmer.append(medlem)
            elif medlem.småkorNavn and 'Eks ' + medlem.småkorNavn in fraværGrupper:
                fraværGrupper['Eks ' + medlem.småkorNavn].medlemmer.append(medlem)
        
        request.queryset = list(filter(lambda fg: fg.medlemmer, fraværGrupper.values()))

        return render(request, 'mytxs/fraværListe.html')


@login_required
def fraværSemesterplan(request, kor, medlemPK):
    if not request.user.medlem.tilganger.filter(navn=consts.Tilgang.fravær, kor__navn=kor).exists():
        messages.error(request, f'Du har ikke tilgang til {request.path}')
        return redirect('login')
    
    medlem = Medlem.objects.get(pk=medlemPK)

    request.queryset = medlem.getHendelser(kor).filter(kor__navn=kor, kategori=Hendelse.OBLIG)

    if not request.GET.get('gammelt'):
        request.queryset = request.queryset.filter(startDate__gte=datetime.datetime.today())

    annotateInstance(medlem, MedlemQuerySet.annotateFravær, kor=kor)
    
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
            nyHendelseForm.save()
            messages.info(request, f'{nyHendelseForm.instance} opprettet!')
            return redirect(nyHendelseForm.instance)

    addPaginatorPage(request)
    
    return render(request, 'mytxs/instanceListe.html', {
        'filterForm': hendelseFilterForm,
        'newForm': nyHendelseForm,
    })


@harTilgang(instanceModel=Hendelse)
def hendelse(request, hendelsePK):
    if request.instance.kategori == Hendelse.OBLIG and request.GET.get('fraværModus'):
        request.queryset = MedlemQuerySet.annotateStemmegruppe(
            request.instance.oppmøter,
            kor=request.instance.kor,
            includeDirr=True,
            pkPath='medlem__pk'
        ).select_related('medlem').order_by(stemmegruppeOrdering(fieldName='stemmegruppe'), 'medlem')

        endreFraværForm = None
        if medlemPK := request.GET.get('førFraværFor') or request.GET.get('medlem'):
            oppmøte = request.queryset.filter(medlem__pk=medlemPK).first()

            if request.GET.get('førFraværFor'):
                if oppmøte.fravær == None:
                    oppmøte.fravær = int(max((min(request.instance.slutt, datetime.datetime.now()) - request.instance.start).total_seconds() / 60, 0))
                    oppmøte.save()
                request.GET = request.GET.copy()
                request.GET['medlem'] = request.GET['førFraværFor']
                del request.GET['førFraværFor']
                return redirectToInstance(request)

            EndreFraværForm = modelform_factory(Oppmøte, fields=['fravær'])

            endreFraværForm = EndreFraværForm(
                postIfPost(request, 'endreFravær'), 
                instance=oppmøte, 
                prefix='endreFravær'
            )

            if request.method == 'POST' and endreFraværForm.is_valid():
                endreFraværForm.save()
                return redirectToInstance(request)
        
        return render(request, 'mytxs/fraværModus.html', {
            'endreFraværForm': endreFraværForm
        })

    if request.GET.get('dupliser'):
        request.GET = request.GET.copy()
        del request.GET['dupliser']

        if Hendelse.objects.filter(
            kor=request.instance.kor,
            navn=request.instance.navn,
            startDate=request.instance.startDate + datetime.timedelta(weeks=1)
        ).exists():
            messages.error(request, 'Kan ikke duplisere hendelsen da det finnes en med samme navn og start dato')
            return redirectToInstance(request)

        # Dupliser hendelsen
        request.instance.pk = None
        request.instance._state.adding = True
        request.instance.startDate += datetime.timedelta(weeks=1)
        if request.instance.sluttDate:
            request.instance.sluttDate += datetime.timedelta(weeks=1)
        request.instance.save()

        return redirectToInstance(request)

    HendelseForm = modelform_factory(Hendelse, exclude=['kor'])

    if request.instance.kategori == Hendelse.UNDERGRUPPE:
        HendelseForm = addHendelseMedlemmer(HendelseForm)

    HendelseForm = addDeleteCheckbox(HendelseForm)

    hendelseForm = HendelseForm(postIfPost(request, 'hendelse'), instance=request.instance, prefix='hendelse')

    disableFormMedlem(request.user.medlem, hendelseForm)

    oppmøteFormset = None
    if request.instance.kategori != Hendelse.UNDERGRUPPE or request.instance.oppmøter.exclude( # Om vi har nån oppmøter med data på seg
        fravær__isnull=True, ankomst=request.instance.defaultAnkomst, melding=''
    ).exists():
        OppmøteFormset = inlineformset_factory(Hendelse, Oppmøte, exclude=[], extra=0, can_delete=True, formset=getPaginatedInlineFormSet(request))
        oppmøteFormset = OppmøteFormset(postIfPost(request, 'oppmøte'), instance=request.instance, prefix='oppmøte', \
            queryset=None if request.instance.kategori != Hendelse.UNDERGRUPPE else request.instance.oppmøter.exclude(
                fravær__isnull=True, ankomst=request.instance.defaultAnkomst, melding=''
            )
        )

        if disableFormMedlem(request.user.medlem, oppmøteFormset): 
            disableFields(oppmøteFormset, 'medlem')
            if not request.instance.varighet:
                disableFields(oppmøteFormset, 'fravær')

            addHelpText(oppmøteFormset, 'DELETE', helpText='Dette oppmøtet ble ikke slettet automatisk pga data, slett det gjerne manuelt.')
            for form in oppmøteFormset.forms:
                if form.instance.medlem in oppmøteFormset.instance.oppmøteMedlemmer:
                    removeFields(form, 'DELETE')
        else:
            removeFields(oppmøteFormset, 'DELETE')

    if request.method == 'POST':
        # Rekkefølgen her e viktig for at bruker skal kunne slette oppmøter nødvendig for å flytte hendelse på en submit:)
        if oppmøteFormset and oppmøteFormset.is_valid():
            oppmøteFormset.save()
        if hendelseForm.is_valid():
            hendelseForm.save()
            if hendelseForm.cleaned_data['DELETE']:
                messages.info(request, f'{hendelseForm.instance} slettet')
                return redirect('hendelse')
        
        if hendelseForm.is_valid() and (not oppmøteFormset or oppmøteFormset.is_valid()):
            return redirectToInstance(request)

    if request.instance.kategori == Hendelse.OBLIG and request.instance.sluttTime != None and abs(datetime.datetime.now() - request.instance.start).total_seconds() / 60 <= 30:
        request.egenFøringLink = consts.qrCodeLinkPrefix + 'http://' + request.get_host() + addHash(reverse('egenFøring', args=[request.instance.pk]))
    
    if request.user.medlem.tilganger.filter(navn=consts.Tilgang.eksport, kor=request.instance.kor).exists():
        request.eksportLenke = reverse('eksport', args=[request.instance.kor.navn]) + '?' + ''.join(map(lambda m: f'm={m}&', request.instance.oppmøter.filter(ankomst=Oppmøte.KOMMER).values_list('medlem', flat=True)))[:-1]

    return render(request, 'mytxs/hendelse.html', {
        'forms': [hendelseForm],
        'formsets': [oppmøteFormset] if oppmøteFormset else [],
    })


@harTilgang
def lenker(request):
    request.queryset = Lenke.objects.distinct().filter(
        Q(kor__in=request.user.medlem.aktiveKor) | Q(kor__navn=consts.Kor.Sangern), 
        synlig=True
    )

    # Om man ikke har tilgang til å redigere noen lenker, bare render her uten formsettet
    if not request.user.medlem.tilganger.filter(navn=consts.Tilgang.lenke).exists():
        return render(request, 'mytxs/lenker.html', {
            'heading': 'Lenker',
        })

    LenkerFormset = modelformset_factory(Lenke, exclude=[], can_delete=True, can_delete_extra=False, extra=1)

    lenkerFormset = LenkerFormset(postIfPost(request, 'lenker'), prefix='lenker', 
        queryset=Lenke.objects.filter(kor__tilganger__in=request.user.medlem.tilganger.filter(navn=consts.Tilgang.lenke)))

    disableFormMedlem(request.user.medlem, lenkerFormset)

    if request.method == 'POST':
        if lenkerFormset.is_valid():
            lenkerFormset.save()
            return redirect(request.get_full_path())

    return render(request, 'mytxs/lenker.html', {
        'formsets': [lenkerFormset],
        'heading': 'Lenker',
        'qrCodeLinkPrefix': consts.qrCodeLinkPrefix
    })


def lenkeRedirect(request, kor, lenkeNavn):
    if lenke := Lenke.objects.filter(kor__navn=kor, navn=lenkeNavn, redirect=True).first():
        return redirect(lenke.lenke)
    raise HttpResponseNotFound('Redirect not found.')


@harTilgang
def vrangstrupen(request):
    request.user.medlem.deviicer = DekorasjonInnehavelse.objects.filter(
        medlem=request.user.medlem,
        dekorasjon__navn__in=consts.vrangstrupeDekorasjoner,
        dekorasjon__kor__navn=consts.Kor.TSS,
        dekorasjon__bruktIKode=True
    )

    request.queryset = DekorasjonInnehavelse.objects.filter(
        dekorasjon__navn__in=consts.vrangstrupeDekorasjoner,
        dekorasjon__kor__navn=consts.Kor.TSS,
        dekorasjon__bruktIKode=True
    ).order_by(
        '-start__year',
        Case(*[When(dekorasjon__navn=consts.vrangstrupeDekorasjoner[i], then=2-i) for i in range(3)])
    ).prefetch_related('medlem', 'dekorasjon')
    return render(request, 'mytxs/vrangstrupen.html', {
        'heading': 'Vrangstrupens Deviicer',
    })


@harTilgang(querysetModel=Verv)
def vervListe(request):
    vervFilterForm = VervFilterForm(request.GET)

    request.queryset = vervFilterForm.applyFilter(request.queryset)

    NyttVervForm = modelform_factory(Verv, fields=['navn', 'kor'])

    nyttVervForm = NyttVervForm(request.POST or None, prefix='nyttVerv')
    
    disableFormMedlem(request.user.medlem, nyttVervForm)

    if request.method == 'POST':
        if nyttVervForm.is_valid():
            nyttVervForm.save()
            messages.info(request, f'{nyttVervForm.instance} opprettet!')
            return redirect(nyttVervForm.instance)
    
    addPaginatorPage(request)
    
    return render(request, 'mytxs/instanceListe.html', {
        'filterForm': vervFilterForm,
        'newForm': nyttVervForm,
    })


@harTilgang(instanceModel=Verv, lookupToArgNames={'kor__navn': 'kor', 'navn': 'vervNavn'})
def verv(request, kor, vervNavn):
    VervForm = modelform_factory(Verv, exclude=['kor'])
    VervInnehavelseFormset = inlineformset_factory(Verv, VervInnehavelse, formset=getPaginatedInlineFormSet(request), **vervInlineFormsetArgs)

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
            vervForm.save()
            if vervForm.cleaned_data['DELETE']:
                messages.info(request, f'{vervForm.instance} slettet')
                return redirect('verv')
        if vervInnehavelseFormset.is_valid():
            vervInnehavelseFormset.save()
        
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
            nyDekorasjonForm.save()
            messages.info(request, f'{nyDekorasjonForm.instance} opprettet!')
            return redirect(nyDekorasjonForm.instance)

    addPaginatorPage(request)
    
    return render(request, 'mytxs/instanceListe.html', {
        'filterForm': dekorasjonFilterForm,
        'newForm': nyDekorasjonForm,
    })


@harTilgang(instanceModel=Dekorasjon, lookupToArgNames={'kor__navn': 'kor', 'navn': 'dekorasjonNavn'})
def dekorasjon(request, kor, dekorasjonNavn):
    DekorasjonForm = modelform_factory(Dekorasjon, exclude=['kor'])
    DekorasjonInnehavelseFormset = inlineformset_factory(Dekorasjon, DekorasjonInnehavelse, formset=getPaginatedInlineFormSet(request), **dekorasjonInlineFormsetArgs)

    DekorasjonForm = addDeleteCheckbox(DekorasjonForm)

    dekorasjonForm = DekorasjonForm(postIfPost(request, 'dekorasjonForm'), filesIfPost(request, 'dekorasjonForm'), instance=request.instance, prefix='dekorasjonForm')
    dekorasjonInnehavelseFormset = DekorasjonInnehavelseFormset(postIfPost(request, 'dekorasjonInnehavelser'), instance=request.instance, prefix='dekorasjonInnehavelser')

    if disableFormMedlem(request.user.medlem, dekorasjonForm):
        disableBrukt(dekorasjonForm)
    disableFormMedlem(request.user.medlem, dekorasjonInnehavelseFormset)

    if res := lazyDropdown(request, dekorasjonInnehavelseFormset, 'medlem'):
        return res

    if request.method == 'POST':
        if dekorasjonForm.is_valid():
            dekorasjonForm.save()
            if dekorasjonForm.cleaned_data['DELETE']:
                messages.info(request, f'{dekorasjonForm.instance} slettet')
                return redirect('dekorasjon')
        if dekorasjonInnehavelseFormset.is_valid():
            dekorasjonInnehavelseFormset.save()

        if dekorasjonForm.is_valid() and dekorasjonInnehavelseFormset.is_valid():
            return redirectToInstance(request)

    return render(request, 'mytxs/instance.html', {
        'forms': [dekorasjonForm],
        'formsets': [dekorasjonInnehavelseFormset]
    })


@harTilgang(querysetModel=Tilgang)
def tilgangSide(request, side=None):
    if side == 'oversikt':
        tilgangVerv = Verv.objects.filter(
            qBool(request.GET.get('ikkeBruktIKode'), falseOption=Q(tilganger__bruktIKode=True)),
            tilganger__kor__tilganger__in=request.user.medlem.tilganger.filter(navn=consts.Tilgang.tilgang)
        ).distinct().prefetch_related(
            'kor',
            Prefetch('tilganger', queryset=Tilgang.objects.filter(
                qBool(request.GET.get('ikkeBruktIKode'), falseOption=Q(bruktIKode=True)),
            ).prefetch_related('kor')),
            Prefetch('vervInnehavelser', queryset=VervInnehavelse.objects.filter(
                vervInnehavelseAktiv('', utvidetStart=datetime.timedelta(days=60), utvidetSlutt=datetime.timedelta(days=30)),
            ).prefetch_related('medlem'))
        )

        return render(request, 'mytxs/tilgangOversikt.html', {
            'tilgangVerv': tilgangVerv,
        })
    
    NyTilgangForm = modelform_factory(Tilgang, fields=['navn', 'kor'])

    nyTilgangForm = NyTilgangForm(request.POST or None, prefix='nyTilgang')
    
    disableFormMedlem(request.user.medlem, nyTilgangForm)

    if request.method == 'POST':
        if nyTilgangForm.is_valid():
            nyTilgangForm.save()
            messages.info(request, f'{nyTilgangForm.instance} opprettet!')
            return redirect(nyTilgangForm.instance)

    addPaginatorPage(request)
    
    return render(request, 'mytxs/instanceListe.html', {
        'newForm': nyTilgangForm,
    })


@harTilgang(instanceModel=Tilgang, lookupToArgNames={'kor__navn': 'kor', 'navn': 'tilgangNavn'})
def tilgang(request, kor, tilgangNavn):
    TilgangForm = modelform_factory(Tilgang, exclude=['kor'])

    TilgangForm = addDeleteCheckbox(TilgangForm)

    tilgangForm = TilgangForm(request.POST or None, instance=request.instance)

    if disableFormMedlem(request.user.medlem, tilgangForm):
        disableBrukt(tilgangForm)

    if request.method == 'POST':
        if tilgangForm.is_valid():
            tilgangForm.save()
            if tilgangForm.cleaned_data['DELETE']:
                messages.info(request, f'{tilgangForm.instance} slettet')
                return redirect('tilgang')
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
            nyTurneForm.save()
            messages.info(request, f'{nyTurneForm.instance} opprettet!')
            return redirect(nyTurneForm.instance)

    addPaginatorPage(request)
    
    return render(request, 'mytxs/instanceListe.html', {
        'filterForm': turneFilterForm,
        'newForm': nyTurneForm,
    })


@harTilgang(instanceModel=Turne, lookupToArgNames={'kor__navn': 'kor', 'start__year': 'år', 'navn': 'turneNavn'})
def turne(request, kor, år, turneNavn):
    TurneForm = modelform_factory(Turne, exclude=['kor'])

    TurneForm = addDeleteCheckbox(TurneForm)

    turneForm = TurneForm(request.POST or None, instance=request.instance)

    disableFormMedlem(request.user.medlem, turneForm)

    if request.method == 'POST':
        if turneForm.is_valid():
            turneForm.save()
            if turneForm.cleaned_data['DELETE']:
                messages.info(request, f'{turneForm.instance} slettet')
                return redirect('turne')
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
    })


@login_required
def loggRedirect(request, modelName, instancePK):
    return redirect(Logg.objects.getLoggForModelPK(modelName, instancePK))


@harTilgang(instanceModel=Logg)
def logg(request, loggPK):
    return render(request, 'mytxs/logg.html')


@harTilgang
def eksport(request, kor):    
    supportedFields = ['id', 'stemmegruppe', 'gammeltMedlemsnummer', 'fødselsdato', 'epost', 'tlf', 'studieEllerJobb', 'boAdresse', 'foreldreAdresse', 'ønskerVårbrev', 'notis', 'overførtData', 'matpreferanse']

    class EksportForm(forms.Form):
        # Medlemmer og felt forkortet til m og f for å lage kortere urler
        m = forms.ModelMultipleChoiceField(required=False, label='Medlemmer', queryset=Medlem.objects.filter(vervInnehavelseAktiv(), stemmegruppeVerv('vervInnehavelser__verv', includeDirr=True), vervInnehavelser__verv__kor__navn=kor).distinct())
        f = forms.MultipleChoiceField(required=False, label='Felt', choices=[(o, o) for o in supportedFields])

    eksportForm = EksportForm(request.GET)

    if 'eksport' in request.GET:
        if not eksportForm.is_valid():
            raise Exception('Invalid exportForm')
        
        medlemmer = eksportForm.cleaned_data['m']
        fields = eksportForm.cleaned_data['f']

        medlemmer = medlemmer.annotateFulltNavn()
        if 'stemmegruppe' in fields:
            medlemmer = medlemmer.annotateStemmegruppe(kor=kor, understemmegruppe=True, includeDirr=True)

        response = downloadFile('MyTXS-eksport.csv', content_type='text/csv')
        writer = csv.writer(response)

        writer.writerow(['Navn'] + fields)
        for medlem in medlemmer:
            row = []
            for field in ['fulltNavn'] + fields:
                if field == 'matpreferanse':
                    row.append(', '.join(list(map(lambda t: t[1], filter(lambda t: t[0] in intToBitList(getattr(medlem, field)), enumerate(consts.matpreferanseOptions))))))
                else:
                    row.append(getattr(medlem, field))
            writer.writerow(row)

        mail.mail_admins(subject='Eksport!', message='''\
Eksport siden har blitt brukt av %s.\n
De hentet ut informasjon om følgende medlemmer: %s\n
For disse medlemmene hentet de ut: %s\n
''' % (str(request.user.medlem), '\n- '.join(['']+list(map(lambda m: str(m), medlemmer))), '\n- '.join(['']+list(fields))))

        return response

    if 'fraværEksport' in request.GET:
        hendelser = Hendelse.objects.filter(inneværendeSemester('startDate')).filter(
            kategori=Hendelse.OBLIG,
            kor__navn=kor,
            sluttTime__isnull=False # Dette betyr at hendelsen har en varighet
        ).annotateDirigentTilstede()

        medlemmer = Medlem.objects.filter(
            oppmøter__hendelse__in=hendelser
        ).distinct().prefetch_related(
            Prefetch('oppmøter', queryset=Oppmøte.objects.filter(
                hendelse__in=hendelser
            ).order_by('hendelse'))
        )

        response = downloadFile('MyTXS-eksport.csv', content_type='text/csv')
        writer = csv.writer(response)

        writer.writerow([*',name,address,zip,city,emailAddress,phoneNumber,gender,yearOfBirth,'.split(','), *['' for h in hendelser]])
        writer.writerow([*'date,,,,,,,,,Dato'.split(','), *[h.start.strftime('%d.%m.%Y') for h in hendelser]])
        writer.writerow([*'time,,,,,,,,,Starttid'.split(','), *[h.start.strftime('%H:%M') for h in hendelser]])
        writer.writerow([*'type,,,,,,,,,Hvordan er samlingen gjennomført?'.split(','), *['F' for h in hendelser]])
        writer.writerow([*'hoursWithoutTeacher,,,,,,,,,Timer uten lærer'.split(','), *[(str(round(h.varighet/60, 2)).replace('.', ',') if not h.dirigentTilstede else 0) for h in hendelser]])
        writer.writerow([*'hours,Navn,Adresse,Postnummer,Poststed,Epostadresse,Telefon,Kjønn,Fødselsår,Timer med lærer'.split(','), *[(str(round(h.varighet/60, 2)).replace('.', ',') if h.dirigentTilstede else 0) for h in hendelser]])
        
        for i, medlem in enumerate(medlemmer):
            postNummer, postSted = '', ''
            if medlem.boAdresse.split(',')[1:] and len(medlem.boAdresse.split(',')[1].split()) > 1:
                postNummer = medlem.boAdresse.split(',')[1].split()[0]
                postSted = medlem.boAdresse.split(',')[1].split()[1]

            row = [i, medlem.navn, medlem.boAdresse.split(',')[0], postNummer, postSted, medlem.epost, medlem.tlf, 'K' if medlem.storkorNavn() == consts.Kor.TKS else 'M', medlem.fødselsdato.year if medlem.fødselsdato else '', '']

            # Må ta høyde for at permisjon kan medføre færre oppmøter enn hendelser
            oppmøteIndex=0
            for hendelse in hendelser:
                if oppmøteIndex == len(medlem.oppmøter.all()):
                    row.append('')
                elif medlem.oppmøter.all()[oppmøteIndex].hendelse_id == hendelse.id:
                    row.append('X' if medlem.oppmøter.all()[oppmøteIndex].fravær != None else '')
                    oppmøteIndex += 1
                else:
                    row.append('')

            writer.writerow(row)
        
        mail.mail_admins(subject='Fravær Eksport!', message=f'Eksport siden sin fravær funksjon har blitt brukt av {str(request.user.medlem)}.')

        return response

    return render(request, 'mytxs/eksport.html', {
        'eksportForm': eksportForm,
        'visCSVLenke': eksportForm.is_valid() and eksportForm.cleaned_data['m'] and eksportForm.cleaned_data['f']
    })


def publish(request, key):
    if os.environ.get('PUBLISH_KEY') == key and os.environ.get('PUBLISH_PATH'):
        os.system(os.environ['PUBLISH_PATH'])
        return HttpResponse('Publish script started!')
    else:
        return HttpResponse('Publish script not started, missing environment variables!')
