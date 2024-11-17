import { MIDI } from './constants.js';

export function tickstampEvents(trackEvents) {
    let ticks = 0;
    for (const e of trackEvents) {
        ticks += e.deltaTime;
        e.ticks = ticks;
    }
}

// Events must be sorted so that tempo and time signatures are accounted for
export function timestampEvents(allEvents, ticksPerBeat) {
    let microsecondsPerBeat = 60000000/MIDI.DEFAULT_BPM;
    let beatsPerBar = MIDI.DEFAULT_BEATS_PER_BAR;
    let time = 0;
    let bar = 0;
    let lastTicks = 0;
    for (const e of allEvents) {
        const deltaTicks = e.ticks - lastTicks;
        const beats = deltaTicks/ticksPerBeat;
        time += beats*microsecondsPerBeat;
        bar += beats/beatsPerBar;
        e.timestamp = time;
        e.bar = bar;
        if (e.metaType == MIDI.METATYPE_SET_TEMPO) {
            microsecondsPerBeat = e.data;
        } else if (e.metaType == MIDI.METATYPE_TIME_SIGNATURE) {
            const _32ndNotesPerBeat = e.data[3];
            const _32ndNotesPerBar = e.data[0]*2**(5 - e.data[1]);
            beatsPerBar = _32ndNotesPerBar/_32ndNotesPerBeat;
        }
        lastTicks = e.ticks;
    }
}
