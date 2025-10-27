# Admin dokumentasjon
I denne delen vil jeg beskrive dokumentasjon for, i mangel av et bedre begrep, adminer. En admin er her en person som har et verv, og som følge av dette får ytterligere tilganger til MyTXS. Det kan fortsatt anbefales å lese [dokumentasjonen for vanlige brukere](../bruker/readme.md) før man leser denne. 


## MyTXS vs MyTSS/MiTKS
Etter dataen i medlemsregisteret ble overført rundt slutten av 2023 skal en anse det gamle medlemsregisteret som dødt, lenge leve det nye medlemsregisteret! Det vil si at alle verv, dekorasjoner, turneer, permisjoner, stemmegruppeskifte og alt annet, skal føres inn på MyTXS, mens MyTSS/MiTKS kan dere for det meste se bort ifra. Unntaket til denne regelen er at det er enkelte tilgangsstyrte funksjoner på den gamle nettsiden, som gjør at vi må holde noe av dataen oppdatert. Her skal jeg prøve å gi en fullstendig oversikt over disse funksjonene:
- Styret må få lagt inn verv slik at de får tilgang til medlemsregisteret, for å fikse på denne typen ting, samt opptak av nye korister. 
- Musikkrådet / Kunstnerisk råd må legges inn slik at de får tilgang til å endre på notearkivet. 
- Barsjef, ØkAns i baren og lignende må legges inn slik at de får tilgang til å styre med kryssesystemet. 
- Knauskorister må legges inn for å få tilgang til notearkivet sitt fra 2019 og tilbake i tid, lang historie. 


### Nye medlemmer
Inntil MyTXS har fullstendig erstattet MyTSS fungerer opptak av nye medlemmer som følger:
- En i styret oppretter de i MyTSS / MiTKS som vanlig. Vennligst følg systemet med hvordan medlemsnummer skal være så mye som mulig, de første 4 siffrene skal være året, siste 2 siffrene kommer av stemmegruppen, 00-19 for 1T/1S, 20-39 for 2T/2S osv, 80-99 for dirigenter og lignende. 
- Få de nyopptatte til å overføre dataen sin til MyTXS. Da vil de få en bruker her også, og da er alt good. 


## Noen har glemt passordet sitt
Fra tid til annen vil folk glemme innloggingen sin, her er koss du fikser det, gitt at du har medlemsdata tilgangen. 
1. Naviger til det aktuelle medlemmet. Gitt at de har overført dataen sin skal de være søkbare på medlemmer lista under adminer funksjoner. 
    - Pass på at du søker opp rett medlem, det er fort gjort å slette feil person, også får de til å logge seg inn på deres medlem, snakker fra erfaring tihi. 
1. Kryss av for slett bruker, og trykk lagre. 
1. Kopier lenken som dukke opp på bunnen av siden, og send den til koristen. 
    - Her må du som admin ikke følg den lenken og fyll inn brukernavn og passord, da har du ha opprettet en bruker på deres medlem. Om det skjer, logg inn som deg selv igjen, slett brukeren demmers, også kopier lenka og send te dem. 
1. Koristen skriver inn ønsket brukernavn og passord, og alt er good:)


## Medlemsregisteret
Medlemsregisteret har en struktur i databasen som er nyttig å forstå seg på. Her er de viktigste objekt typene:
- **Medlem**: Dette representerer en person, som oftest en som har sunget i korene. Forøvrig finnes det dirigenter, innbudte medlemmer og mye div i medlemsregisteret. 
- **Verv**: Et verv er et verv et medlem kan ha, som kan gi vedkommende tilganger. De fleste verv tilsvarer de vi er vant til, men det er enkelte viktige unntak:
    - Stemmegrupper og dirigent: Gjennom "stemmegruppeverv" som `ukjentStemmegruppe`, `1T` og `22B` defineres det hvilke kor man er medlem i, og når en var medlem i disse korene. Det samme gjelder `Dirigent` vervet. 
    - Permisjon: `Permisjon` er et annet viktig "verv", som definerer når vedkommende har permisjon. Hva dette betyr kommer vi tilbake til. 
