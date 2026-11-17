#ifndef GAME_H
#define GAME_H
#include <gb/gb.h>
#include <gb/cgb.h>
#include <string.h>
#include "gen/assets.h"
#include "sound.h"

#define NO_STARTER 255
#define MAX_PARTY 6
#define FLAG_TORCS 1        // Mom has handed over the first PBALLs
#define FLAG_LEFT_HOME 2    // the starter can no longer be re-rolled

typedef struct {
    uint8_t species, level;
    uint16_t hp, maxhp;
    uint32_t exp;
    uint8_t moves[4];
} mon_t;

extern char name[];
extern uint8_t starter, party_n, torcs, potions, win_keep, still;
extern uint16_t flags, got;
extern mon_t party[MAX_PARTY];
extern const palette_color_t white4[4];

uint8_t rnd(void);
void tick(void);
uint8_t pressed(void);
uint8_t say(const char *s);             // returns 1 if closed with A, 0 with B
uint8_t say_t(uint8_t id);              // the same, for a numbered piece of dialogue
void win_clear(void);
void win_wait(void);
void win_print(uint8_t x, uint8_t y, const char *s);
void rect(uint8_t x, uint8_t y, uint8_t w, uint8_t h, uint8_t tile, uint8_t attr);
void print_bkg(uint8_t x, uint8_t y, const char *s);
void hide_sprites_from(uint8_t first);
void load_art(uint8_t sp, uint8_t first_tile, uint8_t back);   // 64 tiles into VRAM bank 1
void put_art(uint8_t x0, uint8_t y0, uint8_t first_tile, uint8_t pal, uint8_t pal2, const uint8_t *mask, uint8_t flip);
void cry(uint8_t who, uint8_t shiny);
void battle_transition(void);
void open_pack(uint8_t boost) BANKED;     // cards.c
void binder(void) BANKED;
void bag(void) BANKED;                   // the ITEMS screen
void party_screen(void) BANKED;
void trainer_card(void) BANKED;
void teach(mon_t *m, uint8_t mv) BANKED;
void badge_scene(void) BANKED;
extern uint8_t art_buf[1024];
void bank_copy(uint8_t bank, const uint8_t *src, uint8_t *dst, uint16_t n) NONBANKED;

uint16_t calc_hp(uint8_t base, uint8_t lvl) BANKED;
void mon_init(mon_t *m, uint8_t sp, uint8_t lvl) BANKED;
void heal_party(void) BANKED;
void level_up(mon_t *m) BANKED;         // one level, as a Cream Soda gives
void present(uint8_t sp) BANKED;        // a PMON springs out of its PBall to meet you
// t is the opposing trainer, or 0 for a wild sp at level lvl; returns 1 if the player has no PMON left standing
uint8_t battle(uint8_t sp, uint8_t lvl, const trainer_t *t) BANKED;
uint8_t watch_battle(const trainer_t *t) BANKED;      // Alex fights it; you look on
#endif
