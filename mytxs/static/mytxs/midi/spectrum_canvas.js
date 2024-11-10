let canvas;
let ctx;

export function initCanvas() {
    canvas = document.getElementById('spectrumCanvas');
    ctx = canvas.getContext('2d');
}

export function clearCanvas() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
}

// export function drawXAxis(numBins, fs) {
//     const freqLabels = [];
//     for (let i = 0; i < numBins; i++) {
//         const freq = binToFreq(i, fs, RECORD.FFT_SIZE);
//         // Display frequencies in increments, for example, every 20th bin
//         if (i % 200 === 0) {
//             freqLabels.push({ x: i * barWidth, freq: freq });
//         }
//     }
//     ctx.font = "12px Arial";
//     ctx.fillStyle = "#000";
//     freqLabels.forEach(label => {
//         ctx.fillText(`${Math.round(label.freq)} Hz`, label.x, canvas.height - 5);
//     });
// }

export function drawSpectrum(spectrum, numBins) {
    const barWidth = canvas.width / numBins;
    for (let i = 0; i < numBins; i++) {
        const barHeight = spectrum[i];
        ctx.fillStyle = `rgb(${barHeight + 100}, 50, 50)`; // Color bars based on magnitude
        ctx.fillRect(i * barWidth, canvas.height - barHeight, barWidth, barHeight);
    }
}

// export function drawTargets(activeTones) {
//     for (const tone of activeTones) {
//         const freq = toneToFreq(tone);
//         const closestBin = freqToClosestBin(freq);
//         ctx.fillStyle = `rgb(50, 100, 50)`; // Color bars based on magnitude
//         ctx.fillRect(closestBin * barWidth, 0, barWidth, canvas.height);
//     }
// }

