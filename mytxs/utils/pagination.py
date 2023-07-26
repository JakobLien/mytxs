from django.core.paginator import Paginator, Page
from django.forms import BaseInlineFormSet

# Utils for pagination

def addPaginatorPage(request, pageSize=40):
    paginator = Paginator(request.queryset, pageSize)
    request.paginatorPage = paginator.get_page(request.GET.get('page'))


class PaginatedQueryset(Paginator):
    'Paginator som har get_page som returne et PaginatedPageQueryset'
    def _get_page(self, *args, **kwargs):
        return PaginatedPageQueryset(*args, **kwargs)


class PaginatedPageQueryset(Page):
    'Klasse som e en paginator page og overfladisk ser ut som et queryset også. Funke på formsets hvertfall:)'
    # En fremtidig TODO er å gjøre dette til en klasse som faktisk både er en paginatorPage og et queryset, ved
    # å arve fra begge.
    def __init__(self, object_list, number, paginator):
        super().__init__(object_list, number, paginator)

        self.queryset = object_list
        self.model = object_list.model

    ordered = True
    def get_queryset(self):
        return self.queryset


def getFormsetPaginator(request, queryset, prefix, pageSize=10):
    'Gitt et request med satt request.queryset og url param "page", returne denne en paginator page'
    paginator = PaginatedQueryset(queryset, pageSize)
    return paginator.get_page(request.GET.get(f'{prefix}Page'))


def getPaginatedInlineFormSet(request, pageSize=10):
    '''
    Funksjon som returne PaginatedModelFormSet for dette requestet.
    Bare legg til formset=getPaginatedInlineFormSet(request) i inlineformset_factory, så ordner den alt. 
    Den bruker request for å plukke ut [form.prefix]Page fra urlen for å skaff hvilken side vi er på. 
    '''
    class PaginatedModelFormSet(BaseInlineFormSet):
        '''
        Klasse som override init av BaseInlineFormSet for å ha et queryset som egtl er en paginator.
        
        Alt i __init__ metoden e det samme som i BaseInlineFormset, unntatt at den calle getFormsetPaginator.
        (og selvfølgelig at super ikke kaller init-en til baseInlineFormSet) 
        '''
        def __init__(
            self,
            data=None,
            files=None,
            instance=None,
            save_as_new=False,
            prefix=None,
            queryset=None,
            **kwargs,
        ):
            if instance is None:
                self.instance = self.fk.remote_field.model()
            else:
                self.instance = instance
            self.save_as_new = save_as_new
            if queryset is None:
                queryset = self.model._default_manager
            if self.instance.pk is not None:
                qs = queryset.filter(**{self.fk.name: self.instance})
            else:
                qs = queryset.none()
            self.unique_fields = {self.fk.name}
            
            super(BaseInlineFormSet, self).__init__(data, files, prefix=prefix, queryset=getFormsetPaginator(request, qs, prefix, pageSize=pageSize), **kwargs)

            # Add the generated field to form._meta.fields if it's defined to make
            # sure validation isn't skipped on that field.
            if self.form._meta.fields and self.fk.name not in self.form._meta.fields:
                if isinstance(self.form._meta.fields, tuple):
                    self.form._meta.fields = list(self.form._meta.fields)
                self.form._meta.fields.append(self.fk.name)

    return PaginatedModelFormSet
