# MyTXS 2.0
Hei, dette er repoet til MyTXS 2.0, den neste versjonen av [MyTSS](https://mytss.mannskor.no/login.php) og [MiTKS](https://mitks.mannskor.no/login.php)!

## Oppsett
Pull repoet, så tippe e det bare å kjør
1. Utfør db-migrasjon med `python3 manage.py migrate`
1. Kjør oppsett seed på databasen med `python3 mange.py seed`
1. Opprett en superuser med `python3 manage.py createsuperuser --username admin --email admin@example.com`, og fyll inn et passord, f.eks. admin. Lokalt e det trygt å ha et dårlig passord, men ikke gjør dette i prod!!!
1. Kjør server med `python3 manage.py runserver`

## Postgres
I steg 1 under oppsett opprette man i utgangspunktet en lokal sql-database. Dette funke om man bare ska inn og test eller fiks en liten greie, men til tross for at Django ORM-en prøver er ikke absolutt alt støttet på tvers av databaser. Derfor anbefales det å kjør [innstaller postgres](https://www.postgresql.org/download/), og bytt til det ved å også sett en .env fil med følgende innhold [her](.env). Innholdet av fila burde da være:

    DATABASE_ENGINE=django.db.backends.postgresql
    DATABASE_NAME=postgres
    DATABASE_USER=postgres
    DATABASE_PASSWORD=postgrespassword
    DATABASE_HOST=localhost
    DATABASE_PORT=5432

Om du under utvikling får feilmelding om at postgres alt kjøre på port 5432? Kjør `sudo pkill -u postgres`. For å resett innholdet i databasen, kjør:

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