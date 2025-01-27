if(document.currentScript.dataset.json){
    const medlemMapData = JSON.parse(document.currentScript.dataset.json);
    const markerMapping = {};

    const map = L.map('map').setView([63.42256257910649, 10.395544839649341], 13);
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '<a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>'
    }).addTo(map);

    function strCord(cord){
        return cord['lat'] + '' + cord['lon'];
    }

    function addAdressToMap(medlem, cord, suffix=''){
        if(markerMapping[strCord(cord)]){
            const marker = markerMapping[strCord(cord)];
            marker.bindPopup(marker._popup._content + '<br>' + `<a href="/sjekkheftet/${medlem.storkorNavn}#m_${medlem.pk}">${medlem.navn}${suffix}</a>`);
        }else{
            const marker = L.marker([cord.lat, cord.lon]).addTo(map);
            marker.bindPopup(`<a href="/sjekkheftet/${medlem.storkorNavn}#m_${medlem.pk}">${medlem.navn}${suffix}</a>`);
            markerMapping[strCord(cord)] = marker;
        }
    }

    for(const medlem of medlemMapData){
        if(medlem.boCord){
            addAdressToMap(medlem, medlem.boCord);
        }
        if(medlem.foreldreCord){
            addAdressToMap(medlem, medlem.foreldreCord, suffix=' (hjemme)');
        }
    }
}