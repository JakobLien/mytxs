from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import FileResponse
from django.urls import include, path, register_converter

from mytxs import views, consts

class KorConverter:
    'Matche at en streng er en av de 6 koran'
    regex="|".join(map(lambda k: f"({k})", consts.alleKorNavn))

    def to_python(self, value):
        # Kunna veldig lett her ha erstatta verdien med det faktiske koret, om det e nyttig
        return value

    def to_url(self, value):
        return value
register_converter(KorConverter, "kor")

# Alt som skal kunne inkludere slash characteren må være av typen path istedet (og selvfølgelig til slutt i urlen)
# Ja, det e en hacky løsning, men det funke bra så e lar det vær:)

urlpatterns = [
    path('admin', admin.site.urls, name='admin'),
    path("__debug__/", include("debug_toolbar.urls")),

    path('', views.login, name='login'),
    path('logout', views.logout, name='logout'),
    path('endreLogin', views.endreLogin, name='endreLogin'),
    path('registrer/<int:medlemPK>', views.registrer, name='registrer'),
    path('overfør/<str:jwt>', views.overfør, name='overfør'),

    path('medlem', views.medlemListe, name='medlem'),
    path('medlem/<int:medlemPK>', views.medlem, name='medlem'),

    path('sjekkheftet/<str:side>', views.sjekkheftet, name='sjekkheftet'),
    path('sjekkheftet/<str:side>/<str:underside>', views.sjekkheftet, name='sjekkheftet'),

    path('semesterplan/<kor:kor>', views.semesterplan, name='semesterplan'),
    path('iCal/<kor:kor>/<int:medlemPK>', views.iCal, name='iCal'),

    path('meldFravær/<int:medlemPK>/<int:hendelsePK>', views.meldFravær, name='meldFravær'),
    path('egenFøring/<int:hendelsePK>', views.egenFøring, name='egenFøring'),

    path('vrangstrupen', views.vrangstrupen, name='vrangstrupen'),

    path('fravær/semesterplan/<kor:kor>/<int:medlemPK>', views.fraværSemesterplan, name='fraværSemesterplan'),
    path('fravær/<str:side>', views.fraværSide, name='fravær'),
    path('fravær/<str:side>/<str:underside>', views.fraværSide, name='fravær'),

    path('hendelse', views.hendelseListe, name='hendelse'),
    path('hendelse/<int:hendelsePK>', views.hendelse, name='hendelse'),

    path('lenker', views.lenker, name='lenker'),
    path('to/<kor:kor>/<path:lenkeNavn>', views.lenkeRedirect, name='lenkeRedirect'),

    path('dekorasjon', views.dekorasjonListe, name='dekorasjon'),
    path('dekorasjon/<kor:kor>/<path:dekorasjonNavn>', views.dekorasjon, name='dekorasjon'),

    path('verv', views.vervListe, name='verv'),
    path('verv/<kor:kor>/<path:vervNavn>', views.verv, name='verv'),

    path('tilgang/<kor:kor>/<str:tilgangNavn>', views.tilgang, name='tilgang'),
    path('tilgang', views.tilgangSide, name='tilgang'),
    path('tilgang/<str:side>', views.tilgangSide, name='tilgang'),

    path('turne', views.turneListe, name='turne'),
    path('turne/<kor:kor>/<int:år>/<path:turneNavn>', views.turne, name='turne'),

    path('eksport/<kor:kor>', views.eksport, name='eksport'),

    path('logg', views.loggListe, name='logg'),
    path('logg/<int:loggPK>', views.logg, name='logg'),
    path('logg/loggRedirect/<str:modelName>/<int:instancePK>', views.loggRedirect, name='loggRedirect'),

    path('uploads/<path:path>', views.serve, name='serve'),
    path('docs/', lambda req: FileResponse(open('docs/index.html', 'rb')), name='docs'),

    path('publish/<str:key>', views.publish, name='publish')
] + static(settings.DOCS_URL, document_root=settings.DOCS_ROOT) # Serves direkte av apache på servern
