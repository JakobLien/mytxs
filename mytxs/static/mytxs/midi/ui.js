import { MIDI, PLAYER, SCORE } from './constants.js';

export function uiPopulateMasterUi(songDuration, songBars, progressCallback, barNumberCallback, tempoBarCallback, pauseCallback, loopStartCallback, loopEndCallback, loopActiveCallback) {
    const progressSpan = document.getElementById("progressSpan");
    progressSpan.innerText = usToMinSec(0);

    const durationSpan = document.getElementById("durationSpan");
    durationSpan.innerText = "".concat(" / ", usToMinSec(songDuration));

    const progressBar = document.getElementById("progressBar");
    progressBar.min = 0;
    progressBar.max = songDuration;
    progressBar.value = 0;
    progressBar.oninput = progressCallback;

    const barNumber = document.getElementById("barNumber");
    barNumber.min = 0; // 1?
    barNumber.max = songBars;
    barNumber.value = 0;
    barNumber.oninput = barNumberCallback;

    const tempoBar = document.getElementById("tempoBar");
    tempoBar.min = PLAYER.TEMPO.MIN;
    tempoBar.max = PLAYER.TEMPO.MAX;
    tempoBar.value = PLAYER.TEMPO.DEFAULT;
    tempoBar.step = PLAYER.TEMPO.STEP;
    tempoBar.oninput = tempoBarCallback;

    const pauseButton = document.getElementById("pauseButton");
    pauseButton.onclick = pauseCallback;

    const loopStartNumber = document.getElementById("loopStartNumber");
    loopStartNumber.min = 0;
    loopStartNumber.max = songBars;
    loopStartNumber.value = 0;
    loopStartNumber.oninput = loopStartCallback;

    const loopEndNumber = document.getElementById("loopEndNumber");
    loopEndNumber.min = 0;
    loopEndNumber.max = songBars;
    loopEndNumber.value = songBars;
    loopEndNumber.oninput = loopEndCallback;

    const loopActive = document.getElementById("loopActive");
    loopActive.oninput = loopActiveCallback;
}

export function uiPopulateSingstarUi(songDuration, songBars, tracks, trackSelectCallback, startCallback) {
    const progressSpan = document.getElementById("progressSpan");
    progressSpan.innerText = usToMinSec(0);

    const durationSpan = document.getElementById("durationSpan");
    durationSpan.innerText = "".concat(" / ", usToMinSec(songDuration));

    const progressBar = document.getElementById("progressBar");
    progressBar.min = 0;
    progressBar.max = songDuration;
    progressBar.value = 0;

    const barNumber = document.getElementById("barNumber");
    barNumber.min = 0; // 1?
    barNumber.max = songBars;
    barNumber.value = 0;

    const trackSelect = document.getElementById("trackSelect");
    trackSelect.oninput = trackSelectCallback;
    for (const track of tracks) {
        if (track.event.every(e => e.type != MIDI.MESSAGE_TYPE_NOTEON)) {
            continue;
        }
        const option = document.createElement("option");
        option.value = track.trackId;
        option.innerText = track.label;
        trackSelect.appendChild(option);
    }

    const startButton = document.getElementById("startButton");
    startButton.onclick = startCallback;
}

export function uiSetStartButtonText(text) {
    const startButton = document.getElementById("startButton");
    startButton.innerText = text;
}

export function uiCreateTrackUi(label, volumeCallback, balanceCallback, muteCallback, soloCallback) {
    const trackUiDiv = document.createElement("div");
    trackUiDiv.innerText = label;

    const volumeLabel = document.createElement("label");
    volumeLabel.innerText = "Volume";
    trackUiDiv.appendChild(volumeLabel);

    const volumeSlider = document.createElement("input");
    volumeSlider.type = "range";
    volumeSlider.min = PLAYER.VOLUME.MIN;
    volumeSlider.max = PLAYER.VOLUME.MAX;
    volumeSlider.value = PLAYER.VOLUME.DEFAULT;
    volumeSlider.oninput = volumeCallback;
    trackUiDiv.appendChild(volumeSlider);

    const balanceLabel = document.createElement("label");
    balanceLabel.innerText = "Balance";
    trackUiDiv.appendChild(balanceLabel);

    const balanceSlider = document.createElement("input");
    balanceSlider.type = "range";
    balanceSlider.min = PLAYER.BALANCE.MIN;
    balanceSlider.max = PLAYER.BALANCE.MAX;
    balanceSlider.value = PLAYER.BALANCE.DEFAULT;
    balanceSlider.oninput = balanceCallback;
    trackUiDiv.appendChild(balanceSlider);

    const muteButton = document.createElement("button");
    muteButton.innerText = "Mute";
    muteButton.onclick = muteCallback;
    trackUiDiv.appendChild(muteButton);

    const soloButton = document.createElement("input");
    soloButton.type = "radio";
    soloButton.name = "soloButton";
    soloButton.onclick = soloCallback;
    trackUiDiv.appendChild(soloButton);

    const trackUiDivs = document.getElementById("trackUiDivs");
    trackUiDivs.appendChild(trackUiDiv);
}

function usToMinSec(us) {
    const secs = us/1000000;
    const mins = Math.trunc(secs/60);
    const overshootingSecs = Math.trunc(secs % 60);
    return "".concat(mins, overshootingSecs < 10 ? ":0" : ":", overshootingSecs);
}

export function uiSetSongName(songName) {
    const songNameHeader = document.getElementById("songNameHeader");
    songNameHeader.innerText = songName;
}

export function uiSetProgress(time, bar) {
    const progressBar = document.getElementById("progressBar");
    progressBar.value = time;
    const progressSpan = document.getElementById("progressSpan");
    progressSpan.innerText = usToMinSec(time);
    const barNumber = document.getElementById("barNumber");
    barNumber.value = Math.floor(bar);
}

export function uiSetScore(score) {
    const scoreSpan = document.getElementById("scoreSpan");
    scoreSpan.innerText = score.toFixed(SCORE.DISPLAY_DECIMALS);
}

export function uiSetHighscore(highscore) {
    const highscoreSpan = document.getElementById("highscoreSpan");
    highscoreSpan.innerText = highscore.toFixed(SCORE.DISPLAY_DECIMALS);
}

export function uiReset() {
    // Intentionally empty
}
