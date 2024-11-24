if(document.currentScript.dataset.json){
    const medlemMapData = JSON.parse(document.currentScript.dataset.json);

    const map = L.map('map').setView([63.42256257910649, 10.395544839649341], 13);
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '<a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>'
    }).addTo(map);

    function addAdressToMap(medlem, cord){
        const marker = L.marker([cord.lat, cord.lon]).addTo(map);
        marker.bindPopup(`<a href="/sjekkheftet/${medlem.storkorNavn}#m_${medlem.pk}">${medlem.navn}</a>`);
    }
    
    for(const medlem of medlemMapData){
        if(medlem.boAdresse){
            addAdressToMap(medlem, medlem.boAdresse);
        }
        if(medlem.foreldreAdresse){
            addAdressToMap(medlem, medlem.foreldreAdresse);
        }
    }
}