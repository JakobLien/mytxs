from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.forms import modelform_factory

from mytxs.models import *
from mytxs.utils.formAddField import addReverseM2M

class VervInnehavelseInline(admin.StackedInline):
    model = VervInnehavelse
    extra = 1
    show_change_link = True

class DekorasjonInnehavelseInline(admin.StackedInline):
    model = DekorasjonInnehavelse
    extra = 1
    show_change_link = True

@admin.register(Medlem)
class MedlemAdmin(admin.ModelAdmin):
    inlines = [VervInnehavelseInline, DekorasjonInnehavelseInline]
    form = addReverseM2M(modelform_factory(Medlem, exclude=[]), 'turneer')

@admin.register(Verv)
class VervAdmin(admin.ModelAdmin):
    inlines = [VervInnehavelseInline]
    form = addReverseM2M(modelform_factory(Verv, exclude=[]), 'tilganger')

@admin.register(Dekorasjon)
class DekorasjonAdmin(admin.ModelAdmin):
    inlines = [DekorasjonInnehavelseInline]

@admin.register(Logg)
class LoggingAdmin(admin.ModelAdmin):
    fields = ['timeStamp', 'instancePK', 'author', 'model', 'kor', 'change',  'value']
    readonly_fields = fields

class MedlemInline(admin.StackedInline):
    model = Medlem
    show_change_link = True
    fields = ['fornavn', 'etternavn']
    readonly_fields = fields
    can_delete = False

# Re-register UserAdmin
admin.site.unregister(User)
@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = UserAdmin.list_display + ('medlem',)

    # Fann ingen god måte på å få User til å vis medlemmet, så da blir det denne hacken, 
    # der vi vise en inline av medlem med ingen editable field og med endringslink. 
    inlines = [MedlemInline]

# Register øverige modeller vi ikkje treng å gjør nå med
admin.site.register([Kor, VervInnehavelse, DekorasjonInnehavelse, LoggM2M, Hendelse, Oppmøte, Lenke, Turne, Tilgang])
