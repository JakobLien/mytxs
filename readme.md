# MyTXS 2.0
Hei, dette er repoet til MyTXS 2.0, den neste versjonen av [MyTSS](https://mytss.mannskor.no/login.php) og [MiTKS](https://mitks.mannskor.no/login.php)!

## Oppsett
Her er hvordan man setter opp nettsiden
1. Når du er der du vil ha repoet, clone repoet med `git clone https://github.com/JakobLien/mytxs.git`
1. Utfør db-migrasjon med `python3 manage.py migrate`
1. Kjør oppsett seed på databasen med `python3 mange.py seed`
1. Opprett en superuser med `python3 manage.py createsuperuser --username admin --email admin@example.com`, og fyll inn et passord, f.eks. admin. Lokalt e det trygt å ha et dårlig passord, men ikke gjør dette i prod!!!
1. Kjør server med `python3 manage.py runserver`

### Postgres
I [oppsett](#oppsett) opprette man i utgangspunktet en lokal sql-database ved å skriv `python3 manage.py migrate`. Dette funke om man bare ska inn og test eller fiks en liten greie, men til tross for at Django ORM-en prøver sitt beste er det ikke absolutt alt som støttes på tvers av databaser. Derfor anbefales det å kjør [innstaller postgres](https://www.postgresql.org/download/), og bytt til det ved å også sett en .env fil med følgende innhold [her](.env). Innholdet av fila burde da være:

    DATABASE_ENGINE=django.db.backends.postgresql
    DATABASE_NAME=postgres
    DATABASE_USER=postgres
    DATABASE_PASSWORD=postgrespassword
    DATABASE_HOST=localhost
    DATABASE_PORT=5432

- Om du under utvikling får feilmelding om at postgres alt kjøre på port 5432? Kjør `sudo pkill -u postgres`. 
- For å resett innholdet i databasen (lokalt selvfølgelig), kjør (i psql shell):

        DROP SCHEMA public CASCADE;
        CREATE SCHEMA public;

## Struktur
Her er kort sagt koss nettsida fungerer:
1. Innkommende requests routes via [urls.py](mytxs/urls.py), som viser de videre til en handler i [views.py](mytxs/views.py). 
1. I [views.py](mytxs/views.py) kjører python kode, og kan kjøre queries på databasen med struktur definert i [models.py](mytxs/models.py), før dataen gis videre til en template i [templates mappa](mytxs/templates/mytxs).
1. Her definere vi hvordan dataen skal vises, og resten av siden. Alle templates trekker fra [base.html](mytxs/templates/mytxs/base.html), som definerer header, navbar og messages popup. Base henter også statiske filer (bilder, css og js) fra [static mappa](mytxs/static/mytxs). Styling er gjort med [Tailwind](#tailwind). 
1. På clientside har vi noen små javascript filer, som skal gjøre siden mere brukervennlig, og gjøre det vanskeligere å gjøre feil:
    - [formSafety.js](mytxs/static/mytxs/formSafety.js) som gir henholdsvis mere brukervenlige forms. 
    - [searchDropdown.js](mytxs/static/mytxs/searchDropdown.js) som gir søkbare og mere brukervennlige select menyer. 
1. Forøverig har vi [signals](mytxs/signals) som håndterer reaksjon på ting som filopplastninger og databaseendringer, [tests.py](mytxs/tests.py) der det skulle vært skrevet bedre tester, [forms.py](mytxs/forms.py), [fields.py](mytxs/fields.py) og [utils mappa](mytxs/utils) der det finnes diverse nyttige utilities for resten av kodebasen, og sist men ikke minst [seed.py](mytxs/management/commands/seed.py) som seeder databasen under utvikling. 

### Signals
Signals i prosjektet er gruppert i ulike filer, en for hvert formål, i [signals](mytxs/static/mytxs) mappa. Viktig at signal filer må stå oppgitt i [apps.py](mytxs/apps.py), om ikke kjører de ikke. 

### Tailwind
Les om tailwind [her](tailwindcss.com/). For å få tailwind i django bruker vi [pytailwindcss](https://github.com/timonweb/pytailwindcss), ikke [django-tailwind](https://github.com/timonweb/django-tailwind), fordi dette virket som herk å sette opp. (Med pytailwindcss får vi tailwind til å kjøre i development. Dermed slipper vi å kjøre det i production bare vi committer [styles.css](mytxs/static/mytxs/styles.css) fila.) For å jobbe med css og kjør tailwind på endring av filer, åpne 2 terminaler og kjør henholdsvis
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

## Publisering
Merk at man må få tilgang av ITK til mytxs mappen på sørveren for å kunne publisere. Stikk innom de i løpet av deres [åpningstider](https://itk.samfundet.no/), så er de veldig behjelpelige med hva enn det skulle være:) Når det er gjort, og du har endringer som skal publiseres, er fremgangsmåten som følger:
1. Kjør `python3 manage.py makemigrations` for å lag migrasjonsfiler for model-endringene du har gjort. Ikke gjør disse uten grunn, og tenk gjennom endringene du gjør. 
1. Skriv `tailwindcss -i mytxs/static/mytxs/inputStyles.css -o mytxs/static/mytxs/styles.css --minify` for å dobbeltsjekke at [styles.css](mytxs/static/mytxs/styles.css) er oppdatert av [tailwind](#tailwind).
1. Kjør `python3 manage.py test`, for å sjekke at endringen din ikke har ødelagt noe, ihvertfall ikke på en måte som er veldig lett å finne ut av. 
    - Testan e verken bra eller fungerende pr no, håpe dem bli årna i framtida engong?:)
1. Skriv `python3 -m pip freeze > requirements.txt` for å lagre i requirements.txt hvilken versjon av alle bibliotekene du bruker. 
    - Pass på å ikke endre versjon av biblioteker uten grunn, og dersom du gjør det uintensjonelt, fiks det før du pushe. >:(
1. Bruk git for å få endringene inn i main, gjerne med merge request inn fra develop (om prosjektet noen gang kommer så langt som å ha flere som jobber på det og kan se over hverandres kode). 
1. Gå på [vpn.samfundet.no](http://vpn.samfundet.no) og last ned wireguard. Dette er samfundet sin VPN, som sikrer at trafikken din ihvertfall kommer fram til huset. Dette er åpenbart ikke nødvendig om man er på husets nett, og er potensielt ikke nødvendig ellers, men det måtte til for meg ihvertfall. 
1. Åpne en terminal og skriv `ssh brukernavn@login.samfundet.no`, der du erstatter brukernavnet med ditt samfundet brukernavn. 
    - I mitt tilfelle: `ssh jakobli@login.samfundet.no`
1. Skriv `cd ../felles/web/mytxs` for å navigere inn i repoet. Slik oppsettet fungerer er at repoet ligger på ITK sine servere, så derfor er neste seg:
1. Skriv `git pull` for å hente alle de nyeste endringene. 
    - La det forbli slik at main er den eneste branchen på serveren, alt annet hadde fort blitt herk og vanskelig å debugge. 
1. Skriv `source venv/bin/activate` for å aktivere [venvet](https://docs.python.org/3/library/venv.html), som kort sagt sikrer at dependencies som django er på samme sted, og at ikke flere prosjekter blir avhengige av samme biblioteker, som hadde gjort at det er vanskeligere å styre hvilken versjon man bruker. Dette kan jeg ikke nok om ennå, så lykke til:) 
1. Skriv `python3 -m pip install -r requirements.txt` for å installere rette versjoner av bibliotekene som brukes. 
1. Kjør `python3 manage.py migrate` for å kjøre migrasjoner på databasen, dersom det er noen. Ikke kjør makemigrations kommandoen på server, det bli bare herk å rydd opp i. 
1. Skriv `python3 manage.py collectstatic` for å samle [statiske filer](https://docs.djangoproject.com/en/4.2/ref/contrib/staticfiles) (fra [static mappa](mytxs/static)) til der serveren vil serve de fra.
1. Skriv `rm reload;touch reload` for å få serveren til å starte på nytt. Gi den et minutt eller to for å ha startet på nytt. 
    - Om det ikke fungerer, kjør gjerne `python3 manage.py runserver` på serveren. Ane ikkje koffor, men det hjalp me ihvertfall. 

### Lesing av loggs
ITK har også et oppsett der man kan se loggs fra den kjørende instansen på serveren. For å gjøre det, logg inn på repoet som beskrevet over, og deretter:
1. Skriv `ssh cirkus`. Dette tror jeg er en (ihvertfall virituelt) separat server der alle koden til ITK faktisk kjører. 
1. Så spørs det på hvilken logg man skal se. Av min oppfatning er følgende hva loggene innebærer. For hver av disse, trykk `q` for å gå ut av loggen. 
    1. For å se kjøre loggs, skriv `less /var/log/uwsgi/app/mytxs.samfundet.no.log`
    1. For å se mellomserver(?) loggs, skriv `less /var/log/apache2/external/error-mytxs.samfundet.no.log`
    1. For å se logg av innkommende requests, skriv `less /var/log/apache2/external/access-mytxs.samfundet.no.log`

## Konvensjoner
Her kommer jeg til å skrive ting som ikke har så my å si, men som er fint å ha svart på kvitt:
- Såvidt jeg vet er det ikke en standard for indentation av django html filer. Jeg velger fordi jeg syns det er ganske leselig at
    - Django tags bidrar ikke til indentation
    - HTML tags bidrar til indentation