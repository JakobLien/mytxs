import {PLAYER} from './player_constants.js';

export function createMasterUi(songDuration, songBars, progressCallback, barNumberCallback, tempoBarCallback, pauseCallback) {
    const uiDiv = document.createElement("div");

    const progressSpan = document.createElement("span");
    progressSpan.innerText = usToMinSec(0);
    progressSpan.id = "progressSpan";
    uiDiv.appendChild(progressSpan);

    const durationSpan = document.createElement("span");
    durationSpan.innerText = "".concat(" / ", usToMinSec(songDuration));
    uiDiv.appendChild(durationSpan);

    const progressBar = document.createElement("input");
    progressBar.type = "range";
    progressBar.id = "progressBar";
    progressBar.min = 0;
    progressBar.max = songDuration;
    progressBar.value = 0;
    progressBar.oninput = progressCallback;
    uiDiv.appendChild(progressBar);

    const barLabel = document.createElement("label");
    barLabel.innerText = "Bar";
    uiDiv.appendChild(barLabel);

    const barNumber = document.createElement("input");
    barNumber.type = "number";
    barNumber.id = "barNumber";
    barNumber.min = 0; // 1?
    barNumber.max = songBars;
    barNumber.value = 0;
    barNumber.oninput = barNumberCallback;
    uiDiv.appendChild(barNumber);

    const tempoLabel = document.createElement("label");
    tempoLabel.innerText = "Tempo";
    uiDiv.appendChild(tempoLabel);

    const tempoBar = document.createElement("input");
    tempoBar.type = "range";
    tempoBar.min = PLAYER.TEMPO.MIN;
    tempoBar.max = PLAYER.TEMPO.MAX;
    tempoBar.value = PLAYER.TEMPO.DEFAULT;
    tempoBar.step = PLAYER.TEMPO.STEP;
    tempoBar.oninput = tempoBarCallback;
    uiDiv.appendChild(tempoBar);

    // TODO
    // let volumeLabel = document.createElement("label");
    // volumeLabel.innerText = "Master volume";
    // uiDiv.appendChild(volumeLabel);

    // let volumeSlider = document.createElement("input");
    // volumeSlider.type = "range";
    // volumeSlider.min = 0;
    // volumeSlider.max = 100;
    // volumeSlider.value = 50;
    // uiDiv.appendChild(volumeSlider);

    const pauseButton = document.createElement("button");
    pauseButton.innerText = "Play";
    pauseButton.onclick = pauseCallback;
    uiDiv.appendChild(pauseButton);

    return uiDiv;
}

export function createTrackUi(label, volumeCallback, panningCallback, muteCallback) {
    const uiDiv = document.createElement("div");
    uiDiv.innerText = label;

    const volumeLabel = document.createElement("label");
    volumeLabel.innerText = "Volume";
    uiDiv.appendChild(volumeLabel);

    const volumeSlider = document.createElement("input");
    volumeSlider.type = "range";
    volumeSlider.min = PLAYER.VOLUME.MIN;
    volumeSlider.max = PLAYER.VOLUME.MAX;
    volumeSlider.value = PLAYER.VOLUME.MAX;
    volumeSlider.oninput = volumeCallback;
    uiDiv.appendChild(volumeSlider);

    const panningLabel = document.createElement("label");
    panningLabel.innerText = "Panning";
    uiDiv.appendChild(panningLabel);

    const panningSlider = document.createElement("input");
    panningSlider.type = "range";
    panningSlider.min = PLAYER.PAN.MIN;
    panningSlider.max = PLAYER.PAN.MAX;
    panningSlider.value = (PLAYER.PAN.MIN + PLAYER.PAN.MAX) / 2;
    panningSlider.oninput = panningCallback;
    uiDiv.appendChild(panningSlider);

    const muteButton = document.createElement("button");
    muteButton.innerText = "Mute";
    muteButton.onclick = muteCallback;
    uiDiv.appendChild(muteButton);

    return uiDiv;
}

function usToMinSec(us) {
    const secs = us/1000000;
    const mins = Math.trunc(secs/60);
    const overshootingSecs = Math.trunc(secs % 60);
    return "".concat(mins, overshootingSecs < 10 ? ":0" : ":", overshootingSecs);
}

export function uiSetProgress(time, bar) {
    const progressBar = document.getElementById("progressBar");
    progressBar.value = time;
    const progressSpan = document.getElementById("progressSpan");
    progressSpan.innerText = usToMinSec(time);
    const barNumber = document.getElementById("barNumber");
    barNumber.value = Math.floor(bar);
}
