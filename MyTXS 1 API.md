# MyTxS export-API
## Kort om API-et
- API-et krever en Bearer token for alle kall
- Medlem-delen av API-et tilbyr i utgangspunktet "arkiv"-informasjon om hvert medlem
- Alle medlemmer kan logge inn på internsidene for å eksportere mer informasjon. De genererer da en JWT som er gyldig i to minutter, og som inneholder hvilke data de ønsker å eksportere. Det grunnleggende settet med data kan ikke velges bort.
- Felter som er tomme blir i utgangspunktet ignorert

## Hvordan eksportere mer informasjon
Denne funksjonaliteten bør integreres mot MyTXS 2.0, f.eks. ved at det genereres en lenke som tar deg til MyTXS 2.0 sin import-side med JWT utfylt.
1. Gå til https://mytss.mannskor.no/index.php?cgi_module=export (eller tilsvarende for TKS)
2. Velg de feltene du ønsker å gi tilgang til å eksportere
3. Generer lenke
4. Kopiere JWT i bunn av siden og bruk som verdi for "jwt="-parameteret i GET-forespørselen mot API-et

## Typer
### Medlem
{
  "medlemsnummer": "TSS191018",
  "fornavn": "Fornavn",
  "mellomnavn": "Mellomnavn",
  "etternavn": "Etternavn",
  "stemmegruppe": "2. bass",
  "yrke": "Sanger",
  "arbeidssted": "Trondheim",
  "email": "mail@example.com",
  "boligadresse": "Elgesetergate 1",
  "boligpost": "7030 Trondheim",
  "hjemadresse": "Elgesetergate 1",
  "hjempost": "7030 Trondheim",
  "mobiltlf": "81549300",
  "sluttet": "1920",
  "status": "Sluttet (skal ha vårbrev)",
  "anmerkninger": "Var med i ur-koret",
  "fodselsdag": "1880-01-01",
  "kortnummer": "123456",
  "passfoto": "/9j/4AAQS...",
  "turne": [
    {
      "aar": 1910,
      "turne": "Oslo"
    }
  ],
  "verv": [
    {
      "aar": 1910,
      "verv": "Verv"
    }
  ],
  "dekorasjoner": [
    {
      "aar": 1920,
      "beskrivelse": "Ridder"
    }
  ]
}

## Endepunkter
### TKS
- https://mitks.mannskor.no/api/medlem
    - Tilbyr en liste over alle medlemmer med "arkiv"-informasjon
- https://mitks.mannskor.no/api/medlem/<\d{6}>
    - Tilbyr et enkelt medlem med "arkiv"-informasjon
    - Dersom et "jwt="-parameter sendes med *må* dette være korrekt - det kan da utvide informasjonen som tilbys
### TSS
- https://mytss.mannskor.no/api/medlem
- https://mytss.mannskor.no/api/medlem/<\d{6}>

## API-nøkkel
- Nøkkelen er av type Bearer token

## Eksempelkode
### Hent alle medlemmer i TSS
`curl -H "Authorization: Bearer $API_KEY" https://mytss.mannskor.no/api/medlem`

### Hent et konkret medlem i TSS (arkiv-data)
`curl -H "Authorization: Bearer $API_KEY" https://mytss.mannskor.no/api/medlem/191080`

### Hent et konkret medlem i TKS med utvidet sett av informasjon
`curl -H "Authorization: Bearer $API_KEY" https://mitks.mannskor.no/api/medlem/193080?jwt=$JWT`

## Feilkoder
- HTTP 403, error: NO_AUTH => Du mangler eller har ugyldig API_KEY
    - curl https://mitks.mannskor.no/api/medlem
- HTTP 403, error: INVALID_AUTH => Du sender med en ugyldig (signaturfeil, utgått, ugyldig scope, for feil medlem, etc.) JWT
    - curl -H "Authorization: Bearer $API_KEY" https://mitks.mannskor.no/api/medlem/193080?jwt=
    - curl -H "Authorization: Bearer $API_KEY" https://mitks.mannskor.no/api/medlem/193080?jwt=123
- HTTP 404, error: INVALID_PARAMS => Du etterspør et objekt (for eksempel et medlem) som ikke finnes
   - curl -H "Authorization: Bearer $API_KEY" https://mitks.mannskor.no/api/medlem/193000

