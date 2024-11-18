import { MIDI, PLAYER } from './constants.js';

export function playerVolume(midiOutput, channel, value) {
    midiOutput.send([(MIDI.MESSAGE_TYPE_CONTROL_CHANGE << MIDI.STATUS_MSB_OFFSET) | channel, MIDI.VOLUME, value])
}

export function playerBalance(midiOutput, channel, value) {
    midiOutput.send([(MIDI.MESSAGE_TYPE_CONTROL_CHANGE << MIDI.STATUS_MSB_OFFSET) | channel, MIDI.BALANCE, value])
}

function playerPan(midiOutput, channel, value) {
    midiOutput.send([(MIDI.MESSAGE_TYPE_CONTROL_CHANGE << MIDI.STATUS_MSB_OFFSET) | channel, MIDI.PAN, value])
}

export function playerSilence(midiOutput, channel) {
    midiOutput.send([(MIDI.MESSAGE_TYPE_CONTROL_CHANGE << MIDI.STATUS_MSB_OFFSET) | channel, MIDI.ALL_SOUND_OFF, 0])
}

export function playerSilenceAll(midiOutput) {
    for (let channel = 0; channel < MIDI.NUM_CHANNELS; channel++) {
        playerSilence(midiOutput, channel);
    }
}

export function playerSleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

export function playerReset(midiOutput) {
    for (let channel = 0; channel < MIDI.NUM_CHANNELS; channel++) {
        playerVolume(midiOutput, channel, PLAYER.VOLUME.DEFAULT);
        playerBalance(midiOutput, channel, PLAYER.BALANCE.DEFAULT);
        playerPan(midiOutput, channel, PLAYER.PAN);
    }
}

