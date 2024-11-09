import { getLargestMagnitude, getMagnitude } from "./record.js";

const SINGSTAR_SCORE = {
    BASE_HZ: 440,
    BASE_TONE: 69,
    RELATIVE_MAGNITUDE_LIMIT: 0.9,
}

function toneToFreq(tone) {
    return SINGSTAR_SCORE.BASE_HZ * 2 ** ((tone - SINGSTAR_SCORE.BASE_TONE) / 12);
}

// https://stackoverflow.com/questions/62615983/why-is-the-highest-fft-peak-not-the-fundamental-frequency-of-a-musical-tone
export function singstarScore(activeTones) {
    let bestScore = 0.0;
    for (const tone of activeTones) {
        const targetFreq = toneToFreq(tone);
        const magnitude = getMagnitude(targetFreq);
        const largestMagnitude = getLargestMagnitude();
        const relativeMagnitude = magnitude/largestMagnitude;
        if (relativeMagnitude > SINGSTAR_SCORE.RELATIVE_MAGNITUDE_LIMIT && relativeMagnitude > bestScore) {
            bestScore = relativeMagnitude;
        }
    }
    return bestScore;
}
