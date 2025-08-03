from django import forms

from mytxs import consts
from mytxs.fields import MyModelMultipleChoiceField
from mytxs.models import Hendelse, Medlem
from mytxs.utils.modelUtils import stemmegruppeVerv, vervInnehavelseAktiv

# Alt som legg til fields på forms

def addReverseM2M(ModelForm, related_name):
    'Utility funksjon for å hiv på reverse relaterte M2M relasjoner'
    relatedModel = getattr(ModelForm._meta.model, related_name).rel.related_model

    # Mesteparten av dette kjem herifra: https://stackoverflow.com/a/53859922/6709450
    class NewForm(ModelForm):
        # Triksete løsning hentet herifra: https://stackoverflow.com/a/20608050/6709450
        vars()[related_name] = MyModelMultipleChoiceField(
            queryset=relatedModel.objects.all(),
            required=False,
        )

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            if self.instance.pk:
                self.fields[related_name].initial = getattr(self.instance, related_name).all().values_list('id', flat=True)

        def save(self, *args, **kwargs):
            instance = super().save(*args, **kwargs)
            # Må ha inn dette for å ikkje krasje når vi sletter modelform.instance
            if self.instance.pk and hasattr(instance, related_name):
                getattr(instance, related_name).set(self.cleaned_data[related_name])
            return instance

    return NewForm

def addDeleteCheckbox(ModelForm):
    '''
    Legg til en delte checkbox og at når modelform.save kjøre slettes instansen.
    Boolean verdien kan aksesseres etter is_valid() via form.cleaned_data['DELETE'].
    '''
    class NewForm(ModelForm):
        DELETE = forms.BooleanField(label='Slett', required=False)

        def save(self):
            if self.cleaned_data['DELETE']:
                return self.instance.delete()
            return super().save()
    
    return NewForm


def addDeleteUserCheckbox(MedlemModelForm):
    class NewForm(MedlemModelForm):
        DELETEUSER = forms.BooleanField(label='Slett bruker', required=False)

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

            # Sjul delete feltet dersom medlemmet ikkje har en user
            if not self.instance.user:
                self.fields = {k: v for k, v in self.fields.items() if k != 'DELETEUSER'}

        def save(self):
            if 'DELETEUSER' in self.fields.keys() and self.cleaned_data['DELETEUSER']:
                return self.instance.user.delete()
            return super().save()
    
    return NewForm


def addHendelseMedlemmer(HendelseForm):
    'Legg til medlemmer felt på et Undergruppe Hendelse form'
    class NewForm(HendelseForm):
        medlemmer = MyModelMultipleChoiceField(required=False, queryset=Medlem.objects.none())

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

            self.fields['medlemmer'].queryset = Medlem.objects.filter(
                vervInnehavelseAktiv(dato=self.instance.startDate), 
                stemmegruppeVerv('vervInnehavelser__verv', includeDirr=True),
                vervInnehavelser__verv__kor__navn__in=consts.bareStorkorNavn if self.instance.kor.navn == consts.Kor.Sangern else [self.instance.kor.navn]
            ).distinct()

            self.fields['medlemmer'].initial = Medlem.objects.filter(oppmøter__hendelse=self.instance)

            self.fields['medlemmer'].setEnableQueryset(
                enableQueryset=self.fields['medlemmer'].queryset.exclude(
                    pk__in=Medlem.objects.filter(
                        vervInnehavelseAktiv(dato=self.instance.startDate),
                        vervInnehavelser__verv__tilganger__navn__in=self.instance.prefiksArray,
                        vervInnehavelser__verv__tilganger__kor=self.instance.kor
                    )
                ),
                initialValue=self.fields['medlemmer'].initial
            )

        def save(self, *args, **kwargs):
            if self.is_valid():
                self.instance.genererOppmøter(undergruppeMedlemmer=self.cleaned_data['medlemmer'])
            super().save(*args, **kwargs)

    return NewForm
