from django.urls import path

from . import views

from django.contrib.auth import views as auth_views

from django.contrib import admin

from django.conf import settings

from django.conf.urls.static import static


urlpatterns = [
    path('admin', admin.site.urls, name='admin'),

    path('login', views.loginView, name='login'),
    path('', views.index, name='index'),
    path('sjekkheftet/<str:gruppe>', views.sjekkheftet, name='sjekkheftet'),

    path('medlem', views.medlemListe, name='medlemListe'),
    path('medlem/<int:pk>', views.medlem, name='medlem'),

    path('verv', views.vervListe, name='vervListe'),
    path('verv/<str:kor>/<str:vervNavn>', views.verv, name='verv'),

    path('tilganger', views.tilgangListe, name='tilgangListe'),
    path('tilganger/<str:tilgangNavn>', views.tilgang, name='tilgang'),

    path('dekorasjon', views.dekorasjonListe, name='dekorasjonListe'),
    path('dekorasjon/<str:kor>/<str:dekorasjonNavn>', views.dekorasjon, name='dekorasjon'),

    path('loginEndpoint', views.loginEndpoint, name='loginEndpoint'),
    path('logoutEndpoint', views.logoutEndpoint, name='logoutEndpoint'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)