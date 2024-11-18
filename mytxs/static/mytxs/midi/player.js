import { MIDI, PLAYER } from './constants.js';

let midiOutput;

export async function playerInit() {
    const access = await window.navigator.requestMIDIAccess();
    access.onstatechange = (event) => {
        console.log(event.port.name, event.port.manufacturer, event.port.state);
    };
    const outputs = Array.from(access.outputs.values());
    let outputIndex = 0;
    if (outputs.length > 1) {
        let promptString = `Flere mulige MIDI-outputs. Vennligst velg (0-${outputs.length-1}):\n`;
        for (const [key, value] of outputs.entries()) {
            promptString += key + ": " + value.name + "\n";
        }
        outputIndex = prompt(promptString);
    } 
    midiOutput = outputs[outputIndex];
}

export function playerPlayEvent(event) {
    const message = [(event.type << MIDI.STATUS_MSB_OFFSET) | event.trackId];
    const data = Array.isArray(event.data) ? event.data : [event.data];
    message.push(...data);
    try {
        midiOutput.send(message);
    } catch (err) {
        console.error(err, event);
    }
}

export function playerVolume(channel, value) {
    midiOutput.send([(MIDI.MESSAGE_TYPE_CONTROL_CHANGE << MIDI.STATUS_MSB_OFFSET) | channel, MIDI.VOLUME, value])
}

export function playerBalance(channel, value) {
    midiOutput.send([(MIDI.MESSAGE_TYPE_CONTROL_CHANGE << MIDI.STATUS_MSB_OFFSET) | channel, MIDI.BALANCE, value])
}

function playerPan(channel, value) {
    midiOutput.send([(MIDI.MESSAGE_TYPE_CONTROL_CHANGE << MIDI.STATUS_MSB_OFFSET) | channel, MIDI.PAN, value])
}

export function playerSilence(channel) {
    midiOutput.send([(MIDI.MESSAGE_TYPE_CONTROL_CHANGE << MIDI.STATUS_MSB_OFFSET) | channel, MIDI.ALL_SOUND_OFF, 0])
}

export function playerSilenceAll() {
    for (let channel = 0; channel < MIDI.NUM_CHANNELS; channel++) {
        playerSilence(channel);
    }
}

export function playerSleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

export function playerReset() {
    for (let channel = 0; channel < MIDI.NUM_CHANNELS; channel++) {
        playerVolume(channel, PLAYER.VOLUME.DEFAULT);
        playerBalance(channel, PLAYER.BALANCE.DEFAULT);
        playerPan(channel, PLAYER.PAN);
    }
}

