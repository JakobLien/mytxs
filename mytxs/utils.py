

import datetime
from django.db.models import Min, Q, F, Count

# Hadd åpenbart foretrukket en syntax ala Tilgang.objects.filter(verv__vervInnehavelse=vervInnehavelseAktiv), 
# Men verden er ikke så perfekt:/

def vervInnehavelseAktiv(pathToVervInnehavelse='vervInnehavelse'):
    """Produsere et Q object som querye for aktive vervInnehavelser. Siden man 
    ikke kan si Tilganger.objects.filter(verv__vervInnehavelse=Q(...)) er dette en funksjon.

    Argumentet er query lookup pathen til vervInnehavelsene.
    - Om man gir ingen argument anntar den at vi filtrere på Medlem eller Verv (som vi som oftest gjør).
    - Om man gir en tom streng kan vi filterere direkte på VervInnehavelse tabellen
    - Alternativt kan man gi en full path, f.eks. i Tilgang.objects.filter(vervInnehavelseAktiv('verv__vervInnehavelse'))

    Eksempel:
    - Verv.objects.filter(vervInnehavelseAktiv(), vervInnehavelse__medlem__in=medlemmer)
    - Medlem.objects.filter(vervInnehavelseAktiv(), vervInnehavelse__verv__in=verv)
    - VervInnehavelse.objects.filter(vervInnehavelseAktiv(''))
    - Tilgang.objects.filter(vervInnehavelseAktiv('verv__vervInnehavelse'))
    """
    if not pathToVervInnehavelse:
        return (Q(slutt=None) | Q(slutt__gte=datetime.date.today())) & Q(start__lte=datetime.date.today())
    else:
        return ((Q(**{f'{pathToVervInnehavelse}__slutt':None}) |
                Q(**{f'{pathToVervInnehavelse}__slutt__gte':datetime.date.today()})) &
                Q(**{f'{pathToVervInnehavelse}__start__lte':datetime.date.today()}))

def disableForm(form):
    """Disable alle fields i formet (untatt id, for da funke det ikkje på modelformsets)"""
    for name, field in form.fields.items():
        if name != 'id':
            field.disabled = True