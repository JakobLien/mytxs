import time

from django.core.management.base import BaseCommand
from django.db import connection
from django.test import RequestFactory
from django.urls import resolve

from mytxs.models import Medlem

class Command(BaseCommand):
    help = '''
    Selv bra kode kan skape SQL som er for treig på servern, som e ikke får debugga med DjDT lokalt,
    siden e ikke har samme datamengder lokalt. Følgende kode ble prototypet for å få fiks dette i prod,
    og dette er en generalisering som skal gjøre det enda lettere å jobbe med performance i prod seinar.
    Kan bare mocke get requests, greit det fordi e bryr meg mest om hastigheten av SELECT spørringer.
    '''
    def add_arguments(self, parser):
        parser.add_argument(
            'url',
            help='Quoted url path requesten skal til, kan ha query parameters.'
        )

        parser.add_argument(
            '--medlem', 
            type=int,
            default=2806,
            help='Hvilket medlem som "sendte requesten".'
        )

        parser.add_argument(
            '--sort',
            action='store_true',
            help='Sorer lista fra raskest til tregest heller enn kronologisk.',
        )

    def handle(self, *args, **options):
        queries_log = []

        def query_logger(execute, sql, params, many, context):
            duration = time.perf_counter()
            try:
                return execute(sql, params, many, context)
            finally:
                duration = time.perf_counter() - duration
                queries_log.append((duration, sql))

        with connection.execute_wrapper(query_logger):
            totalTime = time.perf_counter()

            factory = RequestFactory()
            request = factory.get(options['url'])

            request.user = Medlem.objects.filter(pk=options['medlem']).first().user
            request.resolver_match = resolve(request.path)
            request.resolver_match.func(request, *request.resolver_match.args, **request.resolver_match.kwargs)

            totalTime = time.perf_counter() - totalTime

        if options['sort']:
            queries_log.sort(key=lambda d: d[0])

        for duration, sql in queries_log:
            print(f"\t{sql}\n{duration:.4f}s\n")

        print(f'Heile requesten tok {totalTime:.4f}')
