import { SCORE } from "./constants.js";
import { freqFromTone, freqGetLargestMagnitude, freqGetMagnitude } from "./freq.js";

// https://stackoverflow.com/questions/62615983/why-is-the-highest-fft-peak-not-the-fundamental-frequency-of-a-musical-tone
export function scoreGet(activeTones) {
    let bestScore = 0.0;
    for (const tone of activeTones) {
        const targetFreq = freqFromTone(tone);
        const magnitude = freqGetMagnitude(targetFreq);
        const largestMagnitude = freqGetLargestMagnitude();
        const relativeMagnitude = magnitude/largestMagnitude;
        if (relativeMagnitude > SCORE.RELATIVE_MAGNITUDE_LIMIT && relativeMagnitude > bestScore) {
            bestScore = relativeMagnitude;
        }
    }
    return bestScore;
}
