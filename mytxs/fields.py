from django import forms
from django.db import models

class MyDateFormField(forms.DateField):
    "Et formField som gir input[type=date]"
    widget = forms.widgets.DateInput(attrs={'type': 'date'})

class MyDateField(models.DateField):
    "Et model field som gir et widget med input[type=date]"
    def formfield(self, **kwargs):
        defaults = {'form_class': MyDateFormField}
        defaults.update(kwargs)
        return super().formfield(**defaults)


class MySelectMultiple(forms.widgets.SelectMultiple):
    "Et widget som bare displaye de som er i enableQueryset (om det er satt)"
    enableQueryset = False

    def create_option(self, *args, **kwargs):
        options_dict = super().create_option(*args, **kwargs)
        
        if self.enableQueryset != False and options_dict['value'].instance not in self.enableQueryset:
            # print(f'Disabling: {options_dict["value"].instance}')
            options_dict['attrs']['disabled'] = ''

        return options_dict

class MyModelMultipleChoiceField(forms.ModelMultipleChoiceField):
    "Et form field som har setEnableQueryset og setEnableQuerysetKor metodene"
    widget = MySelectMultiple

    initialValue = False
    "Queryset av alternativ som er selected initially"
    enableQueryset = False
    "Queryset av de som skal enables (ikke vær disabled)"

    def setEnableQueryset(self, enableQueryset, initialValue):
        """Sett hvilke verdier som skal vær enabled basert på queryset. 
        For initialValue er det lettest å si request.instance.tilganger.all()
        """
        self.enableQueryset = enableQueryset
        self.widget.enableQueryset = enableQueryset

        self.initialValue = initialValue

    def setEnableQuerysetKor(self, kor, initialValue):
        """Sett hvilke verdier som skal vær enabled, og en initial value
        for InitialValue. Det er lettest å si request.instance.tilganger.all()
        Dette er en shorthand for setEnableQueryset som oversett fra liste med 
        kor til queryset:)"""

        self.setEnableQueryset(
            self.queryset.filter(kor__in=kor),
            initialValue
        )

    def clean(self, value):
        returnValue = super().clean(value)

        # Så problemet e at fra denne clean metoden kan e ikkje lagre direkte, 
        # men sende heller videre hva verdien skal være, i form av queryset. 
        # Dette kunna vi jobba rundt dersom vi kunna skaffa ka verdien va før den vart endra, 
        # mest realistisk via å gå på form.instance, men vi har ikke tilgang til form fra fieldet...

        # E fann ingen bedre måte å gjør det på enn å si at når man kjøre setEnableQuerySet må man også gi en initialValue.
        # Kjipt, men trur virkelig ikke det va en lurar måte å gjør det på.
        
        if self.enableQueryset != False:
            enablePKs = self.enableQueryset.values_list('pk', flat=True)
            returnValue = (returnValue.filter(pk__in=enablePKs)) | (self.initialValue.exclude(pk__in=enablePKs))
            
        return returnValue

class MyManyToManyField(models.ManyToManyField):
    "Et model field med et form field som kan disable m2m options på seg:)"
    def formfield(self, **kwargs):
        defaults = {'form_class': MyModelMultipleChoiceField}
        defaults.update(kwargs)
        return super().formfield(**defaults)
