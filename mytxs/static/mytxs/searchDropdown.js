/*  For alle <select> menyer gjør denne fila at du kan søke på alternativ. 
    For multiselect (type="multiple") gjør denne fila også at toggle er default.
 */

for(const select of document.querySelectorAll('select')){
    if(select.form.classList.contains('skipSearchDropdown')){
        continue;
    }

    // Lag elementan
    const parent = document.createElement('div');
    const input = document.createElement('input');
    input.setAttribute('type', 'text')
    const div = document.createElement('div');

    // Sett element på rett plass
    select.parentNode.replaceChild(parent, select);
    parent.append(select, input, div);

    // Style dem
    parent.classList.add('inline', 'relative');
    select.classList.add('hidden');

    input.classList.add('peer', 'mb-0');
    if (select.hasAttribute('disabled') || Array.from(select.options).every(o => o.hasAttribute('disabled'))){
        input.classList.add('opacity-40');
    }

    div.classList.add('absolute', 'z-10', 'left-0', 'hidden', 'peer-focus:block', 'hover:block', 'm-0', 
        'bg-white', 'border-black', 'border',
        'max-h-52', 'overflow-scroll', 'min-w-full',
        '[&>*]:mx-1', '[&>*]:mr-3', '[&>*]:text-sm');

    // Gjør at click i div ikkje fjerne focus fra input
    div.onmousedown = e => {
        e.preventDefault();
        e.stopPropagation();
    }

    // På input endring, utfør søk
    input.oninput = e => {
        // Clear div options
        while(div.lastChild){
            div.removeChild(div.lastChild);
        }
        // Populate select options
        for(const selectOption of select.options){
            if(input.value.split(' ').filter(s => s).map(s => s.toLowerCase()).some(s => (
                s === '!' ? !selectOption.selected : !selectOption.text.toLowerCase().includes(s)
            ))){
                continue;
            }
            const divOption = document.createElement('div');
            if(selectOption.selected){
                divOption.classList.add('bg-gray-300');
            }

            // Handle click on options
            divOption.onmousedown = e => {
                if(select.disabled || selectOption.disabled){
                    return;
                }
                if(!select.hasAttribute('multiple')){
                    [...div.childNodes].map(divOpt => divOpt.classList.remove('bg-gray-300'));  
                }
                selectOption.selected = !selectOption.selected;
                divOption.classList.toggle('bg-gray-300');
                select.onchange ? select.onchange() : null;
            }

            divOption.innerText = selectOption.text
            div.appendChild(divOption)
        }
    };

    // På input focus, clear verdien og utfør søk
    input.onfocus = e => {
        if(input.getBoundingClientRect().top/window.innerHeight >= 0.6 != div.classList.contains('bottom-5')){
            div.classList.toggle('bottom-5');
        }

        input.value = '';
        input.oninput();
    };

    // På input blur, sett placeholder verdi og fjern alle optionsa
    input.onblur = e => {
        input.value = getValue(select);
        while(div.lastChild){
            div.removeChild(div.lastChild);
        }

        // På forms som submittes automatisk submitte vi istedet når dem lukke multiselect menyen
        if(select.hasAttribute('multiple') && select.form.getAttribute('onchange') === 'this.submit()' && !arrayEqual(getValue(select), getInitialValue(select))){
            select.form.onchange();
        }
    };
    input.onblur();

    // På endring av select verdien, oppdater placeholder
    select.onchange = e => {
        if(document.activeElement !== input) {
            input.value = getValue(select);
        }

        // På forms som submittes automatisk submitte vi istedet når dem lukke multiselect menyen
        if(!(select.hasAttribute('multiple') && select.form.getAttribute('onchange') === 'this.submit()')){
            select.form.onchange ? select.form.onchange() : null;
        }
    };
}