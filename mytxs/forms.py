from django import forms

from mytxs.models import Medlem

from mytxs.fields import MyDateFormField

class MedlemsDataForm(forms.ModelForm):
    class Meta:
        model = Medlem
        fields = ['fornavn', 'mellomnavn', 'etternavn', 'fødselsdato', 'epost', 'tlf', 'studieEllerJobb', 'boAdresse', 'foreldreAdresse', 'bilde']

class MedlemListeFilterForm(forms.Form):
    kor = forms.ChoiceField(required=False, choices=[("", "Kor")] + [(kor, kor) for kor in ["TSS", "P", "KK", "C", "TKS"]])
    K = forms.ChoiceField(required=False, choices=[("", "Opptaksår")] + [(year, year) for year in range(2023, 1909, -1)])
    stemmegruppe = forms.ChoiceField(required=False, choices=[("", "Stemmegruppe")] + [(i, i) for i in ["dirigent", "1S", "2S", "1A", "2A", "1T", "2T", "1B", "2B"]])
    dato = MyDateFormField(required=False)
    navn = forms.CharField(required=False, max_length=100)