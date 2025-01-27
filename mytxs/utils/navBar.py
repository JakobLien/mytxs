from django.http.request import HttpRequest
from django.template.defaultfilters import capfirst
from django.urls import reverse

class navBarNode():
    'Representerer en node i navBar hierarkiet'
    
    def __init__(self, parent=None, key=None, inURL=True, isPage=True, defaultParameters=''):
        '''
        key e url arguemnt, parent skal peke på parent om den finnes. inURL indikere om noden skal inngå i urlen, 
        eller bare være en visuel inndeling i navBar. isPage indikere at man kan lande på denne siden direkte, 
        eller den bare skal forwarde til children urler. Merk at om en side har isPage=False vil den automatisk 
        fjernes av generateURLs, dersom den ikke har noen children med isPage=True. defaultParameters hiver på 
        det på enden av denne nodens url, altså ?a=b osv, f.eks. slik at hendelseListe siden bare skal være dagens
        og fremtidige hendelser. 
        '''
        self.children = {}
        self.parent = parent
        self.key = key
        self.inURL = inURL if key else False
        self.isPage = isPage if key else False
        self.defaultParameters = defaultParameters

        if self.parent == self:
            raise Exception('Can\'t have self as parent!')

        if self.parent:
            self.parent.children[key] = self


    def __getitem__(self, path, includeNotInURL=False):
        'Finn noden tilsvarende et request, en path eller liste av argument, None betyr mangel på tilgang'
        if isinstance(path, HttpRequest):
            path = (path.resolver_match.url_name, *path.resolver_match.captured_kwargs.values())
            includeNotInURL = True
        elif isinstance(path, str):
            if'/' in path:
                path = path.split('/')
            else:
                path = (path,)
            includeNotInURL = True

        if path:
            if nextChild := self.children.get(path[0]):
                return nextChild.__getitem__(path[1:], includeNotInURL=includeNotInURL)
            elif includeNotInURL:
                childrenNotInURL = list(filter(lambda child: not child.inURL,  self.children.values()))
                for child in childrenNotInURL:
                    if childRes := child.__getitem__(path, includeNotInURL=includeNotInURL):
                        return childRes
            return None
        return self


    def addChildren(self, *childKeys, **kwargs):
        for childKey in childKeys:
            navBarNode(self, key=childKey, **kwargs)


    def getPath(self, hideNotInURL=False) -> list:
        'Skaff pathen til denne pagen som en liste'
        if not self.parent:
            return [self.key] if not hideNotInURL or self.inURL else []
        return self.parent.getPath(hideNotInURL) + ([self.key] if not hideNotInURL or self.inURL else [])


    def buildNavigation(self, activeChild=None):
        returnStr = ''

        if self.parent and self.parent.key != None:
            returnStr = self.parent.buildNavigation(activeChild=self)

        returnStr += '<div class="mb-2 w-auto overflow-x-auto -mx-4 px-4 overflow-y-hidden whitespace-nowrap relative">'
        for child in self.children.values():
            if child == activeChild:
                returnStr += f'<a class="font-semibold bg-txsPurple200 px-1 py-0.5 text-txsWhite" href="{child.url}">{capfirst(child.key)}</a> '
            else:
                returnStr += f'<a class="bg-txsGray300 px-1 py-0.5 mb-6" href="{child.url}">{capfirst(child.key)}</a> '
        if self.children:
            returnStr += '</div>'


        return returnStr


    def generateURLs(self, urlSoFar=[]):
        'Generere urla til alle, og dermed validere at alle URLer finnes'
        for child in list(self.children.values()): # list() e nødvendig
            child.generateURLs(urlSoFar=urlSoFar + ([child.key] if child.inURL else []))
        
        if self.isPage:
            self.url = reverse(urlSoFar[0], args=urlSoFar[1:] if len(urlSoFar) > 1 else None) + self.defaultParameters
        else:
            child = next(iter(self.children.values()), None)
            if child and (url := getattr(child, 'url', None)):
                self.url = url
            if not hasattr(self, 'url'):
                del self.parent.children[self.key]
