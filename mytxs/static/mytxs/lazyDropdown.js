/*  Denne fetcher dropdown alternativ etter siden er lastet inn, for å få siden til å laste inn mye raskere.
 */

if(document.currentScript.dataset.json){
    // Dette scriptet får hvilke felt som er disabled via data-json=... på script tagget
    // Formatet er en json liste med formPrefix-fieldName
    // f.eks: ["vervInnehavelse-verv", "dekorasjonInnehavelse-dekorasjon"]
    const selectNames = JSON.parse(document.currentScript.dataset.json);

    for(selectName of selectNames){
        (async selectName => {
            // Hent optionsa
            const url = new URL(window.location.href);
            url.searchParams.set('getOptions', selectName)
            const json = await fetch(url).then(response => response.json())
            
            // Skaff alle selects vi skal sette de inn på
            let selects = document.querySelectorAll(`select[name^='${selectName.split('-')[0]}'][name$='${selectName.split('-')[1]}']`)

            for(select of selects){
                // Skip disabled felt
                if(select.disabled){
                    continue
                }

                // Start med innsetting på i=1, altså etter blank optionen ('---------')
                let i = 1;
                for(optionData of json){
                    // Siden options har samme rekkefølge på server og client, om selecten har en option
                    // på denne indeksen alt, og den har samme navn som den vi ska sett inn, skip å sett den inn.
                    // Ellers, sett inn før den. Da vil template produserte options og js produserte options
                    // kom i samme rekkefølge som om alt va produsert på serveren:)
                    if(select.options.length > i && select.options[i].value === optionData[0].toString()){
                        i += 1
                        continue
                    }
                    
                    // Opprett optionen
                    let option = document.createElement("option")
                    option.value = optionData[0]
                    option.text = optionData[1]
                    
                    // Sett inn optionen
                    select.add(option, i)
                    i += 1;
                }
                
                // Må resett nån visuelle ting når vi legg til masse options
                select.setAttribute('size', Math.min(10, select.options.length));
                select.style.display = 'block';
                select.previousElementSibling.style.width = `${select.offsetWidth}px`;
                select.style.display = '';
            }
        })(selectName)
    }
}