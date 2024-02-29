import datetime
from django import forms
from django.db.models import Q
from django.db.models.fields import BLANK_CHOICE_DASH
from django.shortcuts import redirect

from mytxs import consts
from mytxs.fields import MyDateFormField
from mytxs.models import Hendelse, Kor, Medlem, MedlemQuerySet, Verv, Oppmøte
from mytxs.utils.formUtils import postIfPost, toolTip
from mytxs.utils.modelUtils import getPathToKor, korLookup, qBool, refreshQueryset, stemmegruppeVerv, vervInnehavelseAktiv


class KorFilterForm(forms.Form):
    'Generisk FilterForm som filtrerre på kor'
    kor = forms.ModelChoiceField(required=False, queryset=Kor.objects.filter(navn__in=consts.alleKorNavn))

    def applyFilter(self, queryset):
        'Filtrere et queryset basert på KorFilterForm'
        if not self.is_valid():
            raise Exception('Invalid filterForm')
        
        if kor := self.cleaned_data['kor']:
            queryset = queryset.filter(**{getPathToKor(queryset.model): kor})

        return queryset


class NavnKorFilterForm(KorFilterForm):
    'Generisk FilterForm som filtrerre på navn og kor'
    navn = forms.CharField(required=False, max_length=100)

    def applyFilter(self, queryset):
        'Filtrere et queryset basert på NavnKorFilterForm'
        queryset = super().applyFilter(queryset)

        if navn := self.cleaned_data['navn']:
            # Dette sjekke om alle ordan e i navnet, heller enn at helheten e i navnet. 
            queryset = queryset.filter(*map(lambda n: Q(navn__icontains=n), navn.split()))

        return queryset


class TurneFilterForm(NavnKorFilterForm):
    år = forms.ChoiceField(required=False, choices=BLANK_CHOICE_DASH + [(year, year) for year in range(2023, 1909, -1)])

    def applyFilter(self, queryset):
        queryset = super().applyFilter(queryset)

        if år := self.cleaned_data['år']:
            queryset = queryset.filter(start__year=år)

        return queryset


class VervFilterForm(NavnKorFilterForm):
    sistAktiv = forms.IntegerField(required=False, label='År siden siste innehaver', help_text=toolTip('Bare vis verv som har hatt innehavere siste n årene'))

    def applyFilter(self, queryset):
        queryset = super().applyFilter(queryset)

        if (sistAktiv := self.cleaned_data['sistAktiv']) or sistAktiv == 0:
            queryset = queryset.filter(
                Q(vervInnehavelser__start__year__gte=datetime.date.today().year - (sistAktiv or 0)) |
                (Q(vervInnehavelser__slutt__isnull=True) & Q(vervInnehavelser__isnull=False))
            )

        return queryset


class HendelseFilterForm(NavnKorFilterForm):
    start = MyDateFormField(required=False)
    slutt = MyDateFormField(required=False)
    kategori = forms.ChoiceField(choices=BLANK_CHOICE_DASH + list(Hendelse.KATEGORI_CHOICES), required=False)
    
    def applyFilter(self, queryset):
        queryset = super().applyFilter(queryset)

        if start := self.cleaned_data['start']:
            queryset = queryset.filter(startDate__gte=start)

        if slutt := self.cleaned_data['slutt']:
            queryset = queryset.filter(startDate__lte=slutt)

        if kategori := self.cleaned_data['kategori']:
            queryset = queryset.filter(kategori=kategori)
        
        return queryset


