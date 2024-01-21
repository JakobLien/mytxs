if(document.currentScript.dataset.json){
    const medlemMapData = JSON.parse(document.currentScript.dataset.json);

    const map = L.map('map').setView([63.42256257910649, 10.395544839649341], 13);
    L.tileLayer('https://opencache.statkart.no/gatekeeper/gk/gk.open_gmaps?layers=norges_grunnkart&zoom={z}&x={x}&y={y}', {
        attribution: '<a href="http://www.kartverket.no/">Kartverket</a>'
    }).addTo(map);

    async function getCord(adresse){
        const cord = await fetch('https://ws.geonorge.no/adresser/v1/sok?sok='+adresse).then(
            response => response.json(),
        );
        if(cord.adresser.length == 0){return false};
        return cord.adresser[0].representasjonspunkt;
    }

    async function addAdressToMap(medlem, adresse){
        const cord = await getCord(adresse);
        if(!cord){return};
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