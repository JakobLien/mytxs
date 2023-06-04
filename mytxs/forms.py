from django import forms

from mytxs.models import Kor, Medlem, Verv

from mytxs.fields import MyDateFormField
from mytxs.utils.modelUtils import toolTip

class MedlemFilterForm(forms.Form):
    kor = forms.ModelChoiceField(required=False, queryset=Kor.objects.all())
    K = forms.ChoiceField(required=False, choices=[("", "Opptaksår")] + [(year, year) for year in range(2023, 1909, -1)])
    stemmegruppe = forms.ChoiceField(required=False, choices=[("", "Stemmegruppe")] + [(i, i) for i in ["dirigent", "1S", "2S", "1A", "2A", "1T", "2T", "1B", "2B"]])
    dato = MyDateFormField(required=False)
    navn = forms.CharField(required=False, max_length=100)

class LoggFilterForm(forms.Form):
    kor = forms.ModelChoiceField(required=False, queryset=Kor.objects.all())
    model = forms.ChoiceField(required=False, choices=[("", "Model")])
    pk = forms.IntegerField(required=False, label='PK', min_value=1)
    author = forms.ModelChoiceField(required=False, queryset=Medlem.objects.all())
    start = MyDateFormField(required=False)
    slutt = MyDateFormField(required=False)

class BaseOptionForm(forms.Form):
    alleAlternativ = forms.BooleanField(required=False, help_text=toolTip("""\
Dette får det til å dukke opp alternativ som er utenfor korene du har tilgang til, \
f.eks. for å gi verv, tilganger osv på tvers av kor. Skjeldent nyttig, men fint å \
kunne tenke e."""))

class OptionForm(BaseOptionForm):
    "Pass meg kwarg 'fields'"
    def __init__(self, *args, **kwargs):
        fields = kwargs.pop('fields')
        super().__init__(*args, **kwargs)
        self.fields = {k: v for k, v in self.fields.items() if k in fields}