import { MIDI, PLAYER } from './constants.js';
import {MidiParser} from './midi-parser.js'; 
import Mutex from './mutex.js'; 
import {tickstampEvents, timestampEvents} from './event_timing.js';
import {uiPopulateMasterUi, uiCreateTrackUi, uiClearTrackDivs, uiSetProgress, uiSetSongName, uiSetPauseButtonText} from './ui.js';
import { playerVolume, playerBalance, playerSilence, playerSilenceAll, playerSleep, playerReset, playerInit, playerPlayEvent, playerWakeUp } from './player.js';

let playerIndex = 0;
let playerTime = 0;

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
                // Return false for all events meant to be controlled by user
                case MIDI.VOLUME:
                case MIDI.BALANCE:
                case MIDI.PAN:
                    return false;
                default:
                    return true;
            }
        default:
            return true;
    }
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
    return high < allEvents.length ? high : low;
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
    return high < allEvents.length ? high : low;
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
        const jumpTime = e.target.value;
        const unlock = await mutex.lock();
        playerIndex = startingIndexFromTime(allEvents, jumpTime);
        playerTime = jumpTime; // Better than allEvents[playerIndex].timestamp, because this allows jumps to the middle of long notes
        uiSetProgress(playerTime, allEvents[playerIndex].bar);
        unlock();
    };

    const barNumberCallback = async e => {
        playerSilenceAll();
        const jumpBar = e.target.value;
        const unlock = await mutex.lock();
        playerIndex = startingIndexFromBar(allEvents, jumpBar);
        playerTime = allEvents[playerIndex].timestamp;
        uiSetProgress(playerTime, allEvents[playerIndex].bar);
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

    uiPopulateMasterUi(songDuration, songBars, progressCallback, barNumberCallback, tempoBarCallback, pauseCallback, loopStartCallback, loopEndCallback, loopActiveCallback);

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
        playerTime = 0;
        playerIndex = 0;
        uiSetProgress(0, 0);
        while (playerIndex < allEvents.length) {
            // Events are remaining - sleep until what is probably 
            // the next event (unless user changes playerTime)
            const dt = allEvents[playerIndex].timestamp - playerTime;
            if (dt > 0) {
                await playerSleep(dt/1000/tempo);
            }

            // Check if user paused or requested reset during sleep
            if (pendingReset) {
                playerSilenceAll();
                break;
            } else if (paused) {
                playerSilenceAll();
                await pausePromise;
            } 

            // Lock in event
            const unlock = await mutex.lock();
            const e = allEvents[playerIndex];
            if (loopActive && e.bar >= loopEnd) {
                // Jump to start of loop
                playerSilenceAll();
                playerIndex = startingIndexFromBar(allEvents, loopStart);
                playerTime = allEvents[playerIndex].timestamp;
                uiSetProgress(playerTime, allEvents[playerIndex].bar);
            } else {
                // Consider whether to actually play event
                if (eventPlayable(trackMuted, soloTrack, e)) {
                    playerPlayEvent(e);
                }
                // Update player state
                playerTime = e.timestamp;
                playerIndex += 1;
                uiSetProgress(playerTime, e.bar);
            }
            unlock();
        }
    }

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
