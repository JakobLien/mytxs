import { MIDI, PLAYER } from './constants.js';
import {MidiParser} from './midi-parser.js'; 
import Mutex from './mutex.js'; 
import {tickstampEvents, timestampEvents} from './event_timing.js';
import {uiPopulateMasterUi, uiCreateTrackUi, uiClearTrackDivs, uiSetProgress, uiSetSongName} from './ui.js';
import { playerVolume, playerBalance, playerSilence, playerSilenceAll, playerSleep, playerReset, playerInit, playerPlayEvent } from './player.js';

let playerIndex = 0;
let playerTime = 0;

let paused = true;
let resume;
function createPausePromise() {
    return new Promise((resolve) => {
        resume = resolve;
    });
}
let pausePromise = createPausePromise();

let tempo = PLAYER.TEMPO.DEFAULT;
let allEvents = [];
const trackMuted = new Map();
let soloTrack = null;
let loopActive = false;
let loopStart = null;
let loopEnd = null;
const mutex = new Mutex();

function eventSendable(trackMuted, soloTrack, event) {
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

function realtimeReset() {
    uiClearTrackDivs();
    playerReset();
    playerSilenceAll();
    playerIndex = 0;
    playerTime = 0;
    uiSetProgress(0, 0);
}

function realtimeSetup(obj) {
    if (obj.formatType != MIDI.FORMAT_TYPE_MULTITRACK) {
        alert("".concat("Ugyldig format: ", obj.formatType));
    }

    if (obj.timeDivision & (1 << MIDI.TIME_DIVISION_TICKS_PER_BEAT)) {
        alert("".concat("Ugyldig tempoformat: ", obj.timeDivision));
    }
    const ticksPerBeat = obj.timeDivision;

    // Process events into a playable format
    allEvents = [];
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

    const pauseCallback = e => {
        paused = !paused;
        e.target.innerText = paused ? "Play" : "Pause";
        if (paused) {
            playerSilenceAll();
            pausePromise = createPausePromise();
        } else {
            resume();
        }
    };

    loopStart = 0;
    const loopStartCallback = (e) => loopStart = e.target.value;
    loopEnd = songBars;
    const loopEndCallback = (e) => loopEnd = e.target.value;
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

async function realtimePlay() {
    while (true) {
        playerTime = 0;
        playerIndex = 0;
        while (playerIndex < allEvents.length) {
            // Play if not paused
            if (paused) {
                await pausePromise;
            } else {
                const unlock = await mutex.lock();
                const e = allEvents[playerIndex];
                if (loopActive && e.bar >= loopEnd) {
                    // Jump to start of loop
                    playerSilenceAll();
                    playerIndex = startingIndexFromBar(allEvents, loopStart);
                    playerTime = allEvents[playerIndex].timestamp;
                    uiSetProgress(playerTime, allEvents[playerIndex].bar);
                } else {
                    // Wait until event
                    const dt = e.timestamp - playerTime;
                    if (dt > 0) {
                        await playerSleep(dt/1000/tempo);
                    }
                    // Consider whether to actually send message
                    if (eventSendable(trackMuted, soloTrack, e)) {
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
        // Avoid starving UI if allEvents.length is zero
        // It would be much cleaner if there was a mechanic to set higher priority for UI threads
        await playerSleep(PLAYER.RESTART_SLEEP_MS);
    }
}

window.onload = async () => {
    await playerInit();
    const fileInput = document.getElementById('fileInput');
    const fileInputCallback = obj => {
        realtimeReset();
        realtimeSetup(obj);
    };
    MidiParser.parse(fileInput, fileInputCallback);
    realtimePlay();
};
