import { EPS } from './constants.js';

// Binary search for index of the first event with element[attr] >= value. Returns last index if none exist
// Assumes that array elements are sorted with respect to the value of attr
export function arrayStartingIndex(array, attr, value) {
    if (array.length == 0) {
        return -1;
    } else if (array[0][attr] >= value) { // All events have element[attr] >= value
        return 0;
    } else if (array[array.length - 1][attr] < value) { // No events have element[attr] >= value
        return array.length - 1;
    } else {
        // Binary search for first index with element[attr] >= value
        let low = 0;
        let high = array.length;
        while (high > low + 1) {
            const mid = Math.trunc((low + high)/2); // Fast integer division
            if (array[mid][attr] >= value) {
                high = mid;
            } else {
                low = mid;
            }
        }
        return high;
    }
}

export function arrayInterpolate(array, high, xAttr, yAttr, x) {
    if (high == 0) {
        return array[0][yAttr];
    }
    const low = high - 1;

    const x0 = array[low][xAttr];
    const x1 = array[high][xAttr];
    const y0 = array[low][yAttr];
    const y1 = array[high][yAttr];

    const dy = y1 - y0;
    const dx = x1 - x0;

    if (dx < EPS) {
        return y0;
    }

    return y0 + (x - x0)* dy / dx;
}
