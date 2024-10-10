from mytxs.forms import addInnstillingerForm

def OptionFormMiddleware(get_response):
    def middleware(request):
        # Om brukeren er innlogget, hiv på optionForm og sjekk for submit
        if request.user.is_authenticated:
            if res := addInnstillingerForm(request):
                return res
        
        return get_response(request)

    return middleware
