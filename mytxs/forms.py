from django import forms
from django.db.models import Q

from mytxs import consts
from mytxs.fields import MyDateFormField
from mytxs.models import Kor, Logg, Medlem, Verv
from mytxs.utils.modelUtils import stemmegruppeVerv, toolTip, vervInnehavelseAktiv


class NavnKorFilterForm(forms.Form):
    'Generisk FilterForm som filtrerre på felt navn og relation kor'
    navn = forms.CharField(required=False, max_length=100)
    kor = forms.ModelChoiceField(required=False, queryset=Kor.objects.filter(kortTittel__in=consts.bareKorKortTittel))

    def applyFilter(self, queryset):
        'Filtrere et queryset basert på NavnKorFilterForm'
        if not self.is_valid():
            raise Exception('Invalid filterForm')
        
        if kor := self.cleaned_data['kor']:
            queryset = queryset.filter(kor=kor)

        if navn := self.cleaned_data['navn']:
            # Dette sjekke om alle ordan e i navnet, heller enn at helheten e i navnet. 
            queryset = queryset.filter(*map(lambda n: Q(navn__icontains=n), navn.split()))

        return queryset


class TurneFilterForm(NavnKorFilterForm):
    år = forms.ChoiceField(required=False, choices=[consts.defaultChoice] + [(year, year) for year in range(2023, 1909, -1)])

    def applyFilter(self, queryset):
        queryset = super().applyFilter(queryset)

        if år := self.cleaned_data['år']:
            queryset = queryset.filter(start__year=år)

        return queryset


class MedlemFilterForm(NavnKorFilterForm):
    # Formet arver feltan navn og kor, men implementere applyFilter dem annerledes fordi medlemmer har navn og kor på en annen måte enn øverige objekter
    K = forms.ChoiceField(required=False, choices=[consts.defaultChoice] + [(year, year) for year in range(2023, 1909, -1)])
    stemmegruppe = forms.ChoiceField(required=False, choices=[consts.defaultChoice] + [(i, i) for i in ['Dirigent', 'ukjentStemmegruppe', *consts.hovedStemmegrupper]])
    dato = MyDateFormField(required=False)

    def applyFilter(self, queryset=Medlem.objects):
        if not self.is_valid():
            raise Exception('Invalid filterForm')
        
        sgVerv = Verv.objects.filter(stemmegruppeVerv('', includeDirr=True))
        if kor := self.cleaned_data['kor']:
            sgVerv = sgVerv.filter(kor=kor)
        
        if K := self.cleaned_data['K']:
            queryset = queryset.annotateKarantenekor(
                kor=kor or None
            )
            queryset = queryset.filter(K=K)
        
        if stemmegruppe := self.cleaned_data['stemmegruppe']:
            sgVerv = sgVerv.filter(navn__iendswith=stemmegruppe)

        if dato := self.cleaned_data['dato']:
            queryset = queryset.filter(
                vervInnehavelseAktiv(dato=dato),
                vervInnehavelse__verv__in=sgVerv
            )
        elif kor or stemmegruppe or K:
            queryset = queryset.filter(vervInnehavelse__verv__in=sgVerv)

        if navn := self.cleaned_data['navn']:
            queryset = queryset.annotateFulltNavn()
            queryset = queryset.filter(*map(lambda n: Q(fulltNavn__icontains=n), navn.split()))
        
        return queryset


class LoggFilterForm(forms.Form):
    kor = forms.ModelChoiceField(required=False, queryset=Kor.objects.filter(kortTittel__in=consts.bareKorKortTittel))
    model = forms.ChoiceField(required=False, choices=[consts.defaultChoice] + [(modelName, modelName) for modelName in consts.loggedModelNames])
    pk = forms.IntegerField(required=False, label='PK', min_value=1)
    author = forms.ModelChoiceField(required=False, queryset=Medlem.objects.all())
    start = MyDateFormField(required=False)
    slutt = MyDateFormField(required=False)

    def applyFilter(self, queryset=Logg.objects):
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
    alleAlternativ = forms.BooleanField(required=False, help_text=toolTip('''\
Dette får det til å dukke opp alternativ som er utenfor korene du har tilgang til, \
f.eks. for å gi verv, tilganger osv på tvers av kor. Skjeldent nyttig, men fint å \
kunne tenke e.'''))

class OptionForm(BaseOptionForm):
    'Pass meg kwarg "fields"'
    def __init__(self, *args, **kwargs):
        fields = kwargs.pop('fields')
        super().__init__(*args, **kwargs)
        self.fields = {k: v for k, v in self.fields.items() if k in fields}
