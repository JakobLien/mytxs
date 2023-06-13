from django import forms

from mytxs.models import Kor, Medlem
from mytxs.fields import MyDateFormField
from mytxs.consts import bareKorKortTittel, loggModelNames, hovedStemmegrupper, defaultChoice
from mytxs.utils.modelUtils import toolTip

class MedlemFilterForm(forms.Form):
    kor = forms.ModelChoiceField(required=False, queryset=Kor.objects.filter(kortTittel__in=bareKorKortTittel))
    K = forms.ChoiceField(required=False, choices=[defaultChoice] + [(year, year) for year in range(2023, 1909, -1)])
    stemmegruppe = forms.ChoiceField(required=False, choices=[defaultChoice] + [(i, i) for i in ["dirigent", *hovedStemmegrupper]])
    dato = MyDateFormField(required=False)
    navn = forms.CharField(required=False, max_length=100)

class LoggFilterForm(forms.Form):
    kor = forms.ModelChoiceField(required=False, queryset=Kor.objects.filter(kortTittel__in=bareKorKortTittel))
    model = forms.ChoiceField(required=False, choices=[defaultChoice] + [(modelName, modelName) for modelName in loggModelNames])
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
