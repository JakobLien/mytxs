import { arrayInterpolate, arrayStartingIndex } from './array_utils.js';

export function startingIndexFromTime(allEvents, time) {
    return arrayStartingIndex(allEvents, 'timestamp', time);
}

export function startingIndexFromBar(allEvents, bar) {
    return arrayStartingIndex(allEvents, 'bar', bar);
}

export function barToTime(allEvents, highIndex, bar) {
    return arrayInterpolate(allEvents, highIndex, 'bar', 'timestamp', bar);
}

export function timeToBar(allEvents, highIndex, time) {
    return arrayInterpolate(allEvents, highIndex, 'timestamp', 'bar', time);
}
