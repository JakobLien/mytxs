from mytxs.forms import addOptionForm

def OptionFormMiddleware(get_response):
    def middleware(request):
        # Om brukeren er innlogget, hiv på optionForm og sjekk for submit
        if request.user.is_authenticated:
            if res := addOptionForm(request):
                return res
        
        return get_response(request)

    return middleware