- **VervInnehavelse**: En vervInnehavelse er noe som knytter et verv og et medlem, fra en start dato og potensielt til en slutt dato. Mangel på slutt dato skal tolkes som at vedkommende har vervet i all overskuelig fremtid. 
    - Mange ting i medlemsregisteret er validert på kryss og tvers, slik at det i teorien skal være umulig for databasen å havne i en inkonsekvent tilstand, f.eks. at noen har flere stemmegrupper i samme kor samtidig. Enkelte ganger kan denne valideringen være til hinder fordi man prøver å endre flere ting samtidig, da hjelper det å gjøre endringene en etter en. 
- **Tilgang**: En tilgang representerer en funksjon på nettsiden en bruker kan få tilgang til gjennom et verv. Brukere har da tilgangene så lenge de har vervet, pluss en liten periode før og etter. 
- **Dekorasjon** og **DekorasjonInnehavelse**: Samme sak som verv og vervInnehavelser, bare at en dekorasjonInnehavelse kun har en start dato, nemlig da man fikk utdelt dekorasjonen. 
- **Turneer**: Ikke særlig komplisert, turneer har folk som var på den og en dato. 

For å redigere alle disse tingene kan man trykke "admin funksjoner" på venstresiden av nettsiden, så vil man få opp flere sider der man kan søke seg frem til det man ser etter, for så å redigere de. Disse sidene følger et mønster, der man på toppen kan filtrere en liste av ting, og på bunnen kan opprette nye. For å slette noe, kryss av "Slett" checkboxen inne på den tingen og trykk lagre. Merk at det finnes ingen søkelister for VervInnehavelser og DekorasjonInnehavelser, fordi disse knytnings-objektene redigeres på sidene til de assosierte objektene, f.eks. kan en vervInnehavelse redigeres både på medlemmets side, og på vervets side. 


