import {MIDI} from './midi_constants.js';
import { PLAYER } from './player_constants.js';

export function volumeChannel(output, channel, value) {
    output.send([(MIDI.MESSAGE_TYPE_CONTROL_CHANGE << MIDI.STATUS_MSB_OFFSET) | channel, MIDI.VOLUME, value])
}

export function balanceChannel(output, channel, value) {
    output.send([(MIDI.MESSAGE_TYPE_CONTROL_CHANGE << MIDI.STATUS_MSB_OFFSET) | channel, MIDI.BALANCE, value])
}

function panChannel(output, channel, value) {
    output.send([(MIDI.MESSAGE_TYPE_CONTROL_CHANGE << MIDI.STATUS_MSB_OFFSET) | channel, MIDI.PAN, value])
}

export function silenceChannel(output, channel) {
    output.send([(MIDI.MESSAGE_TYPE_CONTROL_CHANGE << MIDI.STATUS_MSB_OFFSET) | channel, MIDI.ALL_SOUND_OFF, 0])
}

export function silenceAll(output) {
    for (let channel = 0; channel < MIDI.NUM_CHANNELS; channel++) {
        silenceChannel(output, channel);
    }
}

export function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

export function resetMidiControl(output) {
    for (let channel = 0; channel < MIDI.NUM_CHANNELS; channel++) {
        volumeChannel(output, channel, PLAYER.VOLUME.DEFAULT);
        balanceChannel(output, channel, PLAYER.BALANCE.DEFAULT);
        panChannel(output, channel, PLAYER.PAN);
    }
}

