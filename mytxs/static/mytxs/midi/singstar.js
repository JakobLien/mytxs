import {MIDI} from './midi_constants.js';
import {PLAYER} from './player_constants.js';
import {MidiParser} from './midi-parser.js'; 
import {tickstampEvents, timestampEvents} from './event_timing.js';
import {createSingstarUi, uiSetProgress, uiSetScore} from './ui.js';
import { getNumBins, getSpectrum, startRecording } from './record.js';
import { singstarScore } from './singstar_score.js';
import { clearCanvas, drawSpectrum, initCanvas } from './spectrum_canvas.js';
import { silenceAll, sleep, resetMidiControl } from './player_utils.js';
import Mutex from './mutex.js';

let playerIndex = 0;
let playerTime = 0;
let score = 0;
const tempo = PLAYER.TEMPO.DEFAULT;
const activeTones = new Map(); // Map of sets
let singstarIndex;
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
        const startButton = document.getElementById("startButton");
        startButton.innerText = "Stop";
        stopped = false;
        start();
    }
    unlock();
}

async function stopSession() {
    // Act only if actually started
    const unlock = await mutex.lock();
    if (!stopped) {
        const startButton = document.getElementById("startButton");
        startButton.innerText = "Start";
        stopped = true;
        startPromise = createStartPromise(); // Prepare promise before telling main thread that session is stopped
    }
    unlock();
}

function eventSendable(event) {
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

async function playSingstar(obj, uiDiv, output) {
    // Reset
    uiDiv.innerHTML = "";
    resetMidiControl(output);

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

    // Create song name header
    const songNameHeader = document.createElement("h1");
    songNameHeader.innerText = "Nameless";
    for (const e of obj.track[0].event) {
        if (e.metaType == MIDI.METATYPE_TRACK_NAME) {
            songNameHeader.innerText = e.data;
            break;
        }
    }
    uiDiv.appendChild(songNameHeader);

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
            silenceAll(output);
        }
    };
    const singstarUi = createSingstarUi(songDuration, songBars, obj.track, trackSelectCallback, startCallback);
    uiDiv.appendChild(singstarUi);

    // Play
    outer: while (true) {
        playerTime = 0;
        playerIndex = 0;
        score = 0;
        while (playerIndex < allEvents.length) {
            // Play if not paused
            if (stopped) {
                await startPromise;
                continue outer; // Restart without stopping session, see below
            } else {
                const e = allEvents[playerIndex];
                // Wait until event
                const dt = e.timestamp - playerTime;
                if (dt > 0) {
                    await sleep(dt/1000/tempo);
                }
                // Consider whether to actually send message
                if (eventSendable(e)) {
                    const message = [(e.type << MIDI.STATUS_MSB_OFFSET) | e.trackId];
                    const data = Array.isArray(e.data) ? e.data : [e.data];
                    message.push(...data);
                    try {
                        const trackTones = activeTones.get(e.trackId);
                        if (e.type == MIDI.MESSAGE_TYPE_NOTEON) {
                            trackTones.add(e.data[0]);
                        } else if (e.type == MIDI.MESSAGE_TYPE_NOTEOFF) {
                            if (e.trackId == singstarIndex) {
                                score += singstarScore(trackTones);
                            }
                            trackTones.delete(e.data[0]);
                        }
                        output.send(message);
                    } catch (err) {
                        console.error(err, e);
                    }
                }
                // Update player state
                playerTime = e.timestamp;
                playerIndex += 1;
                uiSetProgress(playerTime, e.bar);
                uiSetScore(score);
            }
        }
        await stopSession(); // Must only be called if player reaches end by itself
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
        const uiDiv = document.getElementById('uiDiv');

        MidiParser.parse(source, obj => playSingstar(obj, uiDiv, output));

        initCanvas();
        startRecording(uiDiv, "click");

        function displaySpectrumLoop() {
            requestAnimationFrame(displaySpectrumLoop); // Repeat in next animation frame
            clearCanvas();
            drawSpectrum(getSpectrum(), getNumBins());
        }

        displaySpectrumLoop(); // Start capturing audio data
    }
);