from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.shortcuts import redirect

# Utils til bruk i og rundt views

def redirectToInstance(request):
    'Redirecter til request.instance med kwargs fra request.GET, eller bare request.get_full_path'
    if request.instance and hasattr(request.instance, 'get_absolute_url'):
        return redirect(request.instance.get_absolute_url() + '?' + request.GET.urlencode())
    return redirect(request.get_full_path())


def harTilgang(viewFunc=None, querysetModel=None, instanceModel=None, lookupToArgNames=None, loginUseNext=True, extendAccess=None):
    '''
    Decorator som sjekke om brukeren sin navBar dekker denne siden, og at brukeren er logget inn. 
    Om instanceModel passes tilgangsstyrer vi på instansen istedet. 
    
    Ved å passe querysetModel vil vi også kjøre
    `request.queryset = request.user.medlem.sideTilgangQueryset(querysetModel)`

    Ved å passe instanceModel vil vi bruke siste url parameter som pk i instanceModel modellen. 
    Så sjekke vi om instansen finnes, om brukeren har tilgang til instansen, og setter instansen på request.instance

    For å override hvilket arg som mappes til hvilken property for å finne request.instnace, 
    gi en dict som mapper fra lookup path til view argument name, så ordner den det. f.eks. 
    ```
    @harTilgang(instanceModel=Turne, lookupToArgNames={'kor__navn': 'kor', 'start__year': 'år', 'navn': 'turneNavn'})
    ```
    
    extendAccess er en funksjon som tar inn request og returne et queryset av ekstra objekt du får rediger tilgang til 
    gjennom hele dette viewet. Det endre altså på medlemmet, i dette viewet.'''
    
    if not viewFunc:
        # Om vi calle decoratoren, return resten av funksjonen wrapped i en lambda (her må vi passe videre ALLE harTilgang parametersa)
        return lambda func: harTilgang(func, querysetModel=querysetModel, instanceModel=instanceModel, lookupToArgNames=lookupToArgNames, loginUseNext=loginUseNext, extendAccess=extendAccess)

    @login_required(**{'redirect_field_name': None if not loginUseNext else 'next'})
    def _decorator(request, *args, skipDecorator=False, **kwargs):
        if skipDecorator:
            return viewFunc(request, *args, **kwargs)

        # Sjekk om brukeren har tilgang til siden via navBar, om ikke vi skal tilgangsstyre på instanceModel
        if not instanceModel and not request.user.medlem.navBar[request]:
            messages.error(request, f'Du har ikke tilgang til {request.path}')
            return redirect('login')
        
        # Hiv på request.queryset
        if querysetModel:
            request.queryset = request.user.medlem.sideTilgangQueryset(querysetModel).distinct()

        # Hiv på request.instance og tilgangsstyr på den
        if instanceModel:
            if not lookupToArgNames:
                *_, lastArg = request.resolver_match.kwargs.values()
                filterKwargs = {'pk': lastArg}
            else:
                filterKwargs = lookupToArgNames.copy()

                # Gå over values i lookupToArgNames og erstatt med argument fra viewFunc
                for key, value in lookupToArgNames.items():
                    # Om den e i kwargs
                    if value not in request.resolver_match.captured_kwargs:
                        raise Exception('Couldn\'t make filterKwargs from {lookupToArgNames} and {request.resolver_match.captured_kwargs}')
                    
                    filterKwargs[key] = request.resolver_match.captured_kwargs[value]
            
            request.instance = instanceModel.objects.filter(**filterKwargs).first()

            if not request.instance:
                messages.error(request, f'{instanceModel.__name__} med {filterKwargs} ikke funnet')
                return redirect('login')

            if extendAccess:
                # Dette e litt komplisert, men basicly skriv vi en decorator som vi så wrappe rundt redigerTilgangQueryset. 
                # Denne decoratorn hive på extendedQS hver gong redigerTilgangQueryset returne et queryset av den modellen:)
                extendedQS = extendAccess(request)
                def extendedRedigerTilgangQueryset(func):
                    def _decorator(*args, includeExtended=True, **kwargs):
                        returnQS = func(*args, **kwargs)
                        if includeExtended and returnQS.model == extendedQS.model:
                            return returnQS | extendedQS
                        return returnQS
                    return _decorator

                request.user.medlem.redigerTilgangQueryset = extendedRedigerTilgangQueryset(request.user.medlem.redigerTilgangQueryset)

            if not request.user.medlem.sideTilgangQueryset(instanceModel).contains(request.instance):
                messages.error(request, f'Du har ikke tilgang til {request.path}')
                return redirect('login')

        return viewFunc(request, *args, **kwargs)
    
    return _decorator
