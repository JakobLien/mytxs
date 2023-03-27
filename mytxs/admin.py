from django.contrib import admin

# Register your models here.

from .models import *


class VervInnehavelseInline(admin.StackedInline):
    model = VervInnehavelse
    extra = 1

class DekorasjonInnehavelseInline(admin.StackedInline):
    model = DekorasjonInnehavelse
    extra = 1


class MedlemAdmin(admin.ModelAdmin):
    # fieldsets = [
    #     (None,               {'fields': ['question_text']}),
    #     ('Date information', {'fields': ['pub_date']}),
    # ]
    inlines = [VervInnehavelseInline, DekorasjonInnehavelseInline]
    #list_display = ('question_text', 'pub_date', 'was_published_recently')
    #list_filter = ['pub_date']
    #search_fields = ['question_text']

class VervAdmin(admin.ModelAdmin):
    inlines = [VervInnehavelseInline]

admin.site.register(Medlem, MedlemAdmin)
admin.site.register(Verv, VervAdmin)
admin.site.register(Tilgang)
admin.site.register(Kor)
admin.site.register(VervInnehavelse)
admin.site.register(Dekorasjon)
admin.site.register(DekorasjonInnehavelse)

