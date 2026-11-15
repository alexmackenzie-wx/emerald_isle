#ifndef CORE_H
#define CORE_H
// The shared engine core (src/core.c): state and routines used by both the
// overworld (bank 1) and the battle code (bank 5). It all sits in bank 0.
#include "game.h"

#define DIR_DOWN 0
#define DIR_UP 1
#define DIR_LEFT 2
#define DIR_RIGHT 3
#define NAME_MAX 7
#define MAX_NPC 4

extern const map_t *cur;
extern uint8_t cur_id;
extern uint8_t px, py;
extern uint8_t opx, opy;
extern uint16_t ppx, ppy;
extern uint8_t dir, moving, steps, speed;
extern int16_t camx, camy;
extern uint8_t frame_count, prev_joy;
extern uint8_t blank_row[20];
extern char name[NAME_MAX + 1];
extern uint8_t starter;
extern mon_t party[MAX_PARTY];
extern uint8_t party_n, torcs, win_keep;
extern uint8_t potions;
extern uint16_t flags;
extern uint8_t map_ram[256];
extern char text_buf[TEXT_MAX];
extern uint8_t cur_tileset;
extern uint8_t still;
extern uint8_t art_buf[1024];
extern uint16_t rng;
extern uint8_t nx[MAX_NPC], ny[MAX_NPC], ndir[MAX_NPC], nmove[MAX_NPC], ntimer[MAX_NPC];
extern uint16_t npx[MAX_NPC], npy[MAX_NPC];
extern int16_t wx;
extern uint8_t wy, w_on, lean_x, lean_y, lean_t;
extern uint16_t w_wait;
extern const int8_t wobble[8];
extern uint16_t bx, by;
extern int8_t bvx, bvy;
uint8_t rnd(void);
void fill_attr(uint8_t pal);
void rect(uint8_t x, uint8_t y, uint8_t w, uint8_t h, uint8_t tile, uint8_t attr);
void print_bkg(uint8_t x, uint8_t y, const char *s);
void print_centre(uint8_t x0, uint8_t w, uint8_t y, const char *s);
void set_cell(uint8_t x, uint8_t y, uint8_t lean);
void ambient(void);
void tick(void);
uint8_t pressed(void);
void hide_sprites_from(uint8_t first);
void win_clear(void);
void win_print(uint8_t x, uint8_t y, const char *s);
void win_wait(void);
uint8_t wait_ab(void);
uint8_t say(const char *s);
extern const palette_color_t white4[4];
void load_art(uint8_t sp, uint8_t first_tile, uint8_t back);
void put_art(uint8_t x0, uint8_t y0, uint8_t first_tile, uint8_t pal, uint8_t pal2, const uint8_t *mask, uint8_t flip);
extern const uint8_t cry_len[N_SPECIES];
extern const uint8_t cry_duty[N_SPECIES];
void cry(uint8_t who, uint8_t shiny);
extern uint8_t wipe_n;
void wipe_cell(uint8_t x, uint8_t y);
void battle_transition(void);
void bank_copy(uint8_t bank, const uint8_t *src, uint8_t *dst, uint16_t n) NONBANKED;
void load_text(uint8_t id) NONBANKED;
uint8_t say_t(uint8_t id);
void load_gfx(void) NONBANKED;
void load_tileset(uint8_t id);
void sparkle(void);             // lives with the card-pack code in bank 1; only called from there
#endif
