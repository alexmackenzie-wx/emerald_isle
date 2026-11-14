// A small music driver: three tracks (pulse lead, wave bass, noise drums)
// stepped from the vertical-blank interrupt. Song data comes from tools/gen_music.py.
#include "sound.h"

static const song_t *song;
static uint8_t cur_song = 255, playing, frame;
static const uint8_t *tp[3];
static uint8_t wait[3];
// two cycles of a triangle, so bass notes sound at their written pitch
static const uint8_t wave[16] = { 0x02, 0x46, 0x8A, 0xCE, 0xFD, 0xB9, 0x75, 0x31,
                                  0x02, 0x46, 0x8A, 0xCE, 0xFD, 0xB9, 0x75, 0x31 };

static void music_isr(void) {
    uint8_t c, n;
    uint16_t f;
    if (!playing) return;
    if (++frame < song->speed) return;
    frame = 0;
    for (c = 0; c != 3; c++) {
        if (wait[c]) { wait[c]--; continue; }
        n = *tp[c];
        if (n == 255) { tp[c] = (c == 0) ? song->lead : (c == 1) ? song->bass : song->drums; n = *tp[c]; }
        wait[c] = tp[c][1] - 1;
        tp[c] += 2;
        if (c == 0) {
            if (!n) NR22_REG = 0;
            else { f = note_freq[n]; NR21_REG = 0x80; NR22_REG = song->lead_env; NR23_REG = (uint8_t)f; NR24_REG = 0x80 | (f >> 8); }
        } else if (c == 1) {
            if (!n) NR32_REG = 0;
            else { f = note_freq[n]; NR32_REG = 0x20; NR33_REG = (uint8_t)f; NR34_REG = 0x80 | (f >> 8); }
        } else if (n == 1) { NR42_REG = 0x31; NR43_REG = 0x11; NR44_REG = 0x80; }     // hat
        else if (n == 2) { NR42_REG = 0x62; NR43_REG = 0x56; NR44_REG = 0x80; }       // kick
    }
}

void sound_init(void) {
    uint8_t i;
    NR52_REG = 0x80; NR50_REG = 0x77; NR51_REG = 0xFF;
    NR30_REG = 0;
    for (i = 0; i != 16; i++) ((uint8_t *)0xFF30)[i] = wave[i];
    NR30_REG = 0x80;
    CRITICAL { add_VBL(music_isr); }
}

void music_play(uint8_t id) {
    if (id == cur_song) return;
    playing = 0;
    song = &songs[id];
    tp[0] = song->lead; tp[1] = song->bass; tp[2] = song->drums;
    wait[0] = wait[1] = wait[2] = 0;
    frame = song->speed - 1;
    cur_song = id;
    playing = 1;
}

void music_stop(void) {
    playing = 0; cur_song = 255;
    NR22_REG = 0; NR32_REG = 0; NR42_REG = 0;
}

void sfx_note(uint8_t note, uint8_t duty, uint8_t envelope) {
    uint16_t f = note_freq[note];
    NR10_REG = 0; NR11_REG = duty; NR12_REG = envelope;
    NR13_REG = (uint8_t)f; NR14_REG = 0x80 | (f >> 8);
}
void sfx_off(void) { NR12_REG = 0; }
void sfx_blip(void) { sfx_note(61, 0x80, 0x71); }
void sfx_type(void) { sfx_note(54, 0x40, 0x21); }
void sfx_noise(uint8_t envelope, uint8_t pitch) { NR42_REG = envelope; NR43_REG = pitch; NR44_REG = 0x80; }
