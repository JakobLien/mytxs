# Dokumentasjon dokumentasjon
Denne dokumentasjonsløsningen er hjemmesnekra, i form av en enkelt [index.html fil](../../docs/index.html) som konverterer markdown til html i nettlesern. Jeg er inspirert av [Ratio](https://raito.arnaud.at/#/), men ville ha mulighet til å skreddersy resultate mere, så jeg implementerte min egen:) 

## Tilnærming
Målet var å ha en markdown basert dokumentasjon som ikke krevde et build step for å leses i nettleser. I stedet skulle nettleseren konvertere markdown til HTML client side, og det var heile utgangspunktet. For at navigasjon til ulike sider ikke skulle lede til en refresh, lagres heller den nåværende åpnede filen i Fragment Identifier (delen etter `#`). Dette er kjent som [Hash Routing](https://developer.mozilla.org/en-US/docs/Glossary/Hash_routing). 

Det var også et mål å implementere sin egen markdown til html konverterer, slik at denne kunne fikses på slik man selv ønsket. I skrivende stund er ikke denne så godt adskilt mellom bibliotek og bruk som jeg gjerne skulle likt, men det vil fort introdusere mer kompleksitet å prøve å skille det tydeligere også. 

## Markdown til HTML konverterer
Den er ganske simplistisk, og tar veldig utgangspunkt i hvordan jeg skriver markdown. For eksempel er det støtte for rekursive lister, både unumererte og numererte inni hverandre. Støtter også grunnleggende inline greier som fet og skrå skrift. Les koden og prøv deg fram. 

## Lenker og adresser
Måten lenker i dokumentasjonen fungerer er ganske intelligent, om e får si det sjølv. Nåværende fil lagres som sagt etter `#` symbolet, så alle lenker til dokumentasjon får en `href` som begynner med `#`. Lenker til dokumentasjon idenfiseres ved å resolve relative paths. 

For url `#abc/def` vil den spørre om `def.md` i mappa `abc`, mens for `#abc/` vil den spørre etter `#abc/markdown.md`. Om den ikke finner en fil, ved at den får noe annet enn statuscode 200 fra serveren, vil den fjerne en del av URLen også jobbe seg oppover. Først den konkrete filen, så oppover mappe for mappe inntil den finner en gyldig fil. Dette er grunnen til at å ha `readme.md` filer som utgangspunkt er å nyttig, siden den alltid vil finne en fil på vei oppover til rot, ofte rot `readme.md` fila. 

Konvertering av lenker til html er også ganske intelligent. Lenker som begynner med `http` beholdes som de er. Lenker som er relative internt i docs mappa fungerer som lenker til andre markdown filer, og åpnes av dokumentasjons systemet. Lenker som er relative, men som går opp og ut av docs mappa, resolver til den fila på main på github. Slik vil alle lenkene fungere på samme måte i den publiserte dokumentasjonen som de gjør lokalt, skikkelig clean. 

Man kan også benytte seg av dette med at lenker opp av docs mappa vil lenke til github, hvilket jeg har gjort på toppen av denne fila, ved å lenke opp og ut av docs mappa, også inn igjen. Om jeg lenket til index.html fila på den korteste måten, heller enn å gå via rotmappa, ville den tenkt det var en markdown fil, og lenka hadd ikkje fungert. 

Å få url fragments til å fungere var ikke helt trivielt, men var mest å få den til å ikke laste inn en ny markdown fil for hver gang man trykker på en lenke internt på siden. 

## Navbar
Navbaren er en skikkelig clean del av dokumentasjonsleseren. Navbaren lenker til alt på den nåværende siden, ved å plukke ut overskriftene i fila. Dereter generer vi bare markdownen som skal til for å ha en rekursiv punktliste med lenker, også gir vi det til den samme markdown til html funksjonen, og hive inn det på nettsida. Den highlighter også disse overskriftene i navbaren automatisk mens man scroller. 

Sist men ikke minst generer denne også lenker til sider som går oppover mappehierarkiet, ved å fjerne deler av URLen på samme måte som den som håndterer når man gir et ugyldig filanvn i urlen. 

## Bygging
Til tross for at [selve fila](../../docs/index.html) er lagd for å ikke har et build step, har dessverre denne dokumentasjonen et build step for tailwind, rett og slett fordi jeg ikke ønsker å måtte laste inn [tailwind CDNen](https://tailwindcss.com/docs/installation/play-cdn) hele tida, og ønsker å kunne jobbe på denne lokalt. Men for the record, dette er fordi jeg bruker tailwind til styling, og er litt uavhengig av selve dokumentasjons løsningen:)

Kjør og fiks på styles med denne kommandoen:

    tailwindcss --cwd docs -o styles.css --minify --watch 

## TODOs
Den er ganske clean som den er nå, med bare 300 linjer kode, men det er flere ting som kan fikses på:
- Code blocks er ikke fenced, altså det er bare indentation som definerer det, ikke noe omringing av tre backticks. Dette gjør at det er litt tvetydig mellom underpunkt i punktlister og code blocks. Scriptet tolke simplistisk alt som starte med whitespace etterfulgt av enten `- ` eller `1. ` som lister, selv når det er omringet av ting som ikke er det. Kunne gjort det mer intelligent, f.eks. si at alle lister må begynne uten indentation toppnivå. Hadd generelt vært ganske nice å kunna deale med code block og lister sin indentation på en bedre måte. Både å gjøre at code blocks kan legges under listepunkter, og at code blocks som inneheld ting som ser ut som lister beholdes som code blocks. 
    - Dobble newlines inni codeblocks uten at dem splittes inn i separate codeblocks hadd også vært nice. 
- Det kunne potensielt vært ganske sick om når man scrolle nedover siden får man også assignet url fragmenten automatisk underveis? Usikker, men hadd vært interessant. 
- Globalt søk: Legg til en søkebar på toppen som automatisk finner alle filer i dokumentasjonen ved å følge alle lenker fra rotfila som ser ut som følgende regex `\./.*\.md`. Deretter kunne den matchet alle avsnitt som nevner ord man skriver live. Burde vært ganske greit å kjørt alt dette client side, men da burde vi også unngå å sende fleir og fleir requests, at man bare laste ned hver fil en gong. Også viktig at denne unngår å send fleir requests enn no når man ikkje bruke search baren. Dette blir i praksis å gjøre om heile greia til en SPA, så både og om e har lyst til å gjør det. ¯\_(ツ)_/¯
- No e den i dark mode, men hadd sikkert kunna lagd en dark og light mode, tailwind har vel nå greier for sånnt?
- Scroll te toppen knapp?
- E slit med at e ikkje får nettleseren til å gå tilbake i navigasjon, fordi den tenke at det e på samme side. Chat hevda at firefox gjor sånnt her meir aggresivt enn chrome, men e ser ikkje nån måta e kan jobb meg rundt det, har prøvd litt div no. Merk at problemet her e ikkje bare at e må fjern redirects oppover mot en gyldig markdown fil fra loggen, men også at når e navigere via en par lenker og går tilbake blir det ikkje rett, og det e heilt vanlige html lenker med hash based navigasjon.
