from django.db.models import Q

from mytxs.models import Logg, Medlem, Verv
from mytxs.utils.modelUtils import stemmegruppeVerv, vervInnehavelseAktiv


def applyMedlemFilterForm(medlemFilterForm, queryset=Medlem.objects):
    'Filtrere et queryset basert på medlemFilterForm'
    if not medlemFilterForm.is_valid():
        raise Exception('Invalid filterForm')
    
    # Filtrer på kor
    sgVerv = Verv.objects.filter(stemmegruppeVerv(''))
    if kor := medlemFilterForm.cleaned_data['kor']:
        sgVerv = sgVerv.filter(kor=kor)
    
    # Filtrer på karantenekor
    if K := medlemFilterForm.cleaned_data['K']:
        queryset = queryset.annotateKarantenekor(
            kor=kor or None
        )
        queryset = queryset.filter(K=K)
    
    # Filtrer på stemmegruppe
    if stemmegruppe := medlemFilterForm.cleaned_data['stemmegruppe']:
        sgVerv = sgVerv.filter(navn__iendswith=stemmegruppe)

    # Filtrer på dato de hadde dette vervet
    if dato := medlemFilterForm.cleaned_data['dato']:
        queryset = queryset.filter(
            vervInnehavelseAktiv(dato=dato),
            vervInnehavelse__verv__in=sgVerv
        )
    elif kor or stemmegruppe or K:
        # Denne elif-en er nødvendig for å få med folk som ikke har et kor
        queryset = queryset.filter(
            Q(vervInnehavelse__verv__in=sgVerv)
        )

    # Filtrer fullt navn
    if navn := medlemFilterForm.cleaned_data['navn']:
        queryset = queryset.annotateFulltNavn()
        queryset = queryset.filter(fulltNavn__icontains=navn)
    
    return queryset


def applyLoggFilterForm(loggFilterForm, queryset=Logg.objects):
    'Filtrere et queryset basert på loggFilterForm'
    if not loggFilterForm.is_valid():
        raise Exception('Invalid filterForm')
    
    if kor := loggFilterForm.cleaned_data['kor']:
        queryset = queryset.filter(kor=kor)

    if model := loggFilterForm.cleaned_data['model']:
        queryset = queryset.filter(model=model)

    if author := loggFilterForm.cleaned_data['author']:
        queryset = queryset.filter(author=author)

    if pk := loggFilterForm.cleaned_data['pk']:
        queryset = queryset.filter(instancePK=pk)

    if start := loggFilterForm.cleaned_data['start']:
        queryset = queryset.filter(timeStamp__date__gte=start)

    if slutt := loggFilterForm.cleaned_data['slutt']:
        queryset = queryset.filter(timeStamp__date__lte=slutt)

    return queryset
