import math

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import models

from mytxs import consts

globalOptions = {}

class Command(BaseCommand):
    help = 'seed database for testing and development.'
    
    def add_arguments(self, parser):
        parser.add_argument(
            'updateFunction',
            help='The operation we are applying to the field',
            choices=[f.__name__ for f in updateFunctions]
        )

        parser.add_argument(
            'model', 
            help='The model whose field we wish to update the values of',
            choices=consts.allModelNames
        )

        parser.add_argument(
            'field',
            help='The field on the model we wish to update the values of'
        )

        parser.add_argument(
            '--dontLogg',
            action='store_true',
            help='Don\'t logg changes'
        )
    
    def handle(self, *args, **options):
        model = apps.get_model('mytxs', options['model'])
        fieldName = options['field']
        updateFunction = next(filter(lambda f: f.__name__ == options['updateFunction'], updateFunctions))

        updateFunction(model, fieldName, options=options)

def isStringField(field):
    return isinstance(field, models.TextField) or isinstance(field, models.CharField)

def fieldIsRequired(field):
    if isStringField(field):
        return not field.blank
    return not field.null

def objectsGenerator(model):
    'Generere en stream av objects, og printe prosent av gjennomgang i strømmen.'
    objects = model.objects.all()
    numberOfObjects = len(objects)
    print(f'Number of objects: {numberOfObjects}')

    for i, instance in enumerate(objects):
        if math.floor(i%(numberOfObjects/100)) == 0:
            print(f'{math.floor(i/numberOfObjects*100)}%')
        yield instance

        instance.save()
    print('100%')

def trim(model, fieldName, options):
    'Trim, bare at vi returne ? om det e whitespace'
    field = model._meta.get_field(fieldName)

    if not isStringField(field):
        raise CommandError('Cannot only use Trim on TextField or CharField')
    
    if not fieldName:
        raise CommandError('trim function needs a fieldName')
    
    for instance in objectsGenerator(model):
        value = getattr(instance, fieldName)

        if value.isspace() and fieldIsRequired(field):
            value = '?'
        else:
            value = value.strip()

        if not options.get('dontLogg') and value != getattr(instance, fieldName):
            print(f'Changed {instance} from "{getattr(instance, fieldName)}" to "{value}"')

        setattr(instance, fieldName, value)

def updateStrRep(model, fieldName, options):
    'Oppdatere strRep for denne modellen'
    for instance in objectsGenerator(model):
        pass

updateFunctions = [trim, updateStrRep]
