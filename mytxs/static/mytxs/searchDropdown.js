for(let select of document.querySelectorAll("select:not([disabled])")){
    // Lag parent, input og options
    let parent = document.createElement("div")
    let input = document.createElement("input");
    input.setAttribute("type", "text");

    // Style dem
    parent.classList.add("inline", 'relative');
    input.classList.add("peer", "mb-0");

    //Set anntall element som skal vises (gjør at select vises som multiselect)
    select.setAttribute("size", Math.min(10, select.options.length));

    // Hacky løsning for å få bredden av input til å match bredden av popupen
    // Må vær før selecten får style hidden like under
    // Kan ikke bruk tailwind for dette sida tallverdien avhenger
    input.style.width = `${select.offsetWidth}px`;

    select.classList.add('absolute', 'z-10', 'left-0', "hidden", "peer-focus:block", "hover:block", 'm-0');

    // Sett element på rett plass
    select.parentNode.replaceChild(parent, select);
    parent.append(input, select);

    // Implementer søkefunksjonen
    input.oninput = e => {
        for(option of select.options){
            option.hidden = !input.value.split(" ").every(word => word ? option.text.toLowerCase().includes(word.toLowerCase()) : true);
        }
    }

    // Handle click på multiselect (å ikke måtte holde CTRL/CMD for å toggle)
    if(select.hasAttribute("multiple")){
        select.onmousedown = e => {
            e.preventDefault();
            if(!e.target.hasAttribute('disabled')){
                e.target.selected = !e.target.selected;
            }
            evaluateManagedForm(e.target.form);
        }
    }

    // Sett inn placeholdertekst som beskriv innholdet
    input.value = getValue(select);

    input.onfocus = e => {
        input.value = "";
        input.oninput(); // Re-evaluer søket om noen lot noe stå der
    }
    input.onblur = e => input.value = getValue(select);
    select.onchange = e => input.value = getValue(select);
}