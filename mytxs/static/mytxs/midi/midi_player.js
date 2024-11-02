import {MIDI} from './midi_constants.js';
import {PLAYER} from './player_constants.js';
import {MidiParser} from './midi-parser.js'; 
import {tickstampEvents, timestampEvents} from './event_timing.js';
import {createMasterUi, createTrackUi, uiSetProgress} from './ui.js';

let jumpTime = null;
let jumpBar = null;
let paused = true;
let tempo = PLAYER.TEMPO.DEFAULT;
const trackMuted = new Map();
let soloTrack = null;

function volumeChannel(output, channel, value) {
    output.send([(MIDI.MESSAGE_TYPE_CHANNEL_MODE << MIDI.STATUS_MSB_OFFSET) | channel, MIDI.MODE_VOLUME, value])
}

function panChannel(output, channel, value) {
    output.send([(MIDI.MESSAGE_TYPE_CHANNEL_MODE << MIDI.STATUS_MSB_OFFSET) | channel, MIDI.MODE_PAN, value])
}

function silenceChannel(output, channel) {
    output.send([(MIDI.MESSAGE_TYPE_CHANNEL_MODE << MIDI.STATUS_MSB_OFFSET) | channel, MIDI.MODE_ALL_SOUND_OFF, 0])
}

function silenceAll(output) {
    for (let channel = 0; channel < MIDI.NUM_CHANNELS; channel++) {
        silenceChannel(output, channel);
    }
}

function eventSendable(trackMuted, soloTrack, event) {
    switch (event.type) {
        case MIDI.MESSAGE_TYPE_META:
            return false;
        case MIDI.MESSAGE_TYPE_NOTEON:
            return !trackMuted.get(event.trackId) && (soloTrack == null || soloTrack == event.trackId);
        case MIDI.MESSAGE_TYPE_CHANNEL_MODE:
            switch (event.data[0]) { 
                // Return false for all events meant to be controlled by user
                case MIDI.MODE_PAN:
                case MIDI.MODE_VOLUME:
                    return false;
                default:
                    return true;
            }
        default:
            return true;
    }
}

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

function startingIndexFromTime(allEvents, time) {
    let low = 0;
    let high = allEvents.length;
    while (high > low + 1) {
        const mid = Math.trunc((low + high)/2); // Fast integer division
        if (allEvents[mid].timestamp >= time) {
            high = mid;
        } else {
            low = mid;
        }
    }
    return low;
}

function startingIndexFromBar(allEvents, bar) {
    let low = 0;
    let high = allEvents.length;
    while (high > low + 1) {
        const mid = Math.trunc((low + high)/2); // Fast integer division
        if (allEvents[mid].bar >= bar) {
            high = mid;
        } else {
            low = mid;
        }
    }
    return low;
}

