import threading

from mytxs.forms import addInnstillingerForm
from mytxs.utils.threadUtils import THREAD_LOCAL


def OptionFormMiddleware(get_response):
    'Om brukeren er innlogget, hiv på optionForm og sjekk for submit'
    def middleware(request):
        if request.user.is_authenticated:
            if res := addInnstillingerForm(request):
                return res
        
        return get_response(request)

    return middleware


def runThreads(threadQueue):
    'En liten fuksjon som kjøre en liste av threads, en etter en.'
    for thread in threadQueue:
        thread.start()
        thread.join()


def ThreadingMiddleware(get_response):
    'Legg til request og threadQueue i THREAD_LOCAL, og kjør threads i threadQueue en etter en etter responsen e klar.'
    def middleware(request):
        THREAD_LOCAL.request = request
        THREAD_LOCAL.threadQueue = []

        response = get_response(request)

        if THREAD_LOCAL.threadQueue:
            threading.Thread(
                target=runThreads,
                args=[THREAD_LOCAL.threadQueue],
                daemon=True
            ).start()

        del THREAD_LOCAL.request
        del THREAD_LOCAL.threadQueue

        return response
    return middleware
