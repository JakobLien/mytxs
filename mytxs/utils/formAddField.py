import hashlib

from django import forms
from django.core.files.base import ContentFile
from django.forms import ValidationError
from django.db import IntegrityError

from mytxs import consts
from mytxs.fields import MultipleFileField, MyModelMultipleChoiceField
from mytxs.models import Medlem
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


def hashFile(file, chunk_size=8192):
    h = hashlib.sha256()
    for chunk in iter(lambda: file.read(chunk_size), b''):
        h.update(chunk)
    file.seek(0) # VIKTIG! Om vi ikkje gjør dette blir alle opplastedde filer tomme!
    return h.digest()


def addBulkFileUpload(SangForm):
    class NewForm(SangForm):
        BULK_UPLOAD=MultipleFileField(required=False)

        def clean(self, *args, **kwargs):
            super().clean(*args, **kwargs)

            # Sjekk at opplastede filer faktisk har ulik data fra alle andre lagrede filer, 
            # og andre filer som lastes opp samtidig. 
            if self.instance.pk:
                existingFiles = [f.fil for f in self.instance.filer.all()]
                for file in self.cleaned_data['BULK_UPLOAD']:
                    for existingFile in existingFiles:
                        if hashFile(file) == hashFile(existingFile):
                            raise ValidationError(f'Opplastede fil {file.name} har samme innhold som {existingFile.name}')
                    existingFiles.append(file)

        def save(self, *args, **kwargs):
            super().save(*args, **kwargs)

            for file in self.cleaned_data['BULK_UPLOAD']:
                # Legg på -1, -2 osv om vi allerede har en fil med det navnet. 
                unikSangNr = 0
                suffix = '' if '.' not in file.name else '.' + file.name.split('.')[-1]
                fileNameWithoutSuffix = file.name[:-len(suffix)]
                while True:
                    try:
                        file.name = fileNameWithoutSuffix + (f'-{unikSangNr}' if unikSangNr else '') + suffix
                        self.instance.filer.create(
                            navn=file.name,
                            fil=ContentFile(file.file.read(), name=file.name)
                        )
                        break
                    except IntegrityError as e:
                        unikSangNr += 1

    return NewForm
