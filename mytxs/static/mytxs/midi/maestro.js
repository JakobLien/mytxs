import { MIDI, PLAYER, EPS } from './constants.js';
import {MidiParser} from './midi-parser.js'; 
import Mutex from './mutex.js'; 
import {tickstampEvents, timestampEvents} from './event_timing.js';
import {uiPopulateMasterUi, uiCreateTrackUi, uiClearTrackDivs, uiSetProgress, uiSetSongName, uiSetPauseButtonText} from './ui.js';
import { playerVolume, playerBalance, playerSilence, playerSilenceAll, playerSleep, playerReset, playerInit, playerPlayEvent, playerWakeUp, playerProgramAll } from './player.js';
import { barToTime, startingIndexFromBar, startingIndexFromTime, timeToBar } from './utils.js';

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
let transpose = PLAYER.TRANSPOSE.DEFAULT;
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

function maestroSetState(index, time, bar) {
    playerIndex = index;
    playerTime = time;
    playerBar = Math.round(bar * 1e6) / 1e6; // Most likely we are never dealing with bar precision less than 1e-6
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
        const unlock = await mutex.lock();
        playerSilenceAll();
        maestroSetStateFromTime(allEvents, Number(e.target.value));
        unlock();
        playerWakeUp();
    };

    const barNumberCallback = async e => {
        const unlock = await mutex.lock();
        playerSilenceAll();
        maestroSetStateFromBar(allEvents, Number(e.target.value));
        unlock();
        playerWakeUp();
    };

    const tempoBarCallback = e => tempo = Number(e.target.value);

    const pauseCallback = () => {
        if (paused) {
            paused = false;
            uiSetPauseButtonText("Pause");
            resume();
        } else {
            pausePromise = createPausePromise();
            paused = true;
            uiSetPauseButtonText("Spill");
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

    const instrumentNumberCallback = e => playerProgramAll(Number(e.target.value));

    const transposeCallback = async e => {
        const unlock = await mutex.lock();
        playerSilenceAll(); // Avoid noteons without corresponding noteoff
        transpose = Number(e.target.value)
        unlock();
    };

    uiPopulateMasterUi(songDuration, songBars, progressCallback, barNumberCallback, tempoBarCallback, pauseCallback, loopStartCallback, loopEndCallback, loopActiveCallback, instrumentNumberCallback, transposeCallback);

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
            track.label = "Spor " + i;
        }

        const trackId = track.event[0].trackId;
        const volumeCallback = e => playerVolume(trackId, Number(e.target.value));
        const balanceCallback = e => playerBalance(trackId, Number(e.target.value));
        trackMuted.set(trackId, false);
        const muteCallback = e => {
            const wasMuted = trackMuted.get(trackId);
            if (!wasMuted) {
                playerSilence(trackId);
            }
            e.target.innerText = wasMuted ? "Demp" : "Dempet";
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

        // Update UI
        uiSetProgress(playerTime, playerBar);

        // Take control over player state and determine whether to play or sleep
        const unlock = await mutex.lock();
        let dt = 0;
        const t0 = playerTime;
        const nextEvent = allEvents[playerIndex];
        if (loopActive && (playerBar < loopStart || playerBar >= loopEnd)) {
            // Jump to start of loop
            playerSilenceAll();
            maestroSetStateFromBar(allEvents, loopStart);
        } else if (nextEvent.timestamp <= playerTime) {
            // We have arrived at the event
            // Consider whether to actually play event
            if (eventPlayable(trackMuted, soloTrack, nextEvent)) {
                playerPlayEvent(nextEvent, transpose);
            }

            // Update player state
            if (playerIndex + 1 >= allEvents.length) {
                maestroSetStateFromIndex(allEvents, 0);
            } else {
                playerIndex = playerIndex + 1; // TODO Clean this up
            }
        } else {
            // We are not at the event yet
            // Find the next interesting time point
            const dtEvent = nextEvent.timestamp - t0;
            const nextSecond = playerTime + 1000000 - playerTime % 1000000;
            const dtSecond = nextSecond - t0;
            const nextBar = Math.ceil(playerBar + EPS);
            const dtBar = barToTime(allEvents, playerIndex, nextBar) - t0; // This value may be wrong if the tempo changes before we reach nextBar, but then dtEvent will be less than dtBar anyways
            dt = Math.min(dtEvent, dtSecond, dtBar); // dt must be nonzero here, otherwise we get an infinite loop. Will be nonzero if dtSecond and dtBar are well-behaved
            const i0 = playerIndex;
            maestroSetStateFromTime(allEvents, playerTime + dt);
            playerIndex = i0; // Ensure that we never skip events. TODO Clean this up
        }
        // By storing dt before unlocking, we avoid long sleeps which may happen
        // if other threads, the UI for instance, cause a jump in playerTime
        unlock();

        // Playerstate will now be ahead of actual time - go to sleep to compensate
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
