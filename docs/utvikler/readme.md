# Utvikler dokumentasjon
Denne dokumentasjonen er tiltenkt utviklere av MyTXS, kodebasen finnes [her](https://github.com/JakobLien/mytxs). Også for denne anbefales det å lese [bruker](../bruker/readme.md) og [admin](../admin/readme.md) dokumentasjonen, men man kan fint skumlese de. 

For mer om hvordan denne dokumentasjonen er publisert, se [her](./dokumentasjon.md). 


## Hvordan bidra?
MyTXS ble ikke bare skrevet for å fungere, men også for å være mulig å endre på. Fra starten har det vært et mål å bygge opp en levende utviklingsgruppe rundt prosjektet. For å holde denne gruppa i gang er det tenkt å ha ukentlige utviklingsmøter. For å bidra trenger man ikke særlig my meir forkunnskaper enn noe som tilsvarer ITGK. Det viktigste er utansett å være gira og å sette av tid til å holde det gående. Her er hvordan nye medlemmer kommer inn på prosjektet:
- Meld din interesse til [Jakob Lien](https://mytxs.samfundet.no/sjekkheftet/TSS#m_2806), så han vet å ta deg med i prosessen! Jakob er veldig behjelpelig med hva enn på prosjektet, og vi ønsker alltid å være flere!
- Få satt opp prosjektet som beskrevet [under oppsett](#oppsett).
- Jobb deg gjennom [django tutorialen](https://docs.djangoproject.com/en/4.2/intro/), for å få en viss kjennskap til rammeverket. Det finnes sinnsynkt mye mer i django enn det som dekkes av tutorialen, men den er en overraskende god introduksjon til det man absolutt må vite om. 
- Se på [github issues](https://github.com/JakobLien/mytxs/issues) etter arbeidsoppgaver du kunne tenkt deg gå løs på. I skrivende stund lever brorparten av beskrivelsen av prosjektet og arbeidsoppgaver i mine private notater, men som med alt annet hjelper jeg deg gjerne å finne ut av det. Jeg skal prøve å få flyttet over flere issues på github snart™.


## Oppsett
Her er hvordan man setter opp nettsiden lokalt. Om du ikke har erfaring med progging kan jeg anbefale [VS Code](https://code.visualstudio.com/) som editor, den e heilt grei. 
1. Når du er der du vil ha repoet, clone repoet med `git clone https://github.com/JakobLien/mytxs.git`. 
1. Installer [Python](https://www.python.org/downloads/), helst versjon 3.11 slik som kjøre på servern. 
    - Koden burde kjøre fint med høyere python versjoner også, men da er det lett å introdusere syntax som ikke støttes av python versjonen på serveren, hvilket er kjipt. 
1. Installer [PostgreSQL](https://www.postgresql.org/download/), og få satt opp en enkel database med [default credentials](#postgres-default-credentials). Om du bruker andre credentials, noter det til sendere. Bruk helst versjon 15, men høyere burde også gå fint. 
    - For Mac anbefales sterkt [Postgres.app](https://postgresapp.com/), den bare fungerer og er dritdigg. 
    - For Ubuntu ser det ut som at libpq-dev også er nødvendig. 
    - Om du slit **veldig** med å installer og få opp Postgres lokalt, kan du også sett det opp via [Supabase](https://supabase.com/) gratis, men da vil enhver databasespørring gå over nettverket. Da kan du ikke utvikle uten nett, og alle databasekall vil vær unødvendig treige for deg, så helst ikkje gjør dette. 
1. Opprett et [venv](https://docs.python.org/3/library/venv.html) med navn `venv` gjennom `python -m venv venv`, og aktiver venvet med kommandoen `venv\Scripts\activate` på Windows eller `source venv/bin/activate` på Mac eller Linux. 
    - Aktivering av venvet må sannsynligvis gjøres hver gang du åpner VS Code. 
    - Venv er kort for Virtual Environment, og er at alle pakkene installeres sammen med koden din. Dette gjør det enklere å sikre at man har rett versjon av alle pakker, uavhengig av versjonene andre python prosjekt på maskinen din bruker. 
1. Kjør `python -m pip install -r requirements.txt` for å installer rett versjon av alle python pakker i venvet, slik som står oppført i `requirements.txt`. 
1. Generer en Django-nøkkel, for eksempel [her](https://djecrety.ir/), og sett den for prosjektet i en [.env fil i rot](../../.env) med `DJANGO_SECRET=<nøkkel>`. Sett også `DJANGO_DEBUG=True`. 
    - Om du *ikke* brukte [postgres default credentials](#postgres-default-credentials) må du definer dem her. 
1. Utfør db-migrasjoner med `python manage.py migrate`. Dette oppretter alle tabeller du treng i den lokale databasen din. 
1. Seed den lokale databasen med `python manage.py seed --adminAdmin`. Dette oppretter en bruker med brukernavn og passord `admin`. 
    - For å ha litt data å jobbe med, kan du legge til argumentet `--testData`. Dette vil opprette medlemmer fra 2010 og utover, i både storkor og småkor, verv, dekorasjoner, hendelser, korledere og dirigenter. 
1. Kjør servern med `python manage.py runserver`. Den burde nå bli tilgjengelig på [localhost](http://127.0.0.1:8000). 


### Postgres
Vi kan ikke bruk [sqlite](https://sqlite.org/) til utvikling, blant annet fordi [django jsonField](https://docs.djangoproject.com/en/4.2/ref/models/fields/#django.db.models.JSONField) ikkje støtte det. Heller enn å prøve å installere [django extentionen](https://docs.djangoproject.com/en/4.2/ref/databases/#sqlite-json1) som støtter det anbefaler jeg derfor å bare installere postgres så det blir samme database oppsett som prod. [settings.py](../../mytxs/settings.py) er satt opp til koble til med [default postgres credentials](postgres-default-credentials), men dette kan endres på. 
- Om du under utvikling får feilmelding om at postgres allerede kjøre på port 5432, fungere det for meg på på Mac kjøre `sudo pkill -u postgres`. 
- For å dropp all data i databasen (lokalt selvfølgelig), kjør (i psql shell, `python manage.py dbshell`):

    DROP SCHEMA public CASCADE;
    CREATE SCHEMA public;


#### Postgres default credentials
Disse er formatert så du kan kopiere og lime de inn i en [.env fil i rota](../../.env). Disse er default for postgres, så du burde ikkje treng å legg inn dette om du ikkje tenke å bruk andre credentials. 

    DATABASE_ENGINE=django.db.backends.postgresql
    DATABASE_NAME=postgres
    DATABASE_USER=postgres
    DATABASE_PASSWORD=postgrespassword
    DATABASE_HOST=localhost
    DATABASE_PORT=5432


### Overordnet struktur
Her følger en rask oversikt av hvordan kodebasen henger sammen. Med innsikt i dette kan en lære å følge koden fra et request kommer inn til respons kommer ut, hvilket muliggjør å lese seg opp på nøyaktig hvordan alt fungerer. 
1. Innkommende requests routes i [urls.py](../../mytxs/urls.py), som sender de til en view i [views.py](../../mytxs/views.py).
1. I [views.py](../../mytxs/views.py) kjører faktisk python kode. Her kan vi kjøre queries på databasen, som har struktur definert i [models.py](../../mytxs/models.py), før dataen gis videre til en html template i [templates mappa](../../mytxs/templates/mytxs).
1. I templates mappa definere vi hvordan dataen skal vises med html. 
    - Templates refererer også til statiske filer (bilder, css og js) fra [static mappa](../../mytxs/static/mytxs). Styling er gjort med [Tailwind](#tailwind). 
    - Sånn ca alle templates arve fra [base.html](../../mytxs/templates/mytxs/base.html), da denne definerer header, navbar, popup og innstillinger. 
    - Nesten alle templates arver fra [instance.html](../../mytxs/templates/mytxs/instance.html) eller [instanceListe.html](../../mytxs/templates/mytxs/instanceListe.html), som har generel logikk for både individuelle ting og lister av ting. 
1. På clientside har vi noen små javascript filer, som skal gjøre siden mere brukervennlig, og gjøre det vanskeligere å gjøre feil:
    - [formSafety.js](../../mytxs/static/mytxs/formSafety.js) gir mere brukervenlige forms ved å markere endringer visuelt, ta en popup bekreftelse før endringer lagres og lignende. 
    - [searchDropdown.js](../../mytxs/static/mytxs/searchDropdown.js) gir søkbare og mere brukervennlige select menyer over hele siden. 
    - [lazyDropdown.js](../../mytxs/utils/lazyDropdown.py) gjør at flere dropdown menyer som har flere like alternativ laster inn en felles gang etter innlasting, med litt hjelp fra serveren. Dette er f.eks. nødvendig på verv, der vi har flere dropdownmenyer med potensielt tusenvis av medlemmer. 
1. Forøverig har vi:
    - [signals](../../mytxs/signals) som fikser på [filopplastninger](../../mytxs/signals/fileSignals.py) og [logging av endringer](../../mytxs/signals/logSignals.py). 
    - [management commands](/Users/jakoblien/Desktop/mytxs/mytxs/management/commands) der vi definerer ekstra konsoll kommandoer som [seed](../../mytxs/management/commands/seed.py), [slettGamleOppmøter](../../mytxs/management/commands/slettGamleOppmøter.py) og [cron](../../mytxs/management/commands/cron.py). 
    - [forms.py](../../mytxs/forms.py), [fields.py](../../mytxs/fields.py) og [utils mappa](../../mytxs/utils) som definerer forms, felt (både form og model nivå) og diverse utilities. 
    - [templateTags.py](../../mytxs/templateTags.py) som definerer ekstra [template tags](https://docs.djangoproject.com/en/4.2/ref/templates/builtins/) vi kan bruke. 
    - [consts.py](../../mytxs/consts.py) der vi definerer diverse konstanter for prosjektet, blant annet navnene på korene, hvilke tilganger som finnes og annet vi ikke vil ha spredt over hele kodebasen med skrivefeil (tihi). 


## Medlemsregisteret og tilgangsstyring
Medlemsregisteret består av flere modeller, men disse 4 er de viktigste:
- Medlem representerer et medlem/en person. De har gjerne et medlemsnummer for å knyttes opp mot den gamle siden, potensielt en bruker, et navn og potensielt diverse data på seg. 
- Verv representerer et verv i et kor. Dette er også hvordan vi representerer dirigenter, stemmegrupper og permisjon. 
- VervInnehavelse representerer at noen har et verv i en periode. VervInnehavelse har, i tillegg til foreignkey til Medlem og Verv, start og nullable slutt dato, hvilket systemet tolker som at de aldri slutter i vervet. 
- Tilgang har en mange til mange relasjon til Verv, og representerer noe de kan gjøre (bruktIKode), eller en logisk gruppe med verv (ikke bruktIKode).  Medlemmer får tilganger av at de har en aktiv VervInnehavelse til et Verv som har den tilgangen. 

Tilganger som lar deg gjøre noe nytt er bruktIKode™, hvilket vil si at navnet på denne tilgangen sjekkes av koden. Følgelig kan ikke slike tilganger slettes, opprettes eller endres navn på. Verv kan også være bruktIKode. Dette gjelder foreløpig verv ved navn `Dirigent`, `ukjentStemmegruppe` og faktiske stemmegrupper som `1T`, `2B` og `22B`. Dette er altså hvordan vi representerer at man er aktiv i korene, du har et stemmegruppe-verv i den perioden du sang den stemmegruppen. 

Grunnet hvor dårlig struktur det var på det gamle medlemsregisteret måtte jeg fikse på ganske mye data under overføring. Dette involverte også en god del graving i dataen for å forstå hvordan jeg best kunne representere den på det nye databaseformatet. Koden som konverterte fra gammelt til nytt dataformat kan du lese i [transfer.py](../../mytxs/management/commands/transfer.py). Denne koden kan være en god kilde til forståelse for medlemsregisteret. 

Vi tilgangsstyrer både på at en har tilgang til å redigere noe, samtidig som vi tilgangsstyrer at en har tilgang til en side. Generelt har en tilgang til en side når enn en har tilgang til å redigere noe på den siden, f.eks. må alle med `TSS-vervInnehavelse` tilgangen ha tilgang til medlemmer i TSS sine sider, og verv i TSS sine sider, siden det er der de faktisk kan bruke tilgangen sin. I tillegg til denne queryset representasjonen av hva man har tilgang til, finnes det også en eksplisit representasjon av individuelle sider ikke assosiert med databaseobjekt i [navBar](../../mytxs/utils/navBar.py) metoden på medlemmet. Virke komplisert, og tilgangsstyring er det, men det burde generelt fungere uten endringer for det meste vi legger til herifra. 


## Semesterplan og fravær
Vi har 2 modeller for semesterplan og fravær:
- Hendelse representerer noe som er i noens kalender. Vi har fire typer hendelser:
    - Oblig: Fraværsføring, folk søker fravær om de ikke kommer.
    - Påmelding: Folk kan melde fra om de kommer eller ikke. 
    - Frivillig: Uten føring av fravær eller melding om de kommer. 
    - Undergruppe: For ting som bare noen få korister skal på, f.eks. jobbvakter. 
- Oppmøte representerer noen som potensielt drar på den hendelsen. Et oppmøte har
    - Fravær: Antall minutter fravær på hendelsen. Null betyr ikke møtt. Dette valideres begge veier med varigheten av hendelsen, så man ikke kan ha mer fravær enn varigheten av hendelsen. 
    - Gyldig: Om eventuelt fravær er gyldig eller ugyldig. 
    - Ankomst: Koristens kortsvar, en av `Kommer`, `Kommer kanskje` eller `Kommer ikke`. 
    - Melding: Fritekstfelt der både koristen og fraværsfører kan notere til hverandre. 

I motsetning til Oblig og Påmelding hendelser som har oppmøter for alle aktive i koret på den dagen som ikke har permisjon, har Undergruppe hendelser har kun oppmøter for de som skal komme på de. Hvem som skal på undergruppehendelsen kan velges på hendelsen sin redigerings side i en dropdown meny. Man kan også i firkantparentes foran navnet på Hendelsen skrive navnet på en tilgang, og da vil de som har den tilgangen i det koret bli lagt til automatisk når hendelsen lagres, f.eks. `[Styret]`. Om man skriver hashtag antall, f.eks. `[#3]`, vil opptil så mange kunne melde seg på hendelsen fra 'Jobbvakter' siden. 

Hver korist har en kalender for hvert kor de er aktive i. Altså vil alle småkorister ha to ulike kalendere, en for storkor, og en for småkor. Sangern kan kun opprette Frivillig og Undergruppe hendelser, som havner i storkor sine kalendere. 

Vi har iCal eksport, slik at korister kan få semesterplan inn i kalenderapplikasjonen sin. En utfordringen med dette er at veldig mange bruker Google Calendar, og Google Calendar nekter oppdatere seg oftere enn en gang pr dag, potensielt skjeldnere. For å komme forbi dette må man gå via Google Calendar sin API, opprette kalendere, og selv endre de når noe endres. En utfordringen med dette er at i MyTXS, blant eksempel på grunn av Undergruppe hendelser, er kalendere unike til medlemmet, altså finnes det 80 ulike kalendere for TSS. Derfor oppretter MyTXS opptil ish 240 individuelle kalendere i Google Calendar, som så deles med hver korist. Disse er basert på iCal eksport koden, slik at videre utvikling bare burde trenge å endre på den, også vil resultatet havne begge steder, se [her](../../mytxs/utils/googleCalendar.py). I tilfelle endringer i Google Calendar grunnet en feil ikke blir oppdatert, har vi også et [script](../../mytxs/management/commands/fixGoogleCalendar.py) som kjøres hver time av cron.py, som går over alle sine kalendere og fikser det som ikke stemmer. 


## Logging
Vi har 2 modeller for logging:
- Logg som inneholder pk, model, tidspunkt, author osv, og et jsonfelt som har en json representasjon av objektet. I jsonfeltet representeres foreign key felt som pk av den nyeste loggen av det relaterte objektet, hvilket muliggjør navigering mellom ulike logger. 
- LoggM2M som representerer mange til mange relasjoner mellom objekter. 

[logSignals.py](../../mytxs/signals/logSignals.py) er ansvarlig for å generere logg objektene for ting som skjer, signal basert. Her får vi inn forfatteren av endringen via THREAD_LOCAL, se [Threading](#threading). Merk også at logger opprettes kun når noe av loggen faktisk har endret seg, for å unngå unødvendige logger ala "Bob endret ingenting på dette tidspunktet". 

Grunnen til at vi ikke har LoggM2M som del av Logg er fordi m2m relasjoner kan endres på begge sider, og om vi lagre verv -> tilgang informasjonen på vervet som en liste, hvilket er mulig, blir det veldig mange logger av at man endrer fra tilgang siden, og mindre oversiktlig hva som faktisk ble endret. Slik det er nå kan man med stor sikkerhet si at "dersom vi har en logg på den modellen, er det den modellen sitt modelform som ble endret" (Det er også kodemessig enklere å gjøre det som en separat tabel.)

For å unngå å lage loggs på ting folk skal kunne endre selv, og ikke minst slette selv, unngår loggene å lagre noe av dataen fra Medlem modellen med unntak av navnet deres. Slik sikrer vi at om en bruker går inn og sletter dataen sin, er den faktisk slettet, veldig greit for personvernet. 


## Infrastruktur
Her følger en beskrivelse av infrastrukturen vi har byggd for å gjøre prosjektet mere bærekraftig. Dette er ting som brukere og adminer på nettsiden har noe som helst forhold til. 


### Tailwind
Les om tailwind [her](https://tailwindcss.com/). For å få tailwind i django bruker vi [pytailwindcss](https://github.com/timonweb/pytailwindcss), ikke [django-tailwind](https://github.com/timonweb/django-tailwind), fordi sistnevnte virket herk å sette opp. Ved å commite [styles.css](../../mytxs/static/mytxs/styles.css) fila slipper vi å styre med tailwind på serveren. For å kjøre tailwind automatisk på endring av relevante filer, åpne 2 terminaler og kjør henholdsvis
1. `python manage.py runserver`
1. `tailwindcss --cwd mytxs -i static/mytxs/inputStyles.css -o static/mytxs/styles.css --minify --watch`

Da vil [styles.css](../../mytxs/static/mytxs/styles.css) oppdateres så fort du endre noe i hvilken som helst html eller js fil! Husk å commit styles.css slik at vi slipper å styre med Tailwind på ITK servern. 

For å få hjelp når du skriv tailwind anbefales virkelig [Tailwind CSS IntelliSense](vscode:extension/bradlc.vscode-tailwindcss) utvidelsen til VS Code. Det e lett å sett opp at det funke med css og html i templates, men for å få det te å også funk der vi bruke det i javascript, hiv på disse snippetsa i din VS Code sin settings.json. 

    "tailwindCSS.experimental.classRegex": [
        ["[Ss]tyles?([^;]*);", "[\"'`]([^\"'`\\n]*)[\"'`]"], //Match alle strings mellom style og semikolon
        [".classList([^;]*);", "[\"'`]([^\"'`\\n]*)[\"'`]"] //Match alle strings mellom .classList og semikolon
    ],


### Cron jobs
Opprettet vårt av cron jobs e ganske enkelt, men fungere flott! På sørvern kjøres kommandoen `python manage.py cron` hvert minutt, slik at i koden i [cron.py](../../mytxs/management/commands/cron.py) kan vi utviklera skriv kode som gjør i stor grad ka som helst, uten å måtta hør med ITK om å få opp en egen cron kommando for det. Cron koden skal ellers vær ganske selvforklarende. Pr no har vi 2 cron jobs:
- [fraværEpost](../../mytxs/management/commands/cron.py), som sende epost te folk med fravær tilgangen 2 tima før øvelse. 
- [fixGoogleCalendar](../../mytxs/management/commands/fixGoogleCalendar.py), som fikse opp i folk sine google calendars en gong i timen. 


### Threading
I [threadUtils.py](../../mytxs/utils/viewUtils.py) defineres det 2 nyttige decorators, til å sette foran funksjoner vi ikke ønsker at brukeren skal måtte vente på. 
- [thread](../../mytxs/utils/threadUtils.py#L35) er en relativt sammensatt funksjon, som skal håndtere kodens behov for å gjøre ting utenfor request syklusen, mest av performance grunner. Samtidig ønske vi ikkje at fleir threads ska jobb med databasen samtidig, da det kan lede til feil. Derfor legg vi heller inn threads som kommer av et request inn i `THREAD_LOCAL.threadQueue`. Så kommer [Threading Middleware](../../mytxs/middleware.py) og starter threads generert av et request, en etter en, **etter** requesten er svart på. Dette gir oss god performance (fra brukerens perspektiv) sida servern svare fortar, og gjør threading lett å jobb med for oss. 
    - For [cron jobs](#cron-jobs) har vi ikkje et request å skulla start ting etter. Følgelig vil funksjoner som threades her kjøre med en gang. 
    - I testing ønske vi ikkje å thread ting, ettersom django prøve å slett test_databasen så fort vi e ferdig, og det kan da fortsatt vær aktive threads som held database connections. Derfor kjøre vi det heller bare sekvensielt da. 
- [mailException](../../mytxs/utils/threadUtils.py#L13) brukes både med threading og med [cron jobs](../../mytxs/management/commands/cron.py), for å generere en epost til `settings.ADMINS` når noe går galt, da Django kun håndterer dette innad den vanlige request syklusen. 

`THREAD_LOCAL` importeres her og der, og er nyttig fordi Django i utgangspunktet er single-threaded. Derfor kan vi her lagre data uten å måtta send det rundt som argument overalt, se [stackoverflow](https://stackoverflow.com/a/64216681/6709450). I middleware sett vi request objektet og en tom threadQueue liste på objektet, så bli det en trygg anntakelse at dersom disse finnes e vi i en request. 

Her vil e også kom med en oppfordring: Det e lett å tenk at økt performance e bare bra, men threading på denne måten e et mektig verktøy som øke kompleksitet, hvilket e [dårlig](https://grugbrain.dev/#grug-on-complexity). Når en ønsker å bruke dette, vurder følgende:
- Sida threaden kjøre etter responsen e generert kjem den neste responsen til å kunna vær feil/utdatert. For ting som relaterte objekts [dbCache](#dbcache) e dette et godt offer, fordi fiksing av dem kan ta mange titalls sekund, f.eks. ved endring av et medlems navn som så må oppdatere streng representasjonen (`__str__`) til hundrevis av oppmøter. 
- Sida testan e satt opp slik no at i testa kjøre "threads" underveis mens i prod kjøre threads etter requesten, prøv å unngå å thread kode som kan gi forskjellig resultat basert på rekkefølgen av det som skal threades, og resten av request håndteringa. 
- Python er generelt mer enn rask nok så leng vi ikke gjør nå dumt. 


### dbCache
dbCache er en mekanisme for å kunne cache "dyre" operasjoner i databasen, ved å lagre resultatet av operasjonen sammen med den assosierte dataen. For å bruke de, bare hiv på en metode som gjør operasjonen, og annotate den med [DBCache decoratoren](../../mytxs/utils/modelCacheUtils.py). Da vil metoden kalles før (i utgangspunktet) enhver lagring av objektet, og resultatet vil lagres i et jsonfield i databasen. dbCache støtter også "paths" på databasenivå, både til relaterte objekt og til felt på objekt, som sie at den kun ska kjør på nytt når en av disse har endret seg. Altså, idet vi endre navn på et verv, vil den få igang endring av alle relaterte vervInnehavelser, på en generalliserbar måte. 

Her følge en gjennomgang av kor vi har brukt dette.  
- `__str__` var hovedårsaken til at jeg lagde denne abstraksjonen. Denne levde ganske lenge på feltet `strRep`, men ble fjernet i starten av 2024 til fordel for dbCache som en mer generell abstraksjon. 
    - Grunnen til at vi ønsker å lagre streng representasjonen direkte er at den veldig ofte avhenger av andre objekter, f.eks. er VervInnehavleser typ `VervInnehavelse Jakob Lien -> Sekretær`. Når vi skal laste inn en liste ting vil django i utgangspunktet calle `__str__` på hvert av objektene, hvilket gir lineært antall databasekall, hvilket er dårlig. 
    - Okei, men koffor lagre vi ikkje bare hvilket kor det e som tekst eller index på objektet, koffor e det sin egen tabell? Fordi vi ønske å bruk Django sin ORM for å joine fra tilgang til kor til verv osv osv, det er mye diggere å kunne gjøre slikt. 
    - Ja, e bryr me kanskje litt mye om korrekthet, men meir korrekt bli meir bærekraftig syns e. 
- Vi cache koordinatan te adressan te folk til visning i [kart visninga i sjekkheftet](https://mytxs.samfundet.no/sjekkheftet/kart). Tidligar her gjor nettlesern et kall til kartverket for hver person som hadd synlig adresse, for hver innlastning av den siden. Mens dette va en kul animasjon, e det fint å unngå å spamme dem. 
- På medlem cache vi også storkor navn, for å kunna gjør enkle ting som å lenke te rett sjekkhefte uten å måtta gjør et ekstra databaseoppslag. Det å ikkje lagre storkor direkte på medlemmet e irriterende, inntil e fikk sammen dette systemet, og da vart det plutselig veldig digg for korrektheten. 


## Publisering
Merk at man må få tilgang av ITK til mytxs mappen på sørveren for å kunne publisere. Stikk innom de i løpet av deres [åpningstider](https://itk.samfundet.no/), så er de veldig behjelpelige med hva enn det skulle være:) Når det er gjort, og du har endringer som skal publiseres, er fremgangsmåten som følger. Lokalt:
1. Kjør `python manage.py makemigrations` for å lag migrasjonsfiler for model-endringene du har gjort. Ikke gjør model-endringer uten grunn, tenk gjennom endringene du gjør. 
1. Oppdater tailwind dokumentasjonen med følgende kommandoer, uten `--watch` flagget:
    - Om du har endret på tailwind for MyTXS, se [her](#tailwind). 
    - Om du har endret på dokumentasjons generatoren, se [her](./dokumentasjon.md#bygging). 
1. Kjør `python manage.py test`, for å sjekke at endringen din ikke har ødelagt noe, ihvertfall ikke på en måte som er veldig lett å finne ut av. 
1. Skriv `python -m pip freeze > requirements.txt` for å lagre i `requirements.txt` hvilken versjon av alle bibliotekene du bruker. 
    - Pass på å ikke endre versjon av biblioteker uten grunn, og dersom du gjør det uintensjonelt, fiks det før du pushe. >:(
1. Bruk git for å få endringene inn i main på github, gjerne via merge request, om prosjektet noen gang kommer så langt som å ha flere som jobber på det og kan se over hverandres kode hehe. 

Mot servern:
1. Gå på [vpn.samfundet.no](http://vpn.samfundet.no) og last ned wireguard. Dette er samfundet sin VPN, som sikrer at trafikken din ihvertfall kommer fram til huset. Dette er åpenbart ikke nødvendig om man er på husets nett, og er potensielt ikke nødvendig ellers, men det måtte noen ganger til for meg ihvertfall. 
1. Åpne en terminal og skriv `ssh <brukernavn>@login.samfundet.no`, der du erstatter brukernavnet med ditt samfundet brukernavn. 
    - Her vil jeg gripe muligheten til å sterkt anbefale VSCode extentionen [Remote Explorer](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-ssh), som lar deg bruke VSCode gjennom SSH, fantastisk nyttig om man ikke er en Linux guru. 
1. Skriv `cd ../felles/web/mytxs` for å navigere inn i kodebasen. 
1. Skriv `git pull` for å hente alle de nyeste endringene. 
    - Minimer kompleksitet: Hold severn på main, ikkje commit ting direkte på servern osv. 
1. Aktiver [venvet](#oppsett), [installer rett versjon av bibliotek](#oppsett) om nødvendig, og [migrer databasen](#oppsett) om nødvendig. 
1. Skriv `python manage.py collectstatic` for å samle [statiske filer](https://docs.djangoproject.com/en/4.2/ref/contrib/staticfiles) (fra [static mappa](../../mytxs/static)) til der serveren vil serve de fra.
1. Den skal automatisk laste inn på nytt når filer har endret seg, om ikke kjør `rm reload;touch reload`. Gi den et minutt eller to, så burde endringene være [live](https://mytxs.samfundet.no/). 


### Lesing av loggs
ITK har også et oppsett der man kan se loggs fra de kjørende instansen(e?) på serveren. For å gjøre det, logg på serveren som beskrevet over, og deretter:
1. Skriv `ssh cirkus`. Dette tror jeg er en (ihvertfall virituelt) separat server der alle koden til ITK faktisk kjører. 
1. Så spørs det på hvilken logg man skal se. Av min oppfatning er følgende hva loggene innebærer. For hver av disse, trykk `q` for å gå ut av loggen. 
    1. For å se kjøre loggs, skriv `less /var/log/uwsgi/app/mytxs.samfundet.no.log`
    1. For å se mellomserver(?) loggs, skriv `less /var/log/apache2/external/error-mytxs.samfundet.no.log`
    1. For å se logg av innkommende requests, skriv `less /var/log/apache2/external/access-mytxs.samfundet.no.log`


## Konvensjoner
Her kommer jeg til å skrive ting som ikke har så my å si, men som er fint å ha svart på kvitt:
- Såvidt jeg vet er det ikke en standard for innrykk av django templates. Jeg velger fordi jeg syns det er ganske leselig at
    - Django tags bidrar ikke til innrykk
    - HTML tags bidrar til innrykk
- I så stor grad som mulig bruker jeg enkle hermetegn i python, både på pydoc og i kode. Utgjør ingen funksjonell forskjell, men jeg syns det er mest leselig. 
- Bruk postIfPost i views med mange forms. Det er ikke alltid strengt nødvendig, men løser noen problem og gjør forms lettere å debugge, siden de bare får dataen som er tiltenkt de. I views der det bare er et form, som liste views der eneste POST formet er å lage nye objekt, kan man fint bruke `request.POST or None`.
- Gjennomgående bruker liste views `request.queryset` mens instance views bruker `request.instance`. Det er veldig nyttig å å kunne generalisere over ulike typer objekt og forms, det forenkler tilgangsstyringen og gjør at vi treng færre templates osv. 
