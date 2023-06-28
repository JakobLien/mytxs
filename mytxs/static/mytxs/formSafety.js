/*  Gjør forms med klasse 'managedForm' lettere å jobbe med ved å:
    - Disable lagre og angre knapper
    - Ha en angreknapp som angrer alle (ulagrede) endringer gjort
    - Ha en liste av hva som endrer seg
    Gjør også forms med klasse 'creationForm' lettere å jobbe med ved å:
    - Disable lagreknappen når ikke alle required felt er utfylte

    Koden e no skrevet på en måte som gjør at ingenting bli ødelagt om man ikkje har javascript 
    altså man kan fortsatt send forms som vanlig. Dette er positivt for accessability, om filer 
    ikke laster osv. Prøv å la det forbli slik:)

    Script fila her burde være includa som defer, slik at den kjøre etter formsa e lasta inn:
    https://developer.mozilla.org/en-US/docs/Web/HTML/Element/script#attr-defer
 */

function getInitialValue(element){
    if(element.tagName === 'SELECT'){
        if(element.hasAttribute('multiple')){
            return [...element.options].filter(option => option.defaultSelected).map(option => option.text);
        }else{
            return element.querySelector('option[selected]').text;
        }
    }else if(element.type === 'checkbox'){
        return element.defaultChecked;
    }
    return element.defaultValue;
}

function getValue(element){
    if(element.tagName === 'SELECT'){
        if(element.hasAttribute('multiple')){
            return [...element.options].filter(option => option.selected).map(option => option.text);
        }else{
            return element.options[element.selectedIndex].text;
        }
    }else if(element.type === 'checkbox'){
        return element.checked;
    }
    return element.value;
}

function resetValue(element){
    if(element.tagName === 'SELECT'){
        if(element.hasAttribute('multiple')){
            [...element.options].forEach(option => {option.selected = option.defaultSelected});
        }else{
            element.selectedIndex = element.querySelector('option[selected]').index;
        }
    }else if(element.type === 'checkbox'){
        element.checked = element.defaultChecked;
    }else{
        element.value = element.defaultValue;
    }

    // For å sette verdien av search dropdown
    element.onchange ? element.onchange() : null;
}

function getActualElements(form){
    return [...form.elements].filter(elem => form.querySelector(`label[for='${elem.id}']`));
}

function arrayEqual(o1, o2){
    if(o1.constructor.name === 'Array'){
        if(o1.length !== o2.length){
            return false
        }
        for(let i = 0; i < o1.length; i++){
            if(o1[i] !== o2[i]){
                return false
            }
        }
        return true
    }else{
        return o1 === o2;
    }
}

/** Returne en liste med endringer, der hvert element er en dictionary med relevante ting */
function getFormChanges(form){
    changes = [];
    for (const element of getActualElements(form)){
        const initialValue = getInitialValue(element);
        const value = getValue(element);
        if(!arrayEqual(value, initialValue)){
            changes.push({
                labelText: form.querySelector(`label[for='${element.id}']`).textContent.replace(':', ''),
                initialValue: initialValue,
                value: value,
                element: element,
                label: form.querySelector(`label[for='${element.id}']`)
            })
        }
    }

    // Legg til changeText
    for(const change of changes){
        if(change.initialValue.constructor.name === 'Array'){
            change.changeText = [];
            for(const option of change.element.options){
                if(change.value.includes(option.text) && !change.initialValue.includes(option.text)){
                    change.changeText.push(`${change.labelText} la til '${option.text}'`);
                }else if(!change.value.includes(option.text) && change.initialValue.includes(option.text)){
                    change.changeText.push(`${change.labelText} fjernet '${option.text}'`);
                }
            }
        }else{
            change.changeText =`${change.labelText} endret fra '${change.initialValue}' til '${change.value}'`;
        }
    }

    return changes;
}

const changedFieldStyle = ['border-0', 'border-l-4', 'border-orange-600'];

let unsavedForms = 0;

function evaluateManagedForm(form){
    const changes = getFormChanges(form);
    
    for(const element of getActualElements(form)){
        // Fjern røde markører
        form.querySelector(`label[for='${element.id}']`).nextElementSibling.classList.remove(...changedFieldStyle);

        // Fjern eksisterende changetext
        if(!element.classList.contains('hidden')){
            element.removeAttribute('title');
        }else{
            element.parentElement.removeAttribute('title');
        }
    }

    for(const change of changes){
        // Legg til røde markører
        change.label.nextElementSibling.classList.add(...changedFieldStyle);

        // Legg til changeText
        if(!change.element.classList.contains('hidden')){
            change.element.setAttribute('title', change.changeText);
        }else{
            change.element.parentElement.setAttribute('title', change.changeText);
        }
    }

    // Oppdater disable status
    if((changes.length !== 0) === form.querySelector('[type=submit]').disabled){
        form.querySelector('[onclick=\'resetForm(this.form)\']').disabled = !form.querySelector('[onclick=\'resetForm(this.form)\']').disabled;
        form.querySelector('[type=submit]').disabled = !form.querySelector('[type=submit]').disabled;
    }

    // Oppdater om vi blokkere brukeren fra å forlat siden, avhengig av om de har ulagrede endringer
    if(unsavedForms > 0){
        window.onbeforeunload = function() {
            return 'Anbefaler å lagre endringene før du forlater siden:)';
        };
    }else{
        window.onbeforeunload = null;
    }
}

function resetForm(form){
    form.onchange = null;
    for (element of form.elements){
        resetValue(element)
    }
    evaluateManagedForm(form)
    form.onchange = () => evaluateManagedForm(form);
}

function evaluateCreationForm(form){
    const changes = getFormChanges(form);

    if(getActualElements(form).filter(elem => elem.hasAttribute('required')).every(elem => elem.value)){
        form.querySelector('[type=submit]').disabled = false;
    }else{
        form.querySelector('[type=submit]').disabled = true;
    }
}

for(const form of document.forms){
    if(form.classList.contains('managedForm') && form.querySelector('[type=submit]')){
        // console.log(form);
        form.onchange = () => evaluateManagedForm(form);
        form.onsubmit = () => {
            window.onbeforeunload = null;
            confirmed = confirm('Bekreft endringer: \n' + getFormChanges(form).map(change => change.changeText).join('\n'))
            if(!confirmed){
                window.onbeforeunload = function() {
                    return 'Anbefaler å lagre endringene før du forlater siden:)';
                };
            }
            return confirmed;
        };
    
        evaluateManagedForm(form);

    }else if(form.classList.contains('creationForm') && form.querySelector('[type=submit]')){
        form.onchange = () => evaluateCreationForm(form);
        form.onsubmit = () => {
            return confirm('Bekreft endringer: \n' + formatFormChanges(getFormChanges(form)).join('\n'))
        };
    
        evaluateCreationForm(form);
    }
}

// managedForm html:
/*
        <input type='button' value='Angre' onclick='resetForm(this.form)'>
        <input type='submit' value='Lagre'>
*/

// creationForm html:
/*
    <input type='submit' value='Lagre'>
*/