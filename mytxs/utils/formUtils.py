# Alt forøverig om forms

formsetArgs = {
    'exclude': [],
    'extra': 1,
    'can_delete_extra': False,
}

def prefixPresent(POST, prefix):
    """
    Utility funksjon for å bare gi POST til modelforms som har relevante keys. 
    Må brukes på sider som har fleire forms for å oppnå korrekt form error handling
    På sider som har bare ett form er 'request.POST or None' akseptabelt
    """
    if any([key.startswith(prefix) for key in POST.keys()]):
        return POST
    else:
        return None
