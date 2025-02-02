import { MIDI, PLAYER, EPS } from './constants.js';
import {MidiParser} from './midi-parser.js'; 
import Mutex from './mutex.js'; 
import {tickstampEvents, timestampEvents} from './event_timing.js';
import {uiPopulateMasterUi, uiCreateTrackUi, uiClearTrackDivs, uiSetProgress, uiSetSongName, uiSetPauseButtonText} from './ui.js';
import { playerVolume, playerBalance, playerSilence, playerSilenceAll, playerSleep, playerReset, playerInit, playerPlayEvent, playerWakeUp, playerProgramAll } from './player.js';

let playerIndex = 0;
let playerTime = 0;
let playerBar = 0;

let pendingReset = false;

let signalExited;
function createExitPromise() {
    return new Promise(resolve => signalExited = resolve);
}
let exitPromise = null;

let paused = true;
let resume;
function createPausePromise() {
    return new Promise(resolve => resume = resolve);
}
let pausePromise = createPausePromise();

let tempo = PLAYER.TEMPO.DEFAULT;
const trackMuted = new Map();
let soloTrack = null;
let loopActive = false;
let loopStart = null;
let loopEnd = null;
const mutex = new Mutex();

function eventPlayable(trackMuted, soloTrack, event) {
    switch (event.type) {
        case MIDI.MESSAGE_TYPE_META:
            return false;
        case MIDI.MESSAGE_TYPE_NOTEON:
            return !trackMuted.get(event.trackId) && (soloTrack == null || soloTrack == event.trackId);
        case MIDI.MESSAGE_TYPE_CONTROL_CHANGE:
            switch (event.data[0]) { 
                case MIDI.MODULATION_WHEEL: // More annoying than fun
                // Return false for all events meant to be controlled by user
                case MIDI.VOLUME:
                case MIDI.BALANCE:
                case MIDI.PAN:
                    return false;
                default:
                    return true;
            }
        case MIDI.MESSAGE_TYPE_PROGRAM_CHANGE:
            return false;
        default:
            return true;
    }
}

