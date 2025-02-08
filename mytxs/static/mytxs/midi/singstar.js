import { EPS, MIDI, PLAYER } from './constants.js';
import {MidiParser} from './midi-parser.js'; 
import {tickstampEvents, timestampEvents} from './event_timing.js';
import {uiClearTrackOptions, uiPopulateSingstarUi, uiSetHighscore, uiSetProgress, uiSetScore, uiSetSongName, uiSetStartButtonText} from './ui.js';
import { freqGetSpectrum, freqStartRecording } from './freq.js';
import { scoreGet } from './score.js';
import { canvasClear, canvasDrawSpectrum, canvasDrawTargets, canvasInit } from './canvas.js';
import { playerSilenceAll, playerSleep, playerReset, playerPlayEvent, playerInit, playerWakeUp } from './player.js';
import { barToTime, startingIndexFromTime, timeToBar } from './utils.js';

let highscore = 0;
const tempo = PLAYER.TEMPO.DEFAULT;
const activeTones = new Map(); // Map of sets
let singstarIndex = null;

let stopped = true;
let stopRequested = false;
let pendingReset = false;

let start;
function createStartPromise() {
    return new Promise(resolve => start = resolve);
}

let signalExited;
function createExitPromise() {
    return new Promise(resolve => signalExited = resolve);
}
let exitPromise = null;

function eventPlayable(event) {
    switch (event.type) {
        case MIDI.MESSAGE_TYPE_META:
            return false;
        case MIDI.MESSAGE_TYPE_NOTEON:
            return true;
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

async function resetSingstar() {
    // Send message to player
    pendingReset = true;

    // If thread exists already, wait for it to exit
    if (exitPromise !== null) {
        await exitPromise;
    }
    exitPromise = createExitPromise();
    
    pendingReset = false;

    playerReset();

    highscore = 0;
    uiSetHighscore(0);

    singstarIndex = null;
    uiClearTrackOptions();
}

function setupSingstar(obj, allEvents) {
    if (obj.formatType != MIDI.FORMAT_TYPE_MULTITRACK) {
        alert("".concat("Ugyldig format: ", obj.formatType));
    }

    if (obj.timeDivision & (1 << MIDI.TIME_DIVISION_TICKS_PER_BEAT)) {
        alert("".concat("Ugyldig tempoformat: ", obj.timeDivision));
    }
    const ticksPerBeat = obj.timeDivision;

    // Process events into a playable format
    for (const i in obj.track) {
        const track = obj.track[i];
        track.trackId = i;
        const events = track.event;
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

    // Label tracks and initialize activeTones
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

        activeTones.set("" + i, new Set());
    }

    // Create singstar UI
    const songDuration = allEvents[allEvents.length - 1].timestamp;
    const songBars = Math.floor(allEvents[allEvents.length - 1].bar);
    const trackSelectCallback = e => singstarIndex = e.target.value;
    const startCallback = () => {
        if (stopped) {
            // Main thread will set stopped = false;
            start();
        } else {
            stopRequested = true;
            playerWakeUp();
        }
    };
    uiPopulateSingstarUi(songDuration, songBars, obj.track, trackSelectCallback, startCallback);
}

async function playSingstar(allEvents) {
    // Session loop
    while (!pendingReset) {

        uiSetStartButtonText("Start");
        const startPromise = createStartPromise();
        stopped = true;
        stopRequested = false;

        await startPromise;

        uiSetStartButtonText("Stopp");
        stopped = false;

        // Prepare session
        let playerIndex = 0;
        let playerTime = 0;
        let playerBar = 0;
        let score = 0;

        uiSetProgress(0, 0);
        uiSetScore(0);

        // Run session
        while (playerIndex < allEvents.length) {
            // Stop session if stop button was pressed during sleep
            if (stopRequested || pendingReset) {
                playerSilenceAll();
                break;
            } 

            const nextEvent = allEvents[playerIndex];
            // Check if we have arrived at event
            if (nextEvent.timestamp <= playerTime) {
                // We have arrived at event. Decide whether to actually play it
                if (eventPlayable(nextEvent)) {
                    try {
                        const trackTones = activeTones.get(nextEvent.trackId);
                        if (nextEvent.type == MIDI.MESSAGE_TYPE_NOTEON) {
                            trackTones.add(nextEvent.data[0]);
                        } else if (nextEvent.type == MIDI.MESSAGE_TYPE_NOTEOFF) {
                            if (nextEvent.trackId == singstarIndex) {
                                // Update and display score
                                score += scoreGet(trackTones);
                                uiSetScore(score);
                            }
                            trackTones.delete(nextEvent.data[0]);
                        }
                    } catch (err) {
                        console.error(err, nextEvent);
                    }
                    playerPlayEvent(nextEvent);
                }

                // Update player state
                playerIndex += 1;
                // playerBar and playerTime should already be correct

            } else {
                // We have not reached the event yet
                const dtEvent = nextEvent.timestamp - playerTime;
                const nextSecond = playerTime + 1000000 - playerTime % 1000000;
                const dtSecond = nextSecond - playerTime;
                const nextBar = Math.ceil(playerBar + EPS);
                const dtBar = barToTime(allEvents, playerIndex, nextBar) - playerTime; // This value may be wrong if the tempo changes before we reach nextBar, but then dtEvent will be less than dtBar anyways
                const dt = Math.min(dtEvent, dtSecond, dtBar); // dt must be nonzero here, otherwise we get an infinite loop. Will be nonzero if dtSecond and dtBar are well-behaved
                if (dt > 0) {
                    await playerSleep(dt/1000/tempo);
                }

                // Update player state
                playerTime += dt;
                const index = startingIndexFromTime(allEvents, playerTime); // Only for bar interpolation, playerIndex should remain the same as we have not reached the event yet
                const bar = timeToBar(allEvents, index, playerTime);
                playerBar = Math.round(bar * 1e6) / 1e6; // Most likely we are never dealing with bar precision less than 1e-6

                // Update UI
                uiSetProgress(playerTime, playerBar);
            }
        }

        // Post-processing of session
        if (highscore < score) {
            highscore = score;
            uiSetHighscore(highscore);
        }
    }

    // Resolve promise for new setup to continue
    signalExited();
}

window.onload = async () => {
    await playerInit();

    const uiDiv = document.getElementById('uiDiv');
    freqStartRecording(uiDiv, "click");

    const fileInput = document.getElementById('fileInput');
    const fileInputCallback = async obj => {
        const allEvents = [];
        await resetSingstar();
        setupSingstar(obj, allEvents);
        playSingstar(allEvents);
    };
    MidiParser.parse(fileInput, fileInputCallback);

    canvasInit();
    function drawSpectrumLoop() {
        requestAnimationFrame(drawSpectrumLoop); // Repeat in next animation frame
        canvasClear();
        canvasDrawSpectrum(freqGetSpectrum());
        if (singstarIndex !== null) {
            const targetTones = activeTones.get(singstarIndex);
            canvasDrawTargets(targetTones);
        }
    }
    drawSpectrumLoop();
};
