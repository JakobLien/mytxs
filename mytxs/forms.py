from django import forms

from mytxs.models import *

class MedlemsDataForm(forms.ModelForm):
    fødselsdato = forms.DateField(
        widget = forms.widgets.DateInput(attrs={'type': 'date'})
    )

    class Meta:
        model = Medlem
        fields = ['fornavn', 'mellomnavn', 'etternavn', 'fødselsdato', 'epost', 'tlf', 'studieEllerJobb', 'boAdresse', 'foreldreAdresse', 'bilde']

class MedlemListeFilterForm(forms.Form):
    kor = forms.ChoiceField(label="kor", required=False, choices=[("", "Kor")] + [(kor, kor) for kor in ["TSS", "P", "KK", "C", "TKS"]])
    K = forms.ChoiceField(label="K", required=False, choices=[("", "Opptaksår")] + [(year, year) for year in range(2023, 1909, -1)])
    navn = forms.CharField(label="navn", required=False, max_length=100)
