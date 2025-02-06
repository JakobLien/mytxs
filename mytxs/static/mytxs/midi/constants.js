export const EPS = 1e-7;

export const PLAYER = {
    VOLUME: {
        MIN: 0,
        MAX: 127,
        DEFAULT: 127,
    },
    BALANCE: {
        MIN: 0,
        MAX: 127,
        DEFAULT: 64,
    },
    PAN: 64,
    TEMPO: {
        MIN: 0.1,
        MAX: 3.0,
        DEFAULT: 1.0,
        STEP: 0.01,
    },
    PROGRAM: {
        MIN: 0,
        MAX: 127,
        DEFAULT: 0,
    },
    TRANSPOSE: {
        MIN: -12,
        MAX: 12,
        DEFAULT: 0,
    },
};

export const RECORD = {
    FFT_SIZE: 4096, // Roughly 0.1 s at a sampling frequency of 44100 Hz
    GAIN: 1.0, // Ideally the user should give a reasonably configured microphone
    MIN_DECIBELS: -100,
    MAX_DECIBELS: -20,
};

export const BASE_TONE = {
    NUMBER: 69,
    HZ: 440,
};

export const CANVAS = {
    // Width and height given in HTML

    MAX_FREQ: 1000,

    BASE_COLOR: {
        R: 100,
        G: 50,
        B: 50,
    },

    TARGET_COLOR: {
        R: 50,
        G: 100,
        B: 50,
    },
};

export const MIDI = {
    NUM_CHANNELS: 16,
    STATUS_MSB_OFFSET: 4,

    DEFAULT_BPM: 120,
    DEFAULT_BEATS_PER_BAR: 4,

    FORMAT_TYPE_MULTITRACK: 1,
    TIME_DIVISION_TICKS_PER_BEAT: 15,

    METATYPE_TRACK_NAME: 3,
    METATYPE_SET_TEMPO: 81,
    METATYPE_TIME_SIGNATURE: 88,

    MESSAGE_TYPE_META: 255,
    MESSAGE_TYPE_NOTEOFF: 8,
    MESSAGE_TYPE_NOTEON: 9,
    MESSAGE_TYPE_CONTROL_CHANGE: 11, // Also used for channel mode messages
    MESSAGE_TYPE_PROGRAM_CHANGE: 12,

    MODULATION_WHEEL: 1,
    VOLUME: 7,
    BALANCE: 8,
    PAN: 10,
    ALL_SOUND_OFF: 120,
};

export const SCORE = {
    RELATIVE_MAGNITUDE_LIMIT: 0.9,
    DISPLAY_DECIMALS: 2,
};
