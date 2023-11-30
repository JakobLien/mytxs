from django import forms
from django.db import models


class MyDateFormField(forms.DateField):
    'Et formfield som gir widget med input[type=date]'
    widget = forms.widgets.DateInput(attrs={'type': 'date'})


class MyDateField(models.DateField):
    'Et model field som gir et widget med input[type=date]'
    def formfield(self, **kwargs):
        defaults = {'form_class': MyDateFormField}
        defaults.update(kwargs)
        return super().formfield(**defaults)


class MyTimeFormField(forms.TimeField):
    'Et formfield som gir widget med input[type=time]'
    widget = forms.widgets.TimeInput(attrs={'type': 'time'})


class MyTimeField(models.TimeField):
    'Et model field som gir et widget med input[type=time]'
    def formfield(self, **kwargs):
        defaults = {'form_class': MyTimeFormField}
        defaults.update(kwargs)
        return super().formfield(**defaults)


class MySelectMultiple(forms.widgets.SelectMultiple):
    'Et widget som disable alle options ikkje i enableQuerysetPKs'
    enableQuerysetPKs = False

    def create_option(self, *args, **kwargs):
        options_dict = super().create_option(*args, **kwargs)
        
        # Det e veldig my raskar å sjekk PKer enn instances, en merkbar forskjell altså
        if self.enableQuerysetPKs != False and options_dict['value'] not in self.enableQuerysetPKs:
            options_dict['attrs']['disabled'] = ''

        return options_dict


class MyModelMultipleChoiceField(forms.ModelMultipleChoiceField):
    'Et form field som bruke enableQueryset for å disable alle options'
    widget = MySelectMultiple

    initialValue = False
    'Queryset av alternativ som er selected initially'
    enableQuerysetPKs = False
    'Queryset av de som skal enables (ikke vær disabled)'

    def setEnableQueryset(self, enableQueryset, initialValue):
        '''
        Sett hvilke verdier som skal vær enabled basert på queryset. 
        For initialValue er det lettest å si request.instance.tilganger.all()
        '''
        self.enableQuerysetPKs = enableQueryset.values_list('pk', flat=True)
        self.widget.enableQuerysetPKs = enableQueryset.values_list('pk', flat=True)

        self.initialValue = initialValue

    def setEnableQuerysetKor(self, kor, initialValue):
        '''
        Sett hvilke verdier som skal vær enabled, og en initial value
        for InitialValue. Det er lettest å si request.instance.tilganger.all()
        Dette er en shorthand for setEnableQueryset som oversett fra liste med 
        kor til queryset
        '''

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
        
        if self.enableQuerysetPKs != False:
            returnValue = (returnValue.filter(pk__in=self.enableQuerysetPKs)).distinct() | (self.initialValue.exclude(pk__in=self.enableQuerysetPKs)).distinct()
        
        return returnValue


class MyManyToManyField(models.ManyToManyField):
    'Et model field med et form field som kan disable m2m options på seg:)'
    def formfield(self, **kwargs):
        defaults = {'form_class': MyModelMultipleChoiceField}
        defaults.update(kwargs)
        return super().formfield(**defaults)


def bitListToInt(lVal):
    'Konvertere en liste av hvilke bits (fra høyre) som er satt til en int, altså [1, 3] -> 10'
    # Kopiere verdien så funksjonen ikkje ødelegg den opprinnelige verdien
    listValue = lVal
    if len(listValue) == 0:
        return 0
    val = 1 << int(listValue.pop())
        
    while len(listValue) > 0:
        val |= 1 << int(listValue.pop())
    
    return val


def intToBitList(val):
    'Konvertere en int til en liste av hvilke bits (fra høyre) som er satt, altså 10 -> [1, 3]'
    num = 0
    listValue = []
    while val > 0:
        if val & 1:
            listValue.append(num)
        num += 1
        val >>= 1
    
    return listValue


class BitmapTypedMultipleChoiceField(forms.TypedMultipleChoiceField):
    'Et TypedMultipleChoiceField som konvertere verdien til et bitmap på BigInteger.'
    def validate(self, value):
        pass
    
    def _coerce(self, value):
        # Kjøre etter to_python, så vi override her for å fjern at den sjekke at det e en liste. 
        # Det gjør vi alt i to_python, så vi lar det vær
        return self.coerce(value)
    
    def to_python(self, value):
        # Kjøre når formet skal parses inn
        if self.disabled:
            # Om feltet e disabled får vi her inn en int istedet!
            value = intToBitList(value)
        listVal = super().to_python(value)
        try:
            return bitListToInt(listVal)
        except (ValueError, TypeError, forms.ValidationError):
            raise forms.ValidationError(
                self.error_messages["invalid_choice"],
                code="invalid_choice",
                params={"value": value},
            )
    
    def has_changed(self, initial, data):
        if self.disabled:
            return False
        if initial is None:
            initial = 0
        if data is None:
            data = 0
        return initial != data
    
    def prepare_value(self, value):
        # Kjøre når formet skal genereres
        if isinstance(value, int):
            return intToBitList(value)
        return value


class BitmapMultipleChoiceField(models.BigIntegerField):
    description = 'Et modelfield som lagre multiselect som et bitmap på et BigIntegerField'

    def __init__(self, *args, blank=True, default=0, **kwargs):
        kwargs['choices'] = [*enumerate(kwargs.pop('choicesList'))]
        kwargs['default'] = default
        kwargs['blank'] = blank
        super().__init__(*args, **kwargs)
    
    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        # Det vi sett i __init__ må vi fjern igjen her
        kwargs['choicesList'] = [c[1] for c in kwargs.pop('choices')]
        if kwargs.get('default', 0) != 0:
            del kwargs['default']
        if kwargs.get('blank', True) != True:
            del kwargs['blank']
        return name, path, args, kwargs
    
    def get_choices(self, include_blank, **kwargs):
        # Denne overriden er nødvendig for å si at vi ikkje skal include_blank. 
        # Vi må ha blank=True på model for å si at fieldet ikke er required, 
        # men dette setter også inn BLANK_CHOICE_DASH. 
        return super().get_choices(include_blank=False, **kwargs)
    
    def validate(self, *args):
        pass
    
    def formfield(self, **kwargs):
        # This is a fairly standard way to set up some defaults
        # while letting the caller override them.
        defaults = {
            'choices_form_class': BitmapTypedMultipleChoiceField,
            'coerce': int,
            'empty_value': 0
        }
        defaults.update(kwargs)
        return super().formfield(**defaults)
