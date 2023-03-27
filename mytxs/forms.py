from django import forms

from mytxs.models import *

class MedlemsDataForm(forms.ModelForm):
    fødselsdato = forms.DateField(
        widget = forms.widgets.DateInput(attrs={'type': 'date'})
    )

    class Meta:
        model = Medlem
        fields = ['navn', 'fødselsdato', 'epost', 'tlf', 'studieEllerJobb', 'boAdresse', 'foreldreAdresse']