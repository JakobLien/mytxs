from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path

from mytxs import views


urlpatterns = [
    path('admin', admin.site.urls, name='admin'),

    path('', views.login, name='login'),
    path('logout', views.logout, name='logout'),

    path('registrer/<int:medlemPK>', views.registrer, name='registrer'),

    path('medlem', views.medlemListe, name='medlemListe'),
    path('medlem/<int:medlemPK>', views.medlem, name='medlem'),

    path('endrePassord', views.endrePassord, name='endrePassord'),

    path('sjekkheftet/<str:gruppe>', views.sjekkheftet, name='sjekkheftet'),
    path('sjekkheftet/<str:gruppe>/<str:undergruppe>', views.sjekkheftet, name='sjekkheftet'),

    path('semesterplan/<str:kor>', views.semesterplan, name='semesterplan'),
    path('meldFravær/<int:hendelsePK>', views.meldFravær, name='meldFravær'),
    path('egenFøring/<int:hendelsePK>', views.egenFøring, name='egenFøring'),

    path('lenker', views.lenker, name='lenker'),

    path('dekorasjon', views.dekorasjonListe, name='dekorasjonListe'),
    path('dekorasjon/<str:kor>/<str:dekorasjonNavn>', views.dekorasjon, name='dekorasjon'),

    path('verv', views.vervListe, name='vervListe'),
    path('verv/<str:kor>/<str:vervNavn>', views.verv, name='verv'),

    path('tilganger', views.tilgangListe, name='tilgangListe'),
    path('tilganger/<str:kor>/<str:tilgangNavn>', views.tilgang, name='tilgang'),

    path('logg', views.loggListe, name='loggListe'),
    path('logg/<int:loggPK>', views.logg, name='logg'),

    path('hendelser', views.hendelseListe, name='hendelseListe'),
    path('hendelser/<int:hendelsePK>', views.hendelse, name='hendelse'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
