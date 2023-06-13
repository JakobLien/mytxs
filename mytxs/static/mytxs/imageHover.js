/*  Når man hoverer på et bilde gjør denne fila at man kan se bildet on hover. Særlig 
    tenkt å brukes på imageField på medlem sida, men virke nyttig ellers også tenke e. 
    Dimensjonan på hover bildet matche sjekkheftet dimensjonan. 
 */

for(const a of document.querySelectorAll("a[href]")){
    hrefText = a.getAttribute('href')
    if(!(hrefText.endsWith('.jpg') || hrefText.endsWith('.png') || hrefText.endsWith('.webp'))){
        continue;
    }

    let image = document.createElement("img")
    image.setAttribute('src', hrefText);

    a.classList.add('group', 'relative');
    image.classList.add("hidden", "group-hover:block", "absolute", 'z-10', '-right-2', 'bottom-4', 'h-44', 'aspect-[139/169]', "object-cover", "p-2", "bg-customPurple", "rounded-lg");

    a.appendChild(image)
}