async function playRealtime(obj, output) {
    if (obj.formatType != MIDI.FORMAT_TYPE_MULTITRACK) {
        alert("".concat(source, " har et ugyldig format: ", obj.formatType));
    }

    if (obj.timeDivision & (1 << MIDI.TIME_DIVISION_TICKS_PER_BEAT)) {
        alert("".concat(source, " har et ugyldig tempoformat: ", obj.timeDivision));
    }
    const ticksPerBeat = obj.timeDivision;

    // Process events into a playable format
    const allEvents = [];
    for (const i in obj.track) {
        const events = obj.track[i].event;

        for (const e of events) {
            e.trackId = i;
        }

        tickstampEvents(events);
        allEvents.push(...events);
    }
    allEvents.sort((e1, e2) => e1.ticks == e2.ticks ? e1.type - e2.type : e1.ticks - e2.ticks); // Sorted by ticks and event type, so that noteoff happens before noteon
    timestampEvents(allEvents, ticksPerBeat);

    // Create song name header
    const songNameHeader = document.createElement("h1");
    songNameHeader.innerText = "Nameless";
    for (const e of obj.track[0].event) {
        if (e.metaType == MIDI.METATYPE_TRACK_NAME) {
            songNameHeader.innerText = e.data;
            break;
        }
    }
    document.getElementById("content").appendChild(songNameHeader);

    // Create master UI
    const songDuration = allEvents[allEvents.length - 1].timestamp;
    const songBars = Math.floor(allEvents[allEvents.length - 1].bar);
    const progressCallback = (e) => jumpTime = e.target.value;
    const barNumberCallback = (e) => jumpBar = e.target.value;
    const tempoBarCallback = (e) => tempo = e.target.value;
    const pauseCallback = (e) => {
        if (!paused) {
            silenceAll(output);
        }
        e.target.innerText = paused ? "Pause" : "Play";
        paused = !paused;
    };
    const masterUi = createMasterUi(songDuration, songBars, progressCallback, barNumberCallback, tempoBarCallback, pauseCallback);
    document.getElementById("content").appendChild(masterUi);

    // Create UI for tracks which have noteon events
    for (let i = 0; i < obj.track.length; i++) {
        const track = obj.track[i];

        if (track.event.every((e) => e.type != MIDI.MESSAGE_TYPE_NOTEON)) {
            continue;
        }

        const trackName = track.event[0].data;
        const pattern = /sopran|alt|tenor|bass/i;
        if (String(trackName).match(pattern) !== null) {
            track.label = trackName;
        } else { 
            track.label = "Track " + i;
        }

        const trackId = track.event[0].trackId;
        const volumeCallback = (e) => volumeChannel(output, trackId, e.target.value);
        const panningCallback = (e) => panChannel(output, trackId, e.target.value);
        trackMuted.set(trackId, false);
        const muteCallback = (e) => {
            const wasMuted = trackMuted.get(trackId);
            if (!wasMuted) {
                silenceChannel(output, trackId);
            }
            e.target.innerText = wasMuted ? "Mute" : "Unmute";
            trackMuted.set(trackId, !wasMuted);
        };
        const soloCallback = (e) => {
            if (soloTrack == trackId) {
                e.target.checked = false;
                soloTrack = null;
            } else {
                soloTrack = trackId;
            }
        };
        const trackUi = createTrackUi(track.label, volumeCallback, panningCallback, muteCallback, soloCallback);
        document.getElementById("content").appendChild(trackUi);
    }

    // Play
    while (true) {
        let time = 0;
        let i = 0;
        while (i < allEvents.length) {
            // Check for player jumps
            if (jumpTime !== null) {
                silenceAll(output);
                i = startingIndexFromTime(allEvents, jumpTime);
                time = jumpTime; // Better than allEvents[i].time, because this allows jumps to the middle of long notes
                uiSetProgress(time, allEvents[i].bar);
                jumpTime = null;
                await sleep(1000); // TODO
            } else if (jumpBar !== null) {
                silenceAll(output);
                i = startingIndexFromBar(allEvents, jumpBar);
                time = allEvents[i].time;
                uiSetProgress(time, allEvents[i].bar);
                jumpBar = null;
                await sleep(1000); // TODO
            }
            // Play if not paused
            if (paused) {
                await sleep(1000); // TODO
            } else {
                const e = allEvents[i];
                uiSetProgress(e.timestamp, e.bar);
                const dt = e.timestamp - time;
                if (dt != 0) {
                    await sleep(dt/1000/tempo);
                }
                // Consider whether to actually send message
                if (eventSendable(trackMuted, soloTrack, e)) {
                    const message = [(e.type << MIDI.STATUS_MSB_OFFSET) | e.trackId];
                    const data = Array.isArray(e.data) ? e.data : [e.data];
                    message.push(...data);
                    try {
                        output.send(message);
                    } catch (err) {
                        console.error(err, e);
                    }
                }
                time = e.timestamp;
                i += 1;
            }
        }
    }
}

window.navigator.requestMIDIAccess().then(
    (access) => {
        const outputs = access.outputs;

        access.onstatechange = (event) => {
            console.log(event.port.name, event.port.manufacturer, event.port.state);
        };
        const iter = outputs.values();
        const output = iter.next().value;

        const source = document.getElementById('filereader');
        MidiParser.parse(source, async (obj) => await playRealtime(obj, output));
    }
);
