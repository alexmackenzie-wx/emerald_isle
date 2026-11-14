#ifndef SOUND_H
#define SOUND_H
#include <gb/gb.h>
#include "gen/music_data.h"

void sound_init(void);
void music_play(uint8_t song);      // no-op if that song is already playing
void music_stop(void);
// Effects use pulse channel 1, which the music never touches.
void sfx_note(uint8_t note, uint8_t duty, uint8_t envelope);
void sfx_off(void);
void sfx_blip(void);                // advancing text, confirming
void sfx_type(void);                // a letter appearing, moving a cursor
void sfx_noise(uint8_t envelope, uint8_t pitch);
#endif
