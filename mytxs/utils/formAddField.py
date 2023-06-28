from django import forms

from mytxs.fields import MyModelMultipleChoiceField

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
            self.fields[related_name].initial = getattr(self.instance, related_name).all().values_list('id', flat=True)

        def save(self, *args, **kwargs):
            instance = super().save(*args, **kwargs)
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

        def save(self, commit=True):
            if self.cleaned_data['DELETE']:
                return self.instance.delete()
            return super().save()
    
    return NewForm
