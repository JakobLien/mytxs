from django import forms

from mytxs.models import *

class MedlemsDataForm(forms.ModelForm):
    # fødselsdato = forms.DateField(
    #     widget = forms.widgets.DateInput(attrs={'type': 'date'}),
    # )

    class Meta:
        model = Medlem
        fields = ['fornavn', 'mellomnavn', 'etternavn', 'fødselsdato', 'epost', 'tlf', 'studieEllerJobb', 'boAdresse', 'foreldreAdresse', 'bilde']

class MedlemListeFilterForm(forms.Form):
    kor = forms.ChoiceField(label="kor", required=False, choices=[("", "Kor")] + [(kor.kortTittel, kor.kortTittel) for kor in Kor.objects.all()])
    K = forms.ChoiceField(label="K", required=False, choices=[("", "Opptaksår")] + [(year, year) for year in range(2023, 1909, -1)])
    stemmegruppe = forms.ChoiceField(label="stemmegruppe", required=False, choices=[("", "Stemmegruppe")] + [(i, i) for i in ["dirigent", "1S", "2S", "1A", "2A", "1T", "2T", "1B", "2B"]])
    aktiv = forms.BooleanField(label="aktiv", required=False)
    navn = forms.CharField(label="navn", required=False, max_length=100)