class MedlemFilterForm(NavnKorFilterForm):
    # Formet arver feltan navn og kor, men implementere applyFilter dem annerledes fordi medlemmer har navn og kor på en annen måte enn øverige objekter
    K = forms.ChoiceField(required=False, choices=BLANK_CHOICE_DASH + [(year, year) for year in range(2023, 1909, -1)])
    stemmegruppe = forms.ChoiceField(required=False, choices=BLANK_CHOICE_DASH + [(i, i) for i in ['Dirigent', 'ukjentStemmegruppe', *consts.hovedStemmegrupper]])
    dato = MyDateFormField(required=False)
    ikkeOverførtData = forms.BooleanField(required=False, label='Ikke overført data', help_text=toolTip('Bare vis medlemmer som ikke har overført dataen sin til MyTXS 2.0.'))
    harPermisjon = forms.ChoiceField(required=False, label='Har Permisjon', choices=[*BLANK_CHOICE_DASH, ('True', 'Har permisjon'), ('False', 'Har ikke permisjon')])
    notisInnhold = forms.CharField(required=False, label='Notis innhold')

    def __init__(self, *args, request=None, **kwargs):
        super().__init__(*args, **kwargs)

        # Bare vis notisInnhold søkefeltet dersom de har medlemsdata tilgangen
        if not request or not request.user.medlem.tilganger.filter(navn='medlemsdata').exists():
            self.fields = {k: v for k, v in self.fields.items() if k != 'notisInnhold'}

    def applyFilter(self, queryset):
        # Fordi medlemmer har et særegent forhold til kor, bruker vi ikke super.applyFilter i det heletatt. 
        # Vi bare arve felt-spesifikasjonen fra NavnKorFilterForm. 
        if not self.is_valid():
            raise Exception('Invalid filterForm')
        
        sgVerv = Verv.objects.filter(stemmegruppeVerv('', includeDirr=True))
        if kor := self.cleaned_data['kor']:
            sgVerv = sgVerv.filter(kor=kor)
        
        if karantenekor := self.cleaned_data['K']:
            # Siden vi må annotateKarantenekor må vi først refresh querysettet siden man 
            # kanskje ikkje har tilgang til medlemmer via småkoret man filtrerer på.
            queryset = refreshQueryset(queryset)
            queryset = queryset.annotateKarantenekor(
                kor=kor or None
            )
            queryset = queryset.filter(karantenekor=karantenekor)
        
        if stemmegruppe := self.cleaned_data['stemmegruppe']:
            sgVerv = sgVerv.filter(navn__iendswith=stemmegruppe)

        if dato := self.cleaned_data['dato']:
            queryset = queryset.filter(
                vervInnehavelseAktiv(dato=dato),
                vervInnehavelser__verv__in=sgVerv
            )
        elif kor or stemmegruppe:
            queryset = queryset.filter(vervInnehavelser__verv__in=sgVerv)

        if navn := self.cleaned_data['navn']:
            queryset = queryset.annotateFulltNavn()
            queryset = queryset.filter(*map(lambda n: Q(fulltNavn__icontains=n), navn.split()))
        
        if navn := self.cleaned_data['ikkeOverførtData']:
            queryset = queryset.filter(overførtData=False)

        if harPermisjon := self.cleaned_data['harPermisjon']:
            queryset = refreshQueryset(queryset)
            harPermQ = Q(
                vervInnehavelseAktiv(dato=dato) if dato else qBool(True),
                korLookup(kor, 'vervInnehavelser__verv__kor') if kor else qBool(True),
                Q(vervInnehavelser__verv__navn='Permisjon')
            )
            queryset = queryset.filter(harPermQ if harPermisjon == 'True' else ~harPermQ)
        
        if 'notisInnhold' in self.fields and (notis := self.cleaned_data['notisInnhold']):
            queryset = queryset.filter(*map(lambda n: Q(notis__icontains=n), notis.split()))
        
        queryset = queryset.order_by(*Medlem._meta.ordering)
        
        return queryset


class LoggFilterForm(KorFilterForm):
    model = forms.ChoiceField(required=False, choices=BLANK_CHOICE_DASH + [(modelName, modelName) for modelName in consts.loggedModelNames])
    pk = forms.IntegerField(required=False, label='PK', min_value=1)
    author = forms.ModelChoiceField(required=False, queryset=Medlem.objects.all())
    start = MyDateFormField(required=False)
    slutt = MyDateFormField(required=False)

    def applyFilter(self, queryset):
        if not self.is_valid():
            raise Exception('Invalid filterForm')
        
        if kor := self.cleaned_data['kor']:
            queryset = queryset.filter(kor=kor)

        if model := self.cleaned_data['model']:
            queryset = queryset.filter(model=model)

        if author := self.cleaned_data['author']:
            queryset = queryset.filter(author=author)

        if pk := self.cleaned_data['pk']:
            queryset = queryset.filter(instancePK=pk)

        if start := self.cleaned_data['start']:
            queryset = queryset.filter(timeStamp__date__gte=start)

        if slutt := self.cleaned_data['slutt']:
            queryset = queryset.filter(timeStamp__date__lte=slutt)

        return queryset