## Tilganger
Tilgangene er separert av kor, så TSS har ingen tilgang i TKS sine sysaker, og omvendt. Følgende tilganger finns:
- `medlemsdata`: Denne finnes kun for storkorene, men gir tilgang til å redigere medlemmers data. 
- `verv`: Denne gir tilgang til å opprette, slette og redigere på verv. 
- `vervInnehavelse`: Denne gir tilgang til å opprette, fjerne og endre på vervInnehavelser. 
- `dekorasjon` og `dekorasjonInnehavelse`: Du skjønner. 
- `lenke`: Lar deg redigere korets lenker på [lenker siden](http://mytxs.samfundet.no/lenker). Disse lenkene er synlige for alle aktive i koret. 
- `turne`: Lar deg redigere turneer. 
- `semesterplan` og `fravær`: Lar deg henholdsvis redigere semesterplan og fraværet til folk. 
- `tilgang`: Lar deg redigere tilganger, samt hvilke verv som har de. 
    - For å unngå et priviledge escalation angrep er det en begrensning på at noen som har `vervInnehavelse` tilgangen, men ikke har `tilgang` tilgangen ikke får lov til å endre på **VervInnehavelse**r til **Verv** som gir flere tilganger enn de selv har. Dette for å stoppe noen fra å gjøre seg selv til Formann, for så å ha tilgang til alt. 
- `tversAvKor`: Okei, denne er faktisk vanskelig å forklare, men den enkle versjonen er at som korleder er det noen ganger nyttig å kunne få lesetilgang på andre kor sine objekter, for å kunne assosiere ting med de. Dette er fordi vi ønsker å ha ett felles medlemsregister heller enn flere adskilte slik som før. 
    - Vi ønsker ikke at Knauskoret skal ha tilgang til å se alle TSS sine tidligere medlemmer, men vi ønsker oss også et unntak slik at når nye Knauskorister tas opp kan de legges inn av lederen av Knauskoret. Dette unntaket er det tvers av kor tilgangen er, og den burde derfor generelt begrenses til korledere. 
    - Siden denne tilgangen kun er unntaksmessig nyttig er dette en checkbox i innstillinger for alle som har denne, og den er i utgangspunktet skrudd av. 

Tilganene over er `bruktIKode`, som vil si at å få denne tilgangen gir den som har den tilgang til noe på nettsiden. Samtidig kan kor opprette sine egne tilganger, som jeg gjerne omtaler som tilgangsgrupper. Disse er brukt mest for å kunne gruppere verv, f.eks. `Styret` og `MR`, i sjekkheftet eller i undergruppe henelser. 

Under tilganger på admin funksjoner finnes det også en oversikt side, som viser hvem som har hvilke verv som har hvilke tilganger, med lenker til alt sammen. 


## Lenker
Lenker er en liten bonusfunksjon som er grei å vite om. På [lenker siden](https://mytxs.samfundet.no/lenker) kan alle aktive meldemmer av koret se lenker, og adminer kan redigere de. I tillegg kan disse lenkene også brukes som forkortede (ish) redirect lenker, tenk [bit.ly](https://bitly.com/). For å opprette en redirect lenke er det bare å krysse av for at den skal redirecte, og så lenge det er krysset av vil `http://mytxs.samfundet.no/to/<kor>/<lenke-navn>` redirecte dit. 

Det som er kult med disse lenkene, i motsetning til bit.ly lenker og lignende, er at man kan slette en slik lenke, også opprette den igjen senere, gitt at man gir den samme navn. Altså er det mulig å produsere en QR kode, og fortløpende endre hva den peker på, etter at man har printet den opp. Lenker både til redirect lenken, og til et bilde av QR koden for denne lenken dukker opp til høyre på siden når dette er krysset av for. 


## Semesterplan og fravær
Semesterplan har 2 typer objekt i databasen:
- **Hendelse**: Dette er en hendelse i noens kalender. En hendelse har start, slutt, sted og beskrivelse, og er en av 4 typer som styrer hvordan oppmøtene håndteres. 
- **Oppmøte**: Dette er knytningen mellom en person og det de møter opp på. Her lagres fraværsmeldingen, om de kommer, gyldighet og antall minutter. 


### Fraværssøknader
Fraværssøknader som folk skriver kommer inn [her](https://mytxs.samfundet.no/frav%C3%A6r/s%C3%B8knader?gyldig=None&harMelding=on). Her kan man filtrere på ganske mye diverse, så det skal være opp til hver enkelt hvordan en jobber med fraværssøknader. 


### Fraværsføring
Fraværsføring er, etter undertegnedes erfaring, stress. Derfor har MyTXS flere verktøy som hjelper med dette. I tillegg til å kunne jobbe med fraværet litt som i et regneark på enhver individuelle hendelse, er det også 2 ekstra verktøy for å føre fravær på direkten, der begge disse dukker opp en halvtime før enhver obligatorisk hendelse starter, på siden til hendelsen. 
- Fraværmodus: Dette dukker opp som en lenke på toppen av hendelsen. Når man er i fraværmodus får man opp en liste av folk, og kan føre fraværet til vedkommende ved å trykke på de. Da føres fraværet basert på når du trykker på, rundet ned til nærmeste hele minutt. Etter å ha trykket på de kan man også redigere det konkrete antall minutter frvær. Det er en par instillinger på toppen der man kan velge å få opp de som har blitt ført på, samt de som har meldt at de ikke kommer. 
- QR kode: QR koden burde være kjent for de fleste, men kort sagt er det en QR kode med en lenke til en spessiel MyTXS innloggings side. Når de logger inn der føres fraværet på samme måte som om de hadde blitt trykket på i fraværmodus, minuttet rundes ned. 


### Permisjon
Permisjon betyr jo litt forskjellig i ulike kor, men for MyTXS er det ganske enkelt. Om noen har permisjon en periode, vil det ikke genereres oppmøter for vedkommende. De trenger ikke, og kan ikke, søke fravær på ting i den perioden, og vil heller ikke dukke opp i statistikken. 


### Fraværsstatistikk
Under Fravær fanen i admin funksjoner finner du også følgende:
- **Oversikt**: Her får du opp fravær per person, fordelt på Umeldt fravær, Ugyldig fravær, Gyldig fravær og Totalt fravær. Alle disse feltene viser minutter og prosent i parentes, og fargen kommer av prosenten. For å se flere detaljer på en aktuell korist sitt fravær kan du trykke "Se semesterplan" til høyre. 
- **Statistikk**: Denne har det samme datagrunnlaget, men grupperer det på blant annet stemmegrupper, karantenekor og småkor. 


### Undergruppe hendelser
Utgangspunktet er at undergruppe hendelser har en ekstra dropdown der man kan velge hvilke medlemmer som skal få opp denne i semesterplan. I tillegg er det 2 funksjoner oppå dette. 
- Det ene er jobbvakter, altså undergruppe hendelser som som `[#2] Lenkevakt`, som betyr at 2 korister kan melde seg opp til den på jobbvakter siden. Når antallet er nådd kan ikke flere melde seg på. 
- Det andre er såkalte tilgangsgrupper. Klassisk har man hendelser som styremøter der man alltid vil ha dette i kalendern til de som har disse vervene. Da kan man opprette Undergruppe hendelser som starter på `[Styret] Møte`, og dersom det finnes en tilgang som heter `Styret` vil de folka som har verv med den tilgangen automatisk legges inn. 


### QnA og tips om fravær
- Kan jeg endre på teksten `[OBLIG]` og lignende for en hendelse?
    - Ja, bare skriv inn `[Ka som helst]` på starten. Bare pass på å ikkje vær missledende på ka som e oblig og ikkje da:)
- Hvilken type fravær registreres det som før man har valgt om fraværsmeldingen er gyldig?
    - Alt fravær er ugyldig inntil det er markert som gyldig. 
- Hva betyr et tomt felt i fravær feltet?
    - Dette betyr ikke møtt, altså fraværet blir antall minutter hendelsen varer. 
- Hvorfor kan ikke obligatoriske hendelser vare lenger enn 12 timer?
    - Se forrige punkt. Selv om øvelse på 3 timer burde åpenbart kunne gi 180 minutter fravær, burde vel ikke en øvingshelg gi `2*24*60 = 2880` minutt fravær? Problemet her er at mengden fravær man kan få kommer direkte av lengden på hendelsen. Noen ganger er dette en upraktisk anntakelse, men totalt sett står jeg ved dette design valget. Å skulle legge til en alternativ måte å føre fravær på som ikke er knyttet til hendelsens varighet i kalendern virker veldig overkomplisert. 
- Kan en undergruppe Hendelse gjøres obligatorisk for de det gjelder?
    - Nei. Kanskje i framtida, men det e my jobb å fiks. 
- Kan man ha hendelser på tvers av TXS?
    - Ja, bare hiv dem inn på Sangern som kor heller enn TSS eller TKS, ihvertfall korlederne har tilgang til dette, og det er lett å gi tilgangen til flere :) 


## Logg
MyTXS har et logg system, som loggfører alle endringer på nesten alle objekter i databasen. Disse loggene er mulig å søke og bla seg frem i, men som oftest er det lettest å følge lenker med litens skrift `(Logg)` til høyre for overskrifter og skjema. Loggene er knyttet på alle relasjoner, slik at innad i loggene en kan trykke seg fra Medlem til VervInnehavelser til Verv til Tilganger, samt fram og tilbake i tid på samme logg. 

Det eneste vi ikke har logger på er personinformasjon, altså all data på medlemmet deres med unntak av navnet deres. Dette er for at det skal være lett for folk å vite hvilken personinformasjon vi har lagret på de, og lett for de å rette opp i og eller slette den. GDPR og sånnt vøttu:)


