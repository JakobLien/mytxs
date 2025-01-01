import sys
import threading

from mytxs import settings

from django.core import mail
from django.views.debug import ExceptionReporter


def mailException(func):
    'Decorator som sende en fint formatert epost te me om det skjer et exception i metoden.'
    def _decorator(*args, **kwargs):
        if settings.DEBUG:
            # Ikkje mail exceptions i development, bare på servern
            return func(*args, **kwargs)

        try:
            return func(*args, **kwargs)
        except Exception as exception:
            reporter = ExceptionReporter(None, type(exception), exception, exception.__traceback__, is_email=True)
            mail.mail_admins(
                subject='Threaded exception', 
                message=reporter.get_traceback_text(),
                html_message=reporter.get_traceback_html()
            )
    return _decorator


THREAD_LOCAL = threading.local()
def thread(func=None):
    '''
    Decorator som threade funksjonen, og gjør at exceptions inni der generere eposta. 

    Om vi e i en request legg vi thread objektet til i threadQueue heller enn å start den umiddelbart. 
    ThreadingMiddleware kjøre så disse threadsa en etter en etter å ha svart på requesten. 
    Dette medføre at når databasearbeid threades e ikkje databasen i en konsekvent tilstand i 
    responsen. Dette e verdt det for å unngå å ha enkelte requests som tar mang titalls sekund. 

    Her har vi også et unntak for testing, fordi hver thread vil ha en egen connection til test 
    databasen, så et sekund etter når django prøve å slett test databasen vil vi få et exception. 
    Vil åpenbart helst unngå unntak for testing, men e ser ikkje en grei måte å gjør det på akk no. 
    '''
    def _decorator(*args, **kwargs):
        if 'test' in sys.argv:
            return func(*args, **kwargs)

        thread = threading.Thread(
            target=mailException(func),
            args=args, 
            kwargs=kwargs,
            daemon=True
        )

        # Threads fra requests kjøre en etter en etter å ha svart på requesten
        threadQueue = getattr(THREAD_LOCAL, 'threadQueue', None)
        if threadQueue != None:
            threadQueue.append(thread)
        else:
            thread.start()
            return thread
    return _decorator
