from django.urls import path

from . import views

from django.contrib.auth import views as auth_views

from django.contrib import admin

from django.conf import settings

from django.conf.urls.static import static


urlpatterns = [
    path('admin', admin.site.urls, name='admin'),

    path('', views.login, name='login'),
    path('logout', views.logout, name='logout'),

    path('registrer/<int:medlemPK>', views.registrer, name='registrer'),

    path('medlem', views.medlemListe, name='medlemListe'),
    path('medlem/<int:pk>', views.medlem, name='medlem'),

    path('endrePassord', views.endrePassord, name='endrePassord'),

    path('sjekkheftet', views.sjekkheftet, name='sjekkheftet'),
    path('sjekkheftet/<str:gruppe>', views.sjekkheftet, name='sjekkheftet'),

    path('dekorasjon', views.dekorasjonListe, name='dekorasjonListe'),
    path('dekorasjon/<str:kor>/<str:dekorasjonNavn>', views.dekorasjon, name='dekorasjon'),

    path('verv', views.vervListe, name='vervListe'),
    path('verv/<str:kor>/<str:vervNavn>', views.verv, name='verv'),

    path('tilganger', views.tilgangListe, name='tilgangListe'),
    path('tilganger/<str:kor>/<str:tilgangNavn>', views.tilgang, name='tilgang'),

    path('logg', views.loggListe, name='loggListe'),
    path('logg/<int:pk>', views.logg, name='logg'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)