from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from mytxs import views

# Alt som skal kunne inkludere slash characteren må være av typen path istedet (og selvfølgelig til slutt i urlen)
# Ja, det e en hacky løsning, men det funke bra så e lar det vær:)

urlpatterns = [
    path('admin', admin.site.urls, name='admin'),

    path("__debug__/", include("debug_toolbar.urls")),

    path('', views.login, name='login'),
    path('logout', views.logout, name='logout'),

    path('registrer/<int:medlemPK>', views.registrer, name='registrer'),
    path('overfør/<str:jwt>', views.overfør, name='overfør'),

    path('medlem', views.medlemListe, name='medlemListe'),
    path('medlem/<int:medlemPK>', views.medlem, name='medlem'),

    path('endrePassord', views.endrePassord, name='endrePassord'),

    path('sjekkheftet/<str:gruppe>', views.sjekkheftet, name='sjekkheftet'),
    path('sjekkheftet/<str:gruppe>/<str:undergruppe>', views.sjekkheftet, name='sjekkheftet'),

    path('semesterplan/<str:kor>', views.semesterplan, name='semesterplan'),
    path('meldFravær/<int:hendelsePK>', views.meldFravær, name='meldFravær'),
    path('egenFøring/<int:hendelsePK>', views.egenFøring, name='egenFøring'),

    path('hendelser', views.hendelseListe, name='hendelseListe'),
    path('hendelser/<int:hendelsePK>', views.hendelse, name='hendelse'),

    path('lenker', views.lenker, name='lenker'),

    path('dekorasjon', views.dekorasjonListe, name='dekorasjonListe'),
    path('dekorasjon/<str:kor>/<path:dekorasjonNavn>', views.dekorasjon, name='dekorasjon'),

    path('verv', views.vervListe, name='vervListe'),
    path('verv/<str:kor>/<path:vervNavn>', views.verv, name='verv'),

    path('tilgang', views.tilgangListe, name='tilgangListe'),
    path('tilgang/<str:kor>/<str:tilgangNavn>', views.tilgang, name='tilgang'),

    path('turne', views.turneListe, name='turneListe'),
    path('turne/<str:kor>/<int:år>/<path:turneNavn>', views.turne, name='turne'),

    path('logg', views.loggListe, name='loggListe'),
    path('logg/<int:loggPK>', views.logg, name='logg'),
    path('logg/loggRedirect/<str:modelName>/<int:instancePK>', views.loggRedirect, name='loggRedirect'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
