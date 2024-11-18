import { SCORE } from "./constants.js";
import { getLargestMagnitude, getMagnitude } from "./record.js";

export function toneToFreq(tone) {
    return SCORE.BASE_HZ * 2 ** ((tone - SCORE.BASE_TONE) / 12);
}

// https://stackoverflow.com/questions/62615983/why-is-the-highest-fft-peak-not-the-fundamental-frequency-of-a-musical-tone
export function scoreGet(activeTones) {
    let bestScore = 0.0;
    for (const tone of activeTones) {
        const targetFreq = toneToFreq(tone);
        const magnitude = getMagnitude(targetFreq);
        const largestMagnitude = getLargestMagnitude();
        const relativeMagnitude = magnitude/largestMagnitude;
        if (relativeMagnitude > SCORE.RELATIVE_MAGNITUDE_LIMIT && relativeMagnitude > bestScore) {
            bestScore = relativeMagnitude;
        }
    }
    return bestScore;
}
