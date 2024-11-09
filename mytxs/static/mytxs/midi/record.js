// https://developer.mozilla.org/en-US/docs/Web/API/AnalyserNode

const RECORD = {
    FFT_SIZE: 4096, // Roughly 0.1 s at a sampling frequency of 44100 Hz
    GAIN: 1.0, // Ideally the user should give a reasonably configured microphone
    MIN_DECIBELS: -100,
    MAX_DECIBELS: -20,
};

let spectrum;
let numBins;
let fs;

function binToFreq(k, fs, n) {
    return k*fs/n;
}

function freqToClosestBin(f, fs, n) {
    return Math.round(n*f/fs);
}

export function getLargestMagnitude() {
    let max = 0;
    for (let i = 0; i < numBins; i++) {
        if (max < spectrum[i]) {
            max = spectrum[i];
        }
    }
    return max;
}

export function getMagnitude(freq) {
    const closestBin = freqToClosestBin(freq, fs, RECORD.FFT_SIZE);
    return closestBin < numBins ? spectrum[closestBin] : 0;
}

export function startRecording(triggerElement, triggerEventType) {
    // Check for browser support
    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        // Create audio context and start trigger
        const audioContext = new (window.AudioContext || window.webkitAudioContext)();
        triggerElement.addEventListener(triggerEventType, () => audioContext.resume());
        fs = audioContext.sampleRate;

        // Configure nodes
        const analyser = audioContext.createAnalyser();
        const gain = audioContext.createGain();
        gain.gain.value = RECORD.GAIN;
        analyser.fftSize = RECORD.FFT_SIZE;
        analyser.minDecibels = RECORD.MIN_DECIBELS;
        analyser.maxDecibels = RECORD.MAX_DECIBELS;

        // Initialize spectrum buffer
        numBins = analyser.frequencyBinCount; // FFT_SIZE/2
        spectrum = new Uint8Array(numBins);


        // Access the microphone and connect to analyser node
        navigator.mediaDevices.getUserMedia({ audio: true }).then(stream => {
            const source = audioContext.createMediaStreamSource(stream);
            source.connect(gain);
            gain.connect(analyser);

            function captureAudioData() {
                requestAnimationFrame(captureAudioData); // Repeat in next animation frame
                // analyser.getByteTimeDomainData(spectrum);
                // console.log(spectrum);
                analyser.getByteFrequencyData(spectrum);
            }

            captureAudioData(); // Start capturing audio data
        }).catch(err => {
            console.error('Error accessing audio stream:', err);
        });
    } else {
        console.error('getUserMedia not supported in this browser.');
    }
}
