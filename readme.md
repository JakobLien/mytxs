# MyTXS 2.0
Hei, dette er repoet til MyTXS 2.0, den neste versjonen av [MyTSS](https://mytss.mannskor.no/login.php) og [MiTKS](https://mitks.mannskor.no/login.php)!


## Oppsett
Her er hvordan man setter opp nettsiden enkelt lokalt
1. Når du er der du vil ha repoet, clone repoet med `git clone https://github.com/JakobLien/mytxs.git`. 
1. Installer [PostgreSQL](https://www.postgresql.org/download/), for Mac anbefales sterkt [Postgres.app](https://postgresapp.com/). For Ubuntu ser det ut som at libpq-dev også er nødvendig. Husk passordet du satte opp! Hvis det ikke er default, som er `postgrespassword`, så må du legge det til senere i .env-fila beskrevet noen punkter lenger nede. 
1. Opprett et [venv](https://docs.python.org/3/library/venv.html) med navn `venv` gjennom `python -m venv venv`. Venv betyr Virtual Environment, og er at alle pakkene installeres sammen med koden din. Dette gjør det enklere å sikre at man har rett versjon av alle pakker, uavhengig av hva andre ting på maskinen din vil ha. Husk å aktivere venvet før du kjører applikasjonen eller installerer ting, slik som i neste steg. På Mac er dette `source venv/bin/activate`. 
1. Kjør `python3 -m pip install -r requirements.txt` for å installer alle packages med rett versjon. 
1. Generer en Django-nøkkel, for eksempel [her](https://djecrety.ir/).
1. Lag en .env-fil i samme mappe som denne readme fila, med følgende: 

        DJANGO_SECRET=<nøkkelen du genererte> 
        DJANGO_DEBUG=True

Dersom du *ikke* brukte defaultpassordet, eller andre postgres-defaults, er du nødt til å legge dem til her. Dette gjør du ved hjelp av

        DATABASE_ENGINE    =  django.db.backends.postgresql
        DATABASE_NAME      =  postgres
        DATABASE_USER      =  postgres
        DATABASE_PASSWORD  =  postgrespassword
        DATABASE_HOST      =  localhost
        DATABASE_PORT      =  5432

der du bytter ut det du ikke lot være default i postgres-setupet. 
1. Utfør db-migrasjon med `python3 manage.py migrate`. Dette oppretter alle tables du treng i den lokale databasen din. 
1. Kjør seed på den lokale databasen med `python3 manage.py seed --adminAdmin`. Dette oppretter en bruker med brukernavn og passord `admin`. 
    - For å ha litt mere data å jobbe med, kan du gi argumentet `--testData`. Dette vil opprette medlemmer fra 2010 og utover, i både storkor og småkor, verv, dekorasjoner, hendelser, korledere og dirigenter. 
1. Kjør servern med `python3 manage.py runserver`. 


### Postgres
Vi kan ikke bruk sqlite til utvikling fordi det mangle [jsonField](https://docs.djangoproject.com/en/4.2/ref/models/fields/#django.db.models.JSONField). Heller enn å prøve å installere extentionen som gir det anbefaler jeg derfor å bare installere postgres så det blir samme database som prod. [settings.py](mytxs/settings.py) skal være satt opp til koble til med default postgres credentials. Du kan endre på dette ved å legg inn følgende i .env:

    DATABASE_ENGINE=django.db.backends.postgresql
    DATABASE_NAME=postgres
    DATABASE_USER=postgres
    DATABASE_PASSWORD=postgrespassword
    DATABASE_HOST=localhost
    DATABASE_PORT=5432

- Om du under utvikling får feilmelding om at postgres allerede kjøre på port 5432, fungere det for meg å på Mac kjør `sudo pkill -u postgres`. 
- For å resett innholdet i databasen (lokalt selvfølgelig), kjør (i psql shell, `python3 manage.py dbshell`):

        DROP SCHEMA public CASCADE;
        CREATE SCHEMA public;


## Struktur
Her er strukturen av filene:
1. Innkommende requests routes via [urls.py](mytxs/urls.py), som sender de til en view i [views.py](mytxs/views.py).
1. I [views.py](mytxs/views.py) kjører faktisk python kode. Her kan vi kjøre queries på databasen, med struktur definert i [models.py](mytxs/models.py), før dataen gis videre til en template i [templates mappa](mytxs/templates/mytxs).
1. I templates mappa definere vi hvordan dataen skal vises med html. Sånn ca alle templates bygger på [base.html](mytxs/templates/mytxs/base.html), da denne definerer header, navbar, popup og innstillinger. Den refererer også til statiske filer (bilder, css og js) fra [static mappa](mytxs/static/mytxs). Styling er gjort med [Tailwind](#tailwind). 
    - Nesten alle templates arver fra [instance.html](mytxs/templates/mytxs/instance.html) eller [instanceListe.html](mytxs/templates/mytxs/instanceListe.html), som har generel logikk for visning av henholdsvis instanser med forms og formsets og lister av instanser med inndeling i sider man kan bla gjennom. 
1. På clientside har vi noen små javascript filer, som skal gjøre siden mere brukervennlig, og gjøre det vanskeligere å gjøre feil:
    - [formSafety.js](mytxs/static/mytxs/formSafety.js) gir mere brukervenlige forms ved å markere endringer, bekrefte før lagring og lignende. 
    - [searchDropdown.js](mytxs/static/mytxs/searchDropdown.js) gir søkbare og mere brukervennlige select menyer over hele siden. 
    - [lazyDropdown.js] gjør at mange dropdown menyer som har mange like alternativ laster inn en felles gang, med litt hjelp fra serveren. Dette er f.eks. nødvendig på verv, der vi har mange dropdownmenyer med oppmot tusenvis av medlemmer. 
1. Forøverig har vi:
    - [signals](mytxs/signals) som fikser på filopplastninger og produserer logger. 
    - [management commands](/Users/jakoblien/Desktop/mytxs/mytxs/management/commands) der vi definerer ekstra konsoll kommandoer som [seed](mytxs/management/commands/seed.py), [slettGamleOppmøter](mytxs/management/commands/slettGamleOppmøter.py) og [cron](mytxs/management/commands/cron.py). 
    - [forms.py](mytxs/forms.py), [fields.py](mytxs/fields.py) og [utils mappa](mytxs/utils) som definerer forms, felt (både form og model) og diverse utilities.
    - [templateTags.py](mytxs/templateTags.py) som definerer ekstra [template tags](https://docs.djangoproject.com/en/4.2/ref/templates/builtins/) vi kan bruke. 
    - [consts.py](mytxs/consts.py) der vi definerer diverse konstanter for prosjektet, blant annet navnene på korene, hvilke tilganger som finnes og annet nyttig. 


### Tailwind
Les om tailwind [her](tailwindcss.com/). For å få tailwind i django bruker vi [pytailwindcss](https://github.com/timonweb/pytailwindcss), ikke [django-tailwind](https://github.com/timonweb/django-tailwind), fordi dette virket som herk å sette opp. Med pytailwindcss får vi tailwind til å kjøre i development. Dermed slipper vi å kjøre det i production bare vi committer [styles.css](mytxs/static/mytxs/styles.css) fila. For å kjøre tailwind automatisk på endring av relevante filer, åpne 2 terminaler og kjør henholdsvis
1. `python3 manage.py runserver`
1. `tailwindcss -i mytxs/static/mytxs/inputStyles.css -o mytxs/static/mytxs/styles.css --watch --minify`

Da vil [styles.css](mytxs/static/mytxs/styles.css) oppdateres så fort du endre noe i hvilken som helst html eller js fil! Husk å commit styles.css slik at vi slipper å styre med Tailwind på ITK servern. 

For å få hjelp når du skriv tailwind anbefales virkelig [Tailwind CSS IntelliSense](vscode:extension/bradlc.vscode-tailwindcss). Det e lett å sett opp at det funke med css og html i templates, men for å få det te å også funk der vi bruke det i javascript, hiv på disse snippetsa i din settings.json. 

```
    "tailwindCSS.experimental.classRegex": [
        ["[Ss]tyles?([^;]*);", "[\"'`]([^\"'`\\n]*)[\"'`]"], //Match alle strings mellom style og semikolon
        [".classList([^;]*);", "[\"'`]([^\"'`\\n]*)[\"'`]"] //Match alle strings mellom .classList og semikolon
    ],
```


## Deler av prosjektet
Denne delen av readme skal forhåpentligvis fungere som en intro til prosjektet, for å tydeliggjøre hvilke valg vi har tatt og hvordan man burde tenke på prosjektet. 


### Medlemsregisteret og tilgangsstyring
Medlemsregisteret har flere modeller, men 4 viktige modeller:
- Medlem representerer et medlem/en person. De har helst et medlemsnummer for å knyttes opp mot den gamle siden, potensielt en bruker, forhåpentligvis et navn og potensielt diverse data på seg. 
- Verv representerer et verv i et kor. Dette er også hvordan vi representerer dirigenter og stemmegrupper. 
- VervInnehavelse representerer at noen har et verv i en periode. VervInnehavelse har, i tillegg til foreignkey til Medlem og Verv, start og slutt Slutt dato er nullable, for å kunne representere "vi vet ikke når vedkommende slutter", hvilket systemet tenker på som at de er aktiv inn i evigheten. 
- Tilgang har en mange til mange relasjon til verv, og representerer en gruppe medlemmer er i, eller noe de kan gjøre.  Medlemmer får tilganger av at de har en aktiv VervInnehavelse til et verv som har den tilgangen. 

Tilganger som lar deg gjøre noe nytt er brukt i kode, hvilket vil si at navnet på tilgangen finnes i kodebasen. Følgelig kan ikke slike tilganger slettes, opprettes eller endres navn på. Verv kan også være brukt i kode. Dette gjelder foreløpig verv ved navn `Dirigent`, `ukjentStemmegruppe` og faktiske stemmegrupper som `S`, `1T`, og `22B`. Dette er altså hvordan vi representerer at man er aktiv i korene, du har et stemmegruppe-verv i den perioden du sang den stemmegruppen. 

Grunnet hvor dårlig struktur det var på det gamle medlemsregisteret måtte jeg gjette på ganske mye data. Koden som gjorde denne gjetningen og hva vi gjettet kan du se i  [transfer.py](mytxs/management/commands/transfer.py).


### Logging
Vi har 2 modeller for logging:
- Logg som inneholder pk, model, tidspunkt, author osv, og et jsonfelt som er en json representasjon av objektet. I jsonfeltet representeres foreign key felt som pk av den nyeste loggen av det relaterte objektet, som er det som muliggjør navigering mellom ulike logger. 
- LoggM2M som representerer mange til mange relasjoner mellom objekter. 

Når noe skal lagres brukes nesten alltid [logAuthorAndSave](mytxs/utils/logAuthorUtils.py), som tar et form, lagrer, og når loggen er opprettet automatisk av [logSignals.py](mytxs/signals/logSignals.py) hiver denne på hvilken forfatter det var. Hvilken forfatter det var er praktisk umulig å få tak i i logSignals på en ryddig måte, så derfor får vi bare med det når endringen er gjort via views. Endringer gjort av admin eller seed.py har følgelig ikke author, men de har logger, siden signals kommer det uansett. Merk også at logger opprettes kun når noe av loggen faktisk har endret seg, for å unngå unødvendige logger ala "Bob endret ingenting på dette tidspunktet". 

Grunnen til at vi ikke har LoggM2M som del av Logg er fordi m2m relasjoner kan endres på begge sider, og om vi lagre verv -> tilgang informasjonen på vervet som en liste, hvilket er mulig, blir det veldig mange logger av at man endrer fra tilgang siden, og mindre oversiktlig hva som faktisk ble endret. Slik det er nå kan man med stor sikkerhet si at "dersom vi har en logg på den modellen, er det den modellen sitt modelform som ble endret" (Det er også kodemessig enklere å gjøre det som en separat tabel.)


### Semesterplan og fravær
Vi har 2 modeller for semesterplan og fravær:
- Hendelse representerer noe som er i noens kalender. Vi har fire typer hendelser:
    - Oblig: Fraværsføring, folk søker fravær om de ikke kommer.
    - Påmelding: Folk kan melde fra om de kommer eller ikke. 
    - Frivillig: Uten føring av fravær eller melding om de kommer. 
    - Undergruppe: For ting som bare noen få korister skal på, f.eks. jobbvakter. 
- Oppmøte representerer noen som potensielt drar på den hendelsen. Et oppmøte har
    - Fravær: Antall minutter fravær på hendelsen. Null betyr ikke møtt. Dette valideres begge veier med varigheten av hendelsen, så man ikke kan ha mer fravær enn varigheten av hendelsen. 
    - Gyldig: Hvorvidt eventuelt fravær er gyldig, eller ugyldig. 
    - Ankomst: Koristens kortsvar, `Kommer`, `Kommer kanskje` eller `Kommer ikke`. 
    - Melding: Fritekstfelt der både koristen og fraværsfører kan skrive til hverandre. 

Undergruppe hendelser har kun oppmøter for de som skal komme på de. Hvem som skal på undergruppehendelsen kan velges på hendelsen sin redigerings side med en dropdown meny. Man kan også i firkantparentes foran navnet på Hendelsen skrive navnet på en tilgang, og da vil de som har den tilgangen i det koret bli lagt til automatisk når hendelsen lagres. Om man skriver hashtag antall, f.eks. '#3', vil opptil så mange kunne melde seg på hendelsen fra 'Jobbvakter' siden. 

Hver korist har en kalender for hvert kor de er aktive i. Altså vil småkorister ha to ulike kalendere, en for storkor, en for småkor. Sangern kan opprette Frivillig og Undergruppe hendelser, som havner i storkor sine kalendere. 

Vi har iCal eksport, slik at korister kan få semesterplan inn i kalenderapplikasjonen sin. En utfordringen med dette er at veldig mange bruker Google Calendar, og Google Calendar nekter oppdatere seg oftere enn en gang pr dag, potensielt skjeldnere. For å komme forbi dette må man gå via Google Calendar sin API, opprette kalendere, og selv endre de når noe endres. En utfordringen med dette er at MyTXS har en kalender per medlem pr kor. Derfor oppretter MyTXS opptil ish 240 individuelle kalendere i Google Calendar, som manuelt er delt med hver korist. Disse er basert på iCal eksport koden, slik at videre utvikling bare burde trenge å endre på den, også vil resultatet havne begge steder. I tilfelle endringer i Google Calendar grunnet en feil ikke blir oppdatert, har vi også et script som kjøres hver time av cron.py, som går over alle sine kalendere og fikser det som ikke stemmer. 


## Publisering
Merk at man må få tilgang av ITK til mytxs mappen på sørveren for å kunne publisere. Stikk innom de i løpet av deres [åpningstider](https://itk.samfundet.no/), så er de veldig behjelpelige med hva enn det skulle være:) Når det er gjort, og du har endringer som skal publiseres, er fremgangsmåten som følger:
1. Kjør `python3 manage.py makemigrations` for å lag migrasjonsfiler for model-endringene du har gjort. Ikke gjør disse uten grunn, og tenk gjennom endringene du gjør. 
1. Skriv `tailwindcss -i mytxs/static/mytxs/inputStyles.css -o mytxs/static/mytxs/styles.css --minify` for å dobbeltsjekke at [styles.css](mytxs/static/mytxs/styles.css) er oppdatert av [tailwind](#tailwind).
1. Kjør `python3 manage.py test`, for å sjekke at endringen din ikke har ødelagt noe, ihvertfall ikke på en måte som er veldig lett å finne ut av. 
1. Skriv `python3 -m pip freeze > requirements.txt` for å lagre i requirements.txt hvilken versjon av alle bibliotekene du bruker. 
    - Pass på å ikke endre versjon av biblioteker uten grunn, og dersom du gjør det uintensjonelt, fiks det før du pushe. >:(
1. Bruk git for å få endringene inn i main på github, gjerne via merge request (om prosjektet noen gang kommer så langt som å ha flere som jobber på det og kan se over hverandres kode). 
1. Gå på [vpn.samfundet.no](http://vpn.samfundet.no) og last ned wireguard. Dette er samfundet sin VPN, som sikrer at trafikken din ihvertfall kommer fram til huset. Dette er åpenbart ikke nødvendig om man er på husets nett, og er potensielt ikke nødvendig ellers, men det måtte noen ganger til for meg ihvertfall. 
1. Åpne en terminal og skriv `ssh brukernavn@login.samfundet.no`, der du erstatter brukernavnet med ditt samfundet brukernavn. 
    - Her vil jeg gripe muligheten til å sterkt anbefale VSCode extentionen Remote Explorer, som lar deg bruke VSCode gjennom SSH, magisk nyttig om man ikke er en Linux guru. 
1. Skriv `cd ../felles/web/mytxs` for å navigere inn i kodebasen. Følgelig er neste seg:
1. Skriv `git pull` for å hente alle de nyeste endringene. 
    - La det forbli slik at main er den eneste branchen på serveren, alt annet hadde fort blitt herk og vanskelig å debugge. 
1. Skriv `source venv/bin/activate` for å aktivere [venvet](https://docs.python.org/3/library/venv.html). 
1. Skriv `python3 -m pip install -r requirements.txt` for å installere rette versjoner av bibliotekene som brukes. 
1. Kjør `python3 manage.py migrate` for å kjøre migrasjoner på databasen, dersom det er noen. Ikke kjør makemigrations kommandoen på server, det bli bare herk å rydd opp i. 
1. Skriv `python3 manage.py collectstatic` for å samle [statiske filer](https://docs.djangoproject.com/en/4.2/ref/contrib/staticfiles) (fra [static mappa](mytxs/static)) til der serveren vil serve de fra.
1. Skriv `rm reload;touch reload` for å få serveren til å starte på nytt. Gi den et minutt eller to for å ha startet på nytt. 


### Lesing av loggs
ITK har også et oppsett der man kan se loggs fra den kjørende instansen på serveren. For å gjøre det, logg inn på repoet som beskrevet over, og deretter:
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
- I så stor grad som mulig bruker jeg enkle hermetegn i python, både på pydoc og i kode. 
- Bruk postIfPost i views med mange forms. Det er ikke alltid strengt nødvendig, men løser noen problem og gjør forms lettere å debugge, siden de bare får dataen som er tiltenkt de. I views der det bare er et form, som liste views der eneste POST formet er å lage nye objekt, kan man bruke `request.POST or None`
- Gjennomgående bruker liste views request.queryset mens instance views bruker request.instance. Det er veldig nyttig å å kunne generalisere over ulike typer objekt og forms, forenkler tilgangsstyringen og gjør at vi treng færre templates, og de vi treng kan ofte bare modifisere de to hoved templatesa [instance.html](mytxs/templates/mytxs/instance.html) og [instanceListe.html](mytxs/templates/mytxs/instanceListe.html). 