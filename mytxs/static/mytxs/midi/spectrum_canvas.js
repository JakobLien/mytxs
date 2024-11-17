import { freqToClosestBin } from "./record.js";
import { toneToFreq } from "./singstar_score.js";

const DISPLAY_MAX_FREQ = 2093;

let canvas;
let ctx;
let displayBins;

export function initCanvas() {
    canvas = document.getElementById('spectrumCanvas');
    ctx = canvas.getContext('2d');
    displayBins = freqToClosestBin(DISPLAY_MAX_FREQ);
}

export function clearCanvas() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
}

export function drawSpectrum(spectrum) {
    const barWidth = canvas.width / displayBins;
    for (let i = 0; i < displayBins; i++) {
        const barHeight = spectrum[i];
        ctx.fillStyle = `rgb(${barHeight + 100}, 50, 50)`; // Color bars based on magnitude
        ctx.fillRect(i * barWidth, canvas.height - barHeight, barWidth, barHeight);
    }
}

export function drawTargets(activeTones) {
    const barWidth = canvas.width / displayBins;
    for (const tone of activeTones) {
        const freq = toneToFreq(tone);
        const closestBin = freqToClosestBin(freq);
        ctx.fillStyle = `rgb(50, 100, 50)`; // Color bars based on magnitude
        ctx.fillRect(closestBin * barWidth, 0, barWidth, canvas.height);
    }
}