## Eksport
Eksport siden har en tilhørende tilgang, og 2 funksjoner. 
- Den ene er en generell eksport, der man kan velge hvem man skal trekke ut data for, samt hvilken data man ønsker for de, så får man det på CSV. 
- Den andre funksjonen er å trekke ut fraværsdata formatert spesifikt for musikkens studieforbund. 
    - Her må man trikse og fikse inntil man får konvertert CSVen til et regneark, slik de ønsker å få lastet opp. Ideelt sett skulle kanskje nedlastningen vært direkte til regneark, men det hadde vært mye meir knot å gjøre i kode, så ye. Bare prøv deg fram, så får du det nok te:)
    - Også må du kanskje fylle inn litt ekstra på infoen te folk om det er noe som mangler. 


## Øvrige tips
- Rundt om på nettsiden ser du kanskje `(?)`. Dette er en tooltip, hold musepekeren over den så vil det stå en forklaring der. 
- Siden vervInnehavelser og lignende kan redigeres på flere steder, ta gjerne et øyeblikk til å tenk hvor det er lettest å gjøre endringen du ønsker å gjøre, så sparer du nok litt tid. 
- Både i sjekkheftet og i semesterplan dukker det opp `rediger` lenker på folk og hendelser, som tar deg rett til deres redigeringsside. 
