import datetime
from django import forms
from django.db.models import Q
from django.db.models.fields import BLANK_CHOICE_DASH
from django.shortcuts import redirect

from mytxs import consts
from mytxs.fields import MyDateFormField
from mytxs.models import Hendelse, Kor, Medlem, Verv
from mytxs.utils.formUtils import postIfPost, toolTip
from mytxs.utils.modelUtils import getPathToKor, refreshQueryset, stemmegruppeVerv, vervInnehavelseAktiv


class KorFilterForm(forms.Form):
    'Generisk FilterForm som filtrerre på kor'
    kor = forms.ModelChoiceField(required=False, queryset=Kor.objects.filter(kortTittel__in=consts.bareKorKortTittel))

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

    def applyFilter(self, queryset):
        # Fordi medlemmer har et særegent forhold til kor, bruker vi ikke super.applyFilter i det heletatt. 
        # Vi bare arve felt-spesifikasjonen fra NavnKorFilterForm. 
        if not self.is_valid():
            raise Exception('Invalid filterForm')
        
        sgVerv = Verv.objects.filter(stemmegruppeVerv('', includeDirr=True))
        if kor := self.cleaned_data['kor']:
            sgVerv = sgVerv.filter(kor=kor)
        
        if K := self.cleaned_data['K']:
            # Siden vi må annotateKarantenekor må vi først refresh querysettet siden man 
            # kanskje ikkje har tilgang til medlemmer via småkoret man filtrerer på.
            queryset = refreshQueryset(queryset)
            queryset = queryset.annotateKarantenekor(
                kor=kor or None
            )
            queryset = queryset.filter(K=K)
        
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


class BaseOptionForm(forms.Form):
    optionFormSubmitted = forms.BooleanField(widget=forms.HiddenInput(), initial=True)
    disableTilganger = forms.BooleanField(required=False, help_text=toolTip(
        'Vis hvordan siden ser ut uten dine tilganger.'))
    bareAktive = forms.BooleanField(required=False, help_text=toolTip(
        'Bare få opp/ha tilgang til aktive medlemmer.'))
    tversAvKor = forms.BooleanField(required=False, help_text=toolTip(
        'Dette skrur på tversAvKor tilgangen din, altså gjør at du kan sette relasjoner på tvers av kor.'))
    adminTilganger = forms.ChoiceField(required=False, choices=BLANK_CHOICE_DASH + [(o, o) for o in ['Alle'] + consts.alleKorKortTittel], help_text=toolTip(
        'Dette gir deg alle tilganger i det valgte koret, bare tilgjengelig for admin brukere.'))


class OptionForm(BaseOptionForm):
    'Pass meg kwarg "fields"'
    def __init__(self, *args, **kwargs):
        fields = kwargs.pop('fields')
        super().__init__(*args, **kwargs)
        self.fields = {k: v for k, v in self.fields.items() if k in fields}


def addOptionForm(request):
    if not hasattr(request.user, 'medlem'):
        # Om de ikke har en user, skip dette. Det e mest nyttig for admin
        return
    
    faktiskeTilganger = request.user.medlem.faktiskeTilganger

    optionFormFields = ['optionFormSubmitted']
    if request.user.is_superuser:
        optionFormFields.extend(['bareAktive', 'tversAvKor', 'adminTilganger'])
    
    # Den store majoritet av brukere har ikke tilgang til noe, derfor filtrere vi på det først. 
    if faktiskeTilganger.exists():
        if faktiskeTilganger.filter(navn='tversAvKor').exists():
            optionFormFields.extend(['tversAvKor'])
        optionFormFields.extend(['disableTilganger', 'bareAktive'])

    if len(optionFormFields) == 1:
        # Om du ikke har noen options, ikke legg til optionForm på request
        # (og følgelig ikke vis det til brukeren)
        return
    
    request.optionForm = OptionForm(postIfPost(request, 'optionForm'), initial=request.user.medlem.innstillinger, fields=optionFormFields, prefix='optionForm')
 
    # Vi bruke optionFormSubmitted for å sjekk om optionform va sendt. 
    # Trur ellers det er umulig å sjekke dette sida når booleanFields er false sendes 
    # de ikke i request.POST, som medfører at når andre forms sendes telles det i utgangspunktet 
    # som et gyldig optionForm med bare false verdier. 
    if request.optionForm.is_valid() and request.optionForm.cleaned_data['optionFormSubmitted'] == True:
        request.user.medlem.innstillinger = request.optionForm.cleaned_data
        request.user.medlem.save()
        return redirect(request.get_full_path())
