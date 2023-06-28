import hashlib
import base64
from mytxs.settings import SECRET_KEY

from urllib.parse import unquote

def getHash(path):
    '''
    Tanken her er at om vi hashe pathen sammen med django sin SECRET_KEY, blir det både
    1. Umulig å forutsi hva hashen blir uten secreten
    2. En annerledes hash for hver gang vi treng det, ulik både for 
    instanser og typer objekt (anntar at ulike objekt har ulike paths)

    Dette anntar også at vi bare treng en hash for en url en gong, som e syns e en fair anntagelse. 
    I og med at Django aldri gjennbruke pks, og telle videre opp sjølv om man slette ting, 
    skal det litt til for at vi nån gong treng det fleir gong på en side:)
    '''
    
    # Pass på at reverse og request.path returne det samme
    path = unquote(path)

    # Opprett et sha3 hash
    hashGen = hashlib.sha3_256()

    # Hash inn pathen
    hashGen.update(path.encode('utf-8'))

    # Hash inn django secret key
    hashGen.update(SECRET_KEY.encode('utf-8'))

    # Vi tar 32 characters for å lagre 6**32 muligheter, som e trur e tilstrekkelig for våre formål
    hash = base64.b64encode(hashGen.digest(), altchars=b'-_').decode()[:32]

    return hash

def testHash(request):
    'Returne True om hashen stemme for requesten'
    return request.GET.get('hash', False) == getHash(request.path)
