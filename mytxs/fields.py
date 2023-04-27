
from django import forms
from django.db import models

# Definer et formfield med input type="date" widget
class MyDateFormField(forms.DateField):
    widget = forms.widgets.DateInput(attrs={'type': 'date'})

# Definer et model field som bruke det form-fieldet
class MyDateField(models.DateField):
    def formfield(self, **kwargs):
        defaults = {'form_class': MyDateFormField}
        defaults.update(kwargs)
        return super(models.DateField, self).formfield(**defaults)