// Binary search for index of the first event with element[attr] >= value. Returns last index if none exist
// Assumes that array elements are sorted with respect to the value of attr
function startingIndexFromAttribute(array, attr, value) {
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

function startingIndexFromTime(allEvents, time) {
    return startingIndexFromAttribute(allEvents, 'timestamp', time);
}

function startingIndexFromBar(allEvents, bar) {
    return startingIndexFromAttribute(allEvents, 'bar', bar);
}

function interpolateBetweenElements(array, high, xAttr, yAttr, x) {
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

function barToTime(allEvents, highIndex, bar) {
    return interpolateBetweenElements(allEvents, highIndex, 'bar', 'timestamp', bar);
}

function timeToBar(allEvents, highIndex, time) {
    return interpolateBetweenElements(allEvents, highIndex, 'timestamp', 'bar', time);
}

function maestroSetState(index, time, bar) {
    playerIndex = index;
    playerTime = time;
    playerBar = bar;
}

function maestroSetStateFromIndex(allEvents, index) {
    const time = allEvents[index].timestamp;
    const bar = allEvents[index].bar;
    maestroSetState(index, time, bar);
}

function maestroSetStateFromTime(allEvents, time) {
    const index = startingIndexFromTime(allEvents, time);
    const bar = timeToBar(allEvents, index, time);
    maestroSetState(index, time, bar);
}

function maestroSetStateFromBar(allEvents, bar) {
    const index = startingIndexFromBar(allEvents, bar);
    const time = barToTime(allEvents, index, bar);
    maestroSetState(index, time, bar);
}

async function maestroReset() {
    // Send message to player
    pendingReset = true;

    // If thread exists already, wait for it to exit
    if (exitPromise !== null) {
        await exitPromise;
    }
    exitPromise = createExitPromise();
    
    pendingReset = false;

    playerReset();

    playerIndex = 0;
    playerTime = 0;
    playerBar = 0;

    tempo = PLAYER.TEMPO.DEFAULT;
    trackMuted.clear();
    soloTrack = null;
    loopActive = false;
    loopStart = null;
    loopEnd = null;

    uiClearTrackDivs();
}

function maestroSetup(obj, allEvents) {
    if (obj.formatType != MIDI.FORMAT_TYPE_MULTITRACK) {
        alert("".concat("Ugyldig format: ", obj.formatType));
    }

    if (obj.timeDivision & (1 << MIDI.TIME_DIVISION_TICKS_PER_BEAT)) {
        alert("".concat("Ugyldig tempoformat: ", obj.timeDivision));
    }
    const ticksPerBeat = obj.timeDivision;

    // Process events into a playable format
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

    // Set song name
    uiSetSongName("Nameless");
    for (const e of obj.track[0].event) {
        if (e.metaType == MIDI.METATYPE_TRACK_NAME) {
            uiSetSongName(e.data);
            break;
        }
    }

    // Create master UI
    const songDuration = allEvents[allEvents.length - 1].timestamp;
    const songBars = Math.floor(allEvents[allEvents.length - 1].bar);

    const progressCallback = async e => {
        playerSilenceAll();
        const unlock = await mutex.lock();
        maestroSetStateFromTime(allEvents, e.target.value);
        unlock();
    };

    const barNumberCallback = async e => {
        playerSilenceAll();
        const unlock = await mutex.lock();
        maestroSetStateFromBar(allEvents, e.target.value);
        unlock();
    };

    const tempoBarCallback = e => tempo = e.target.value;

    const pauseCallback = () => {
        if (paused) {
            paused = false;
            uiSetPauseButtonText("Pause");
            resume();
        } else {
            pausePromise = createPausePromise();
            paused = true;
            uiSetPauseButtonText("Play");
            playerWakeUp(); // For main thread to quickly react to pausing
        }
    };

    loopStart = 0;
    const loopStartCallback = e => {
        const value = Number(e.target.value); // Avoid lexicographic string comparison
        if (value >= loopEnd) {
            e.target.value = loopStart; // Reject value if invalid
        } else {
            loopStart = value;
        }
    };
    loopEnd = songBars;
    const loopEndCallback = e => {
        const value = Number(e.target.value); // Avoid lexicographic string comparison
        if (value <= loopStart) {
            e.target.value = loopEnd; // Reject value if invalid
        } else {
            loopEnd = value;
        }
    };
    const loopActiveCallback = () => loopActive = !loopActive;

    const instrumentNumberCallback = e => playerProgramAll(e.target.value);

    uiPopulateMasterUi(songDuration, songBars, progressCallback, barNumberCallback, tempoBarCallback, pauseCallback, loopStartCallback, loopEndCallback, loopActiveCallback, instrumentNumberCallback);

    // Create UI for tracks which have noteon events
    for (let i = 0; i < obj.track.length; i++) {
        const track = obj.track[i];

        if (track.event.every(e => e.type != MIDI.MESSAGE_TYPE_NOTEON)) {
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
        const volumeCallback = e => playerVolume(trackId, e.target.value);
        const balanceCallback = e => playerBalance(trackId, e.target.value);
        trackMuted.set(trackId, false);
        const muteCallback = e => {
            const wasMuted = trackMuted.get(trackId);
            if (!wasMuted) {
                playerSilence(trackId);
            }
            e.target.innerText = wasMuted ? "Mute" : "Unmute";
            trackMuted.set(trackId, !wasMuted);
        };
        const soloCallback = e => {
            if (soloTrack == trackId) {
                e.target.checked = false;
                soloTrack = null;
            } else {
                soloTrack = trackId;
            }
        };
        uiCreateTrackUi(track.label, volumeCallback, balanceCallback, muteCallback, soloCallback);
    }
}

async function maestroPlay(allEvents) {
    while (!pendingReset) {
        // Check if user paused or requested reset during sleep
        if (paused) {
            playerSilenceAll();
            await pausePromise;
        }

        // Lock in event and play
        const unlock = await mutex.lock();
        const e = allEvents[playerIndex];
        const t0 = playerTime;
        if (loopActive && e.bar >= loopEnd) {
            // Jump to start of loop
            playerSilenceAll();
            maestroSetStateFromBar(allEvents, loopStart);
        } else {
            // Consider whether to actually play event
            if (eventPlayable(trackMuted, soloTrack, e)) {
                playerPlayEvent(e);
            }

            // Update UI when events are played
            // Add EPS to bar to avoid e.g. 5.999999 being truncated to 5
            uiSetProgress(playerTime, playerBar + EPS);

            // Update player state
            if (playerIndex + 1 >= allEvents.length) {
                maestroSetStateFromIndex(allEvents, 0);
            } else {
                maestroSetStateFromIndex(allEvents, playerIndex + 1);
            }
        }
        // The next state is now targeted - note down the time until it occurs
        // By storing this before unlocking, we avoid long sleeps which may happen
        // if other threads, the UI for instance, cause a jump in playerTime
        const t1 = playerTime;
        const dt = t1 - t0;
        unlock();

        // Sleep
        if (dt > 0) {
            await playerSleep(dt/1000/tempo);
        }

    }

    // Silence player in case the reset was issued before all note off events were sent
    playerSilenceAll();
    
    // Resolve promise for new setup to continue
    signalExited();
}

window.onload = async () => {
    await playerInit();
    const fileInput = document.getElementById('fileInput');
    const fileInputCallback = async obj => {
        const allEvents = [];
        await maestroReset();
        maestroSetup(obj, allEvents);
        maestroPlay(allEvents);
    };
    MidiParser.parse(fileInput, fileInputCallback);
};
