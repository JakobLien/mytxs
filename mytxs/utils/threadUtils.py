import threading

from django.core import mail
from django.views.debug import ExceptionReporter

def mailException(func):
    'Sende en fint formatert epost te me om det skjer et exception i metoden.'
    def _decorator(*args, **kwargs):
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


def thread(func=None):
    'Lage en thread for funksjonen, og gjør at exceptions der generere eposta'
    def _decorator(*args, **kwargs):
        t = threading.Thread(
            target=mailException(func),
            args=args, 
            kwargs=kwargs,
            daemon=True
        )
        t.start()
        return t
    return _decorator
