import { MIDI, PLAYER } from './constants.js';
import {MidiParser} from './midi-parser.js'; 
import {tickstampEvents, timestampEvents} from './event_timing.js';
import {uiClearTrackOptions, uiPopulateSingstarUi, uiSetHighscore, uiSetProgress, uiSetScore, uiSetSongName, uiSetStartButtonText} from './ui.js';
import { freqGetSpectrum, freqStartRecording } from './freq.js';
import { scoreGet } from './score.js';
import { canvasClear, canvasDrawSpectrum, canvasDrawTargets, canvasInit } from './canvas.js';
import { playerSilenceAll, playerSleep, playerReset, playerPlayEvent, playerInit } from './player.js';
import Mutex from './mutex.js';

let playerIndex = 0;
let playerTime = 0;
let score = 0;
let highscore = 0;
const tempo = PLAYER.TEMPO.DEFAULT;
const activeTones = new Map(); // Map of sets
let singstarIndex = null;
let allEvents = [];
const mutex = new Mutex();

let stopped = true;

let start;
function createStartPromise() {
    return new Promise((resolve) => {
        start = resolve;
    });
}
let startPromise = createStartPromise();

async function startSession() {
    // Act only if actually stopped
    const unlock = await mutex.lock();
    if (stopped) {
        uiSetStartButtonText("Stop");
        stopped = false;
        start();
    }
    unlock();
}

async function stopSession() {
    // Act only if actually started
    const unlock = await mutex.lock();
    if (!stopped) {
        uiSetStartButtonText("Start");
        stopped = true;
        startPromise = createStartPromise(); // Prepare promise before telling main thread that session is stopped
    }
    unlock();
}

function eventPlayable(event) {
    switch (event.type) {
        case MIDI.MESSAGE_TYPE_META:
            return false;
        case MIDI.MESSAGE_TYPE_NOTEON:
            return true;
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

async function resetSingstar() {
    await stopSession();
    playerReset();
    playerSilenceAll();
    playerIndex = 0;
    playerTime = 0;
    score = 0;
    highscore = 0;
    singstarIndex = null;
    uiClearTrackOptions();
    uiSetHighscore(0);
    uiSetScore(0);
    uiSetProgress(0, 0);
}

function setupSingstar(obj) {
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
    const startCallback = async () => {
        if (stopped) {
            await startSession();
        } else {
            await stopSession();
            playerSilenceAll();
        }
    };
    uiPopulateSingstarUi(songDuration, songBars, obj.track, trackSelectCallback, startCallback);
}

async function playSingstar() {
    // Session loop
    while (true) {

        // Prepare session
        playerTime = 0;
        playerIndex = 0;
        score = 0;

        // Run session
        while (true) {
            // Wait if stopped, and stop if at the end of song
            if (stopped) {
                await startPromise;
                break;
            } else if (playerIndex >= allEvents.length) {
                await stopSession();
                break;
            } 

            // Events are remaining - sleep until what is probably 
            // the next event (unless user changes playerTime)
            const dt = allEvents[playerIndex].timestamp - playerTime;
            if (dt > 0) {
                await playerSleep(dt/1000/tempo);
            }

            // Wait for restart if stop button was pressed during sleep
            if (stopped) {
                await startPromise;
                break;
            } 

            // Lock in event 
            const e = allEvents[playerIndex];
            // Decide whether to actually play event
            if (eventPlayable(e)) {
                try {
                    const trackTones = activeTones.get(e.trackId);
                    if (e.type == MIDI.MESSAGE_TYPE_NOTEON) {
                        trackTones.add(e.data[0]);
                    } else if (e.type == MIDI.MESSAGE_TYPE_NOTEOFF) {
                        if (e.trackId == singstarIndex) {
                            score += scoreGet(trackTones);
                        }
                        trackTones.delete(e.data[0]);
                    }
                } catch (err) {
                    console.error(err, e);
                }
                playerPlayEvent(e);
            }

            // Update player state
            playerTime = e.timestamp;
            playerIndex += 1;
            uiSetProgress(playerTime, e.bar);
            uiSetScore(score);
        }

        // Post-processing of session
        if (highscore < score) {
            highscore = score;
            uiSetHighscore(highscore);
        }
    }
}

window.onload = async () => {
    await playerInit();

    const uiDiv = document.getElementById('uiDiv');
    freqStartRecording(uiDiv, "click");

    const fileInput = document.getElementById('fileInput');
    const fileInputCallback = async obj => {
        await resetSingstar();
        setupSingstar(obj);
    };
    MidiParser.parse(fileInput, fileInputCallback);
    setTimeout(playSingstar, 0); // Essentially call in new thread

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
