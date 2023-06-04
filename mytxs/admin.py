from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

# Register your models here.
from django.contrib.auth.models import User

from mytxs.models import *

class VervInnehavelseInline(admin.StackedInline):
    model = VervInnehavelse
    extra = 1
    show_change_link = True

class DekorasjonInnehavelseInline(admin.StackedInline):
    model = DekorasjonInnehavelse
    extra = 1
    show_change_link = True

class VervInline(admin.StackedInline):
    model = Verv.tilganger.through
    extra = 1

@admin.register(Medlem)
class MedlemAdmin(admin.ModelAdmin):
    inlines = [VervInnehavelseInline, DekorasjonInnehavelseInline]

@admin.register(Tilgang)
class TilgangAdmin(admin.ModelAdmin):
    inlines = [VervInline]

@admin.register(Verv)
class VervAdmin(admin.ModelAdmin):
    inlines = [VervInnehavelseInline]

@admin.register(Dekorasjon)
class DekorasjonAdmin(admin.ModelAdmin):
    inlines = [DekorasjonInnehavelseInline]


@admin.register(Logg)
class LoggingAdmin(admin.ModelAdmin):
    fields = ["timeStamp", "instancePK", "author", "model", "change",  "value"]
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
admin.site.register([Kor, VervInnehavelse, DekorasjonInnehavelse])