class OppmøteFilterForm(KorFilterForm):
    gyldig = forms.ChoiceField(required=False, choices=BLANK_CHOICE_DASH + list(map(lambda c: (str(c[0]), c[1]), Oppmøte.GYLDIG_CHOICES)))
    ankomst = forms.ChoiceField(required=False, choices=BLANK_CHOICE_DASH + list(map(lambda c: (str(c[0]), c[1]), Oppmøte.ANKOMST_CHOICES)))
    harMelding = forms.BooleanField(required=False, label='Har melding')
    hendelse = forms.ModelChoiceField(required=False, queryset=Hendelse.objects.all())
    medlem = forms.ModelChoiceField(required=False, queryset=Medlem.objects.all())
    stemmegruppe = forms.ChoiceField(required=False, choices=BLANK_CHOICE_DASH + [(i, i) for i in ['Dirigent', 'ukjentStemmegruppe', *consts.hovedStemmegrupper]])

    def __init__(self, *args, request=None, **kwargs):
        'Vi må fiks at dem ikkje får opp alle medlemmer og hendelser'
        super().__init__(*args, **kwargs)

        self.fields['hendelse'].queryset = request.user.medlem.redigerTilgangQueryset(Oppmøte, resModel=Hendelse)
        self.fields['medlem'].queryset = Medlem.objects.filter(
            oppmøter__hendelse__in=self.fields['hendelse'].queryset
        ).distinct()

    def applyFilter(self, queryset):
        queryset = super().applyFilter(queryset)

        if self.cleaned_data['harMelding']:
            queryset = queryset.exclude(melding='')

        if gyldig := self.cleaned_data['gyldig']:
            for bool in [True, None, False]:
                if gyldig == str(bool):
                    queryset = queryset.filter(gyldig=bool)
                    break
        
        if ankomst := self.cleaned_data['ankomst']:
            for bool in [True, None, False]:
                if ankomst == str(bool):
                    queryset = queryset.filter(ankomst=bool)
                    break

        if hendelse := self.cleaned_data['hendelse']:
            queryset = queryset.filter(hendelse=hendelse)

        if medlem := self.cleaned_data['medlem']:
            queryset = queryset.filter(medlem=medlem)

        if sg := self.cleaned_data['stemmegruppe']:
            queryset = MedlemQuerySet.annotateStemmegruppe(
                queryset,
                kor=self.cleaned_data['kor'],
                includeUkjent=True,
                pkPath='medlem__pk'
            )

            queryset = queryset.filter(stemmegruppe=sg)

        return queryset


class BaseOptionForm(forms.Form):
    optionFormSubmitted = forms.BooleanField(widget=forms.HiddenInput(), initial=True)
    disableTilganger = forms.BooleanField(required=False, help_text=toolTip(
        'Vis hvordan siden ser ut uten dine tilganger.'))
    bareAktive = forms.BooleanField(required=False, help_text=toolTip(
        'Bare få opp/ha tilgang til aktive medlemmer.'))
    tversAvKor = forms.BooleanField(required=False, help_text=toolTip(
        'Dette skrur på tversAvKor tilgangen din, altså gjør at du kan sette relasjoner på tvers av kor.'))
    adminTilganger = forms.MultipleChoiceField(required=False, choices=[(o, o) for o in consts.alleTilganger], 
        help_text=toolTip('Dette sier hvilke tilganger du får i det valgte koret, bare tilgjengelig for admin brukere.'))
    adminTilgangerKor = forms.MultipleChoiceField(required=False, choices=[(o, o) for o in consts.alleKorNavn], 
        help_text=toolTip('Dette gir deg alle tilganger i det valgte koret, bare tilgjengelig for admin brukere.'))


def subForm(baseForm, fields=None, exclude=None):
    'Pass meg kwarg "fields" og eller "exclude"'
    class SubForm(baseForm):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            if fields != None:
                self.fields = {k: v for k, v in self.fields.items() if k in fields}
            if exclude != None:
                self.fields = {k: v for k, v in self.fields.items() if k not in exclude}
    return SubForm


def addOptionForm(request):
    if not hasattr(request.user, 'medlem'):
        # Om de ikke har en user, skip dette. Det e mest nyttig for admin
        return
    
    faktiskeTilganger = request.user.medlem.faktiskeTilganger

    optionFormFields = ['optionFormSubmitted']
    if request.user.is_superuser:
        optionFormFields.extend(['disableTilganger', 'bareAktive', 'tversAvKor', 'adminTilgangerKor', 'adminTilganger'])
    
    # Den store majoritet av brukere har ikke tilgang til noe, derfor filtrere vi på det først. 
    elif faktiskeTilganger.exists():
        optionFormFields.extend(['disableTilganger', 'bareAktive'])
        if faktiskeTilganger.filter(navn='tversAvKor').exists():
            optionFormFields.extend(['tversAvKor'])

    if len(optionFormFields) == 1:
        # Om du ikke har noen options, ikke legg til optionForm på request
        # (og følgelig ikke vis det til brukeren)
        return
    
    OptionForm = subForm(BaseOptionForm, fields=optionFormFields)
    
    request.optionForm = OptionForm(postIfPost(request, 'optionForm'), initial=request.user.medlem.innstillinger, prefix='optionForm')
 
    # Vi bruke optionFormSubmitted for å sjekk om optionform va sendt. 
    # Trur ellers det er umulig å sjekke dette sida når booleanFields er false sendes 
    # de ikke i request.POST, som medfører at når andre forms sendes telles det i utgangspunktet 
    # som et gyldig optionForm med bare false verdier. 
    if request.optionForm.is_valid() and request.optionForm.cleaned_data['optionFormSubmitted'] == True:
        del request.optionForm.cleaned_data['optionFormSubmitted']
        request.user.medlem.innstillinger = request.optionForm.cleaned_data
        request.user.medlem.save()
        return redirect(request.get_full_path())
