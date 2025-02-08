import { freqFromTone, freqToClosestBin, MAX_MAGNITUDE } from "./freq.js";
import { CANVAS } from "./constants.js";

let canvas;
let ctx;
let displayBins;

export function canvasInit() {
    canvas = document.getElementById('spectrumCanvas');
    ctx = canvas.getContext('2d');
    displayBins = freqToClosestBin(CANVAS.MAX_FREQ);
}

export function canvasClear() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
}

export function canvasDrawSpectrum(spectrum) {
    const barWidth = canvas.width / displayBins;
    for (let i = 0; i < displayBins; i++) {
        const barHeight = spectrum[i] / MAX_MAGNITUDE * canvas.height;
        ctx.fillStyle = `rgb(${barHeight + CANVAS.BASE_COLOR.R}, ${CANVAS.BASE_COLOR.G}, ${CANVAS.BASE_COLOR.B})`; // Color bars based on magnitude
        ctx.fillRect(i * barWidth, canvas.height - barHeight, barWidth, barHeight);
    }
}

export function canvasDrawTargets(activeTones) {
    const barWidth = canvas.width / displayBins;
    for (const tone of activeTones) {
        const freq = freqFromTone(tone);
        const closestBin = freqToClosestBin(freq);
        ctx.fillStyle = `rgb(${CANVAS.TARGET_COLOR.R}, ${CANVAS.TARGET_COLOR.G}, ${CANVAS.TARGET_COLOR.B})`; // Color bars based on magnitude
        ctx.fillRect(closestBin * barWidth, 0, barWidth, canvas.height);
    }
}

