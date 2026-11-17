// Emerald Isle - the shared engine core: state, text, drawing helpers, ambient
// effects, art loading and the battle transition. Everything here is linked
// into ROM bank 0, which is always mapped, so the overworld (bank 1) and the
// battle code (bank 5) can both use it.
#include <gbdk/font.h>
#include "core.h"

const map_t *cur;
uint8_t cur_id;                 // not static: the test scripts read these three from RAM
uint8_t px, py;                 // player tile position
uint8_t opx, opy;        // tile the player is stepping out of
uint16_t ppx, ppy;       // player pixel position (map space)
uint8_t dir, moving, steps, speed;
int16_t camx, camy;
uint8_t frame_count, prev_joy;
uint8_t blank_row[20];
char name[NAME_MAX + 1] = "JAMES";
uint8_t starter = NO_STARTER;
mon_t party[MAX_PARTY];
uint8_t party_n, torcs, win_keep;
uint8_t cards, shiny_cards;     // PMON cards collected: a bit per species, plain and shiny
uint16_t beaten, got;           // trainers beaten and pickups taken, beyond what the flags hold
uint8_t tms;                    // TMs owned, a bit each
uint8_t sodas;                  // Cream Sodas: each raises a PMON one level
uint8_t potions;                // not static: the test scripts read it
uint16_t flags;
uint16_t money;                 // in euro; won from trainers, spent in the Mart
uint16_t say_num;               // the number a '#' in dialogue stands for
char numbuf[6];
uint8_t ret_map, ret_x, ret_y;  // where a shared interior (Centre, Mart) sends you back to

char *numstr(uint16_t n) {      // n as decimal text
    uint8_t i = 5;
    numbuf[5] = 0;
    do { numbuf[--i] = '0' + n % 10; n /= 10; } while (n);
    return numbuf + i;
}
uint8_t map_ram[MAP_MAX];   // the current map's cells (up to 32x32), copied out of ROM bank 3
char text_buf[TEXT_MAX];    // the current piece of dialogue, likewise
uint8_t cur_tileset = 255;
uint8_t still;                  // set while a full-screen view (battle, pause, cards) hides the map
uint8_t art_buf[1024];
uint16_t rng = 0x1D2B;
// live NPC state (copied from the map so they can move)
uint8_t nx[MAX_NPC], ny[MAX_NPC], ndir[MAX_NPC], nmove[MAX_NPC], ntimer[MAX_NPC];
uint16_t npx[MAX_NPC], npy[MAX_NPC];
// ambient life: wind gusts and a butterfly
int16_t wx;                  // the whirling breeze
uint16_t wy;
uint8_t w_on, lean_x, lean_y, lean_t;
uint16_t w_wait = 200;
const int8_t wobble[8] = { 0, 3, 5, 3, 0, -3, -5, -3 };
uint16_t bx, by;
int8_t bvx, bvy;

// ---------------------------------------------------------------- helpers
uint8_t rnd(void) {
    rng = rng * 25173u + 13849u + DIV_REG;
    return rng >> 8;
}

void fill_attr(uint8_t pal) {
    VBK_REG = 1;
    fill_bkg_rect(0, 0, 32, 32, pal);
    fill_win_rect(0, 0, 32, 32, pal);
    VBK_REG = 0;
}

void rect(uint8_t x, uint8_t y, uint8_t w, uint8_t h, uint8_t tile, uint8_t attr) {
    VBK_REG = 1; fill_bkg_rect(x, y, w, h, attr);
    VBK_REG = 0; fill_bkg_rect(x, y, w, h, tile);
}

void print_bkg(uint8_t x, uint8_t y, const char *s) {
    while (*s) set_bkg_tile_xy(x++, y, *s++ - 32);
}

void print_centre(uint8_t x0, uint8_t w, uint8_t y, const char *s) {
    print_bkg(x0 + ((w - strlen(s)) >> 1), y, s);
}

// A small whirl of wind wanders across the map now and then. Grass, flowers
// and trees lean for a moment as it passes over them.
void set_cell(uint8_t x, uint8_t y, uint8_t lean) {
    uint8_t m = map_ram[y * cur->w + x], x0 = camx >> 4, y0 = camy >> 4;
    // the screen's tile memory holds a 16x16 window of the map that wraps round;
    // a cell outside what is on screen must not be drawn, or it lands on top of one that is
    if (x < x0 || x > x0 + 10 || y < y0 || y > y0 + 9) return;
    if (mt_sway[m] != m) set_bkg_tiles((x & 15) << 1, (y & 15) << 1, 2, 2, mt_tiles[lean ? mt_sway[m] : m]);
}

void ambient(void) {
    int16_t sx, sy, y;
    uint8_t cx, cy, ph, t, m;
    if ((frame_count & 31) == 0)
        set_bkg_data(WATER_TILE, 1, water_anim[(frame_count >> 5) & 1]);
    if (lean_t && !--lean_t) set_cell(lean_x, lean_y, 0);
    if (cur->weather) {
        for (cx = 16; cx != 24; cx++) {
            shadow_OAM[cx].y += 5; shadow_OAM[cx].x -= 2;
            if (shadow_OAM[cx].y > 150 || shadow_OAM[cx].y < 8) {
                shadow_OAM[cx].y = 8 + (rnd() & 15); shadow_OAM[cx].x = 16 + rnd() % 168;
                shadow_OAM[cx].tile = RAIN_TILE; shadow_OAM[cx].prop = 7;
            }
        }
    }
    if (!w_on) {
        if (!--w_wait) { w_on = 1; wx = -16; wy = 40 + ((uint16_t)rnd() << 1) % (cur->h * 16 - 96); }
        return;
    }
    wx++;
    y = wy + wobble[(frame_count >> 3) & 7];
    if (wx >= cur->w * 16) {
        w_on = 0; w_wait = 150 + rnd();
        move_sprite(36, 0, 0); move_sprite(37, 0, 0);
        return;
    }
    if (wx >= 0) {
        cx = (wx + 8) >> 4; cy = (y + 8) >> 4;
        if (cx < cur->w && cy < cur->h && (!lean_t || cx != lean_x || cy != lean_y)) {
            m = map_ram[cy * cur->w + cx];
            if (mt_sway[m] != m) {
                if (lean_t) set_cell(lean_x, lean_y, 0);
                set_cell(cx, cy, 1);
                lean_x = cx; lean_y = cy; lean_t = 18;
            }
        }
    }
    sx = wx - camx; sy = y - camy;
    if (sx < -16 || sx > 160 || sy < -16 || sy > 144) { move_sprite(36, 0, 0); move_sprite(37, 0, 0); return; }
    ph = (frame_count >> 3) & 3;                    // four frames: two drawings, each also turned 180
    t = ((ph & 1) ? F_WHIRL_B : F_WHIRL_A) << 2;
    set_sprite_tile(36, (ph & 2) ? t + 2 : t); set_sprite_tile(37, (ph & 2) ? t : t + 2);
    set_sprite_prop(36, 7 | ((ph & 2) ? S_FLIPX | S_FLIPY : 0));
    set_sprite_prop(37, 7 | ((ph & 2) ? S_FLIPX | S_FLIPY : 0));
    move_sprite(36, sx + 8, sy + 16); move_sprite(37, sx + 16, sy + 16);
}

void tick(void) {
    frame_count++;
    if (cur && cur->outdoor && !still) ambient();
    vsync();
}

uint8_t pressed(void) {      // buttons that went down this frame
    uint8_t joy = joypad(), p = joy & ~prev_joy;
    prev_joy = joy;
    return p;
}

void hide_sprites_from(uint8_t first) {
    uint8_t i;
    for (i = first; i != 40; i++) move_sprite(i, 0, 0);
}

// ---------------------------------------------------------------- dialog box
void win_clear(void) {
    uint8_t y;
    for (y = 1; y != 5; y++) set_win_tiles(1, y, 18, 1, blank_row);
}

void win_print(uint8_t x, uint8_t y, const char *s) {
    while (*s) set_win_tile_xy(x++, y, *s++ - 32);
}

void win_wait(void) { wait_ab(); }   // hold whatever is in the dialog box until A or B

uint8_t wait_ab(void) {      // returns 1 for A, 0 for B
    uint8_t blink = 0, j;
    while (joypad() & (J_A | J_B)) tick();
    while (!((j = joypad()) & (J_A | J_B))) {
        set_win_tile_xy(18, 4, (blink++ & 16) ? 0 : FR_ARROW);
        tick();
    }
    set_win_tile_xy(18, 4, 0);
    sfx_blip();
    return (j & J_A) ? 1 : 0;
}

// '\n' second line, '\f' new page, '@' player name, '$' partner name.
uint8_t say(const char *s) {
    uint8_t col = 1, row = 2, c, i, r;
    const char *sub = 0;
    set_win_tile_xy(0, 0, FR_TL); set_win_tile_xy(19, 0, FR_TR);
    set_win_tile_xy(0, 5, FR_BL); set_win_tile_xy(19, 5, FR_BR);
    for (i = 1; i != 19; i++) { set_win_tile_xy(i, 0, FR_T); set_win_tile_xy(i, 5, FR_B); }
    for (i = 1; i != 5; i++) { set_win_tile_xy(0, i, FR_L); set_win_tile_xy(19, i, FR_R); }
    win_clear();
    // the window draws under sprites, so tuck away anyone standing behind it
    for (i = 0; i != 40; i++) if (shadow_OAM[i].y > 100 || (cur && cur->weather && i >= 16 && i < 24)) move_sprite(i, 0, 0);     // ...and the rain
    move_win(7, 96);
    SHOW_WIN;
    while (joypad() & J_A) tick();
    while (1) {
        if (sub) { c = *sub++; if (!c) { sub = 0; continue; } }
        else {
            c = *s++;
            if (!c) break;
            if (c == '@') { sub = name; continue; }
            if (c == '$') { sub = species[starter].name; continue; }
            if (c == '#') { sub = numstr(say_num); continue; }
        }
        if (c == '\n') { row = 4; col = 1; }
        else if (c == '\f') { wait_ab(); win_clear(); row = 2; col = 1; }
        else {
            set_win_tile_xy(col++, row, c == '%' ? FR_EURO : c - 32);        // '%' prints a euro sign
            if (c != ' ' && (col & 1)) sfx_type();
            tick();
            if (!(joypad() & (J_A | J_B))) tick();
        }
    }
    r = wait_ab();
    if (!win_keep) HIDE_WIN;
    while (joypad() & (J_A | J_B)) tick();
    prev_joy = joypad();
    return r;
}

// ---------------------------------------------------------------- shared with the battle bank
// Everything from the top of this file down to here is also called by the battle
// code, which runs with ROM bank 5 switched in. So it must all sit in bank 0;
// tools/check_layout.py verifies that after every build. Keep it early in the file.
const palette_color_t white4[4] = { 0x7FFF, 0x7FFF, 0x7FFF, 0x7FFF };

// Landmark buildings and features are unique to one map. Their tiles live in
// VRAM bank 1 (128 upward), which battles and the card screen borrow for creature
// art, so they are reloaded whenever a map is entered after one of those.
uint8_t cur_extra = 255;
void load_extra(uint8_t map) {
    const uint8_t *src = extra_tiles[map];
    uint8_t n = extra_n[map], first = 128, k;
    if (!n || map == cur_extra) return;
    cur_extra = map;
    while (n) {
        k = n > 64 ? 64 : n;
        bank_copy(EXTRA_BANK, src, art_buf, (uint16_t)k << 4);
        VBK_REG = 1; set_bkg_data(first, k, art_buf); VBK_REG = 0;
        src += (uint16_t)k << 4; first += k; n -= k;
    }
}

// Creature pictures go to VRAM bank 1, so they never compete with map tiles.
// back = 1 asks for the view from behind (the caller checks the species has one).
void load_art(uint8_t sp, uint8_t first_tile, uint8_t back) {
    if (back) bank_copy(BACK_BANK, species_back[species[sp].back], art_buf, 1024);
    else if (sp < ART2_FROM) bank_copy(ART_BANK, species_art[sp], art_buf, 1024);
    else bank_copy(ART2_BANK, species_art2[sp - ART2_FROM], art_buf, 1024);
    VBK_REG = 1; set_bkg_data(first_tile, 64, art_buf); VBK_REG = 0;
    cur_extra = 255;            // the picture has overwritten any landmark tiles
}

// mask has one byte per tile row; a set bit means that tile uses the creature's
// second palette (pal2) instead of its main one.
void put_art(uint8_t x0, uint8_t y0, uint8_t first_tile, uint8_t pal, uint8_t pal2, const uint8_t *mask, uint8_t flip) {
    uint8_t x, y, sx, row[8], attr[8];
    for (y = 0; y != 8; y++) {          // a row at a time keeps the redraw quick enough to animate
        for (x = 0; x != 8; x++) {
            sx = flip ? 7 - x : x;
            row[x] = first_tile + (y << 3) + sx;
            attr[x] = ((mask[y] & (0x80 >> sx)) ? pal2 : pal) | 0x08 | (flip ? 0x20 : 0);
        }
        VBK_REG = 1; set_bkg_tiles(x0, y0 + y, 8, 1, attr);
        VBK_REG = 0; set_bkg_tiles(x0, y0 + y, 8, 1, row);
    }
}

const uint8_t cry_notes[N_SPECIES][6] = {
    { 18, 21, 25, 23, 18, 14 },     // Boveen: a low call that rises and droops
    { 58, 65, 61, 56, 52, 47 },     // Ruakit: a sharp yip, falling away
    { 49, 56, 52, 59, 56, 63 },     // Dovran: bubbling chirps, climbing
    { 44, 51, 44, 51, 47, 40 },     // Girrin: a squeaky thump-thump
    { 68, 72, 68, 72, 70, 66 },     // Spidge: a quick trill
    { 30, 28, 30, 27, 25, 25 },     // Granog: a low grumble
    { 37, 44, 49, 54, 52, 49 },     // Faolan: a rising howl
    { 40, 47, 40, 47, 40, 35 },     // Gandal: a two-note honk
    { 33, 33, 37, 33, 37, 30 },     // Dornan: a clacking mutter
    { 56, 54, 56, 52, 49, 49 },     // Puifin: a creaking growl, dropping
    { 42, 49, 54, 61, 54, 49 },     // Bradan: a rising splash of notes
    { 13, 11, 13, 9, 8, 8 },        // Gallan: stone grinding on stone
    { 66, 70, 66, 70, 73, 61 },     // Franca: a squeal
    { 44, 43, 42, 41, 47, 35 },     // Pucan: a sliding moan
    { 20, 15, 20, 13, 8, 6 } };     // Dullan: a knell
const uint8_t cry_len[N_SPECIES] = { 8, 3, 4, 3, 2, 5, 9, 5, 3, 7, 3, 9, 2, 8, 12 };
const uint8_t cry_duty[N_SPECIES] = { 0x40, 0x00, 0x80, 0x40, 0x80, 0x00, 0x80, 0x40, 0x00, 0x40, 0x80, 0x00, 0x00, 0x80, 0x40 };

void cry(uint8_t who, uint8_t shiny) {
    uint8_t i, f;
    if (who == 1) sfx_noise(0xA2, 0x33);
    for (i = 0; i != 6; i++) {
        sfx_note(cry_notes[who][i], cry_duty[who], 0xC0);
        for (f = 0; f != cry_len[who]; f++) { if (shiny) sparkle(); tick(); }
    }
    sfx_note(cry_notes[who][5], cry_duty[who], 0xC2);       // let the last note fade
}

// Into battle: the screen flashes, then black closes in from the edges in a spiral.
uint8_t wipe_n;
void wipe_cell(uint8_t x, uint8_t y) {
    x &= 31; y &= 31;
    VBK_REG = 1; set_bkg_tile_xy(x, y, P_UI);
    VBK_REG = 0; set_bkg_tile_xy(x, y, FR_BLACK);
    if (++wipe_n == 9) { wipe_n = 0; tick(); }
}

void battle_transition(void) {
    uint8_t i, n, x, y, l = 0, t = 0, r = 19, b = 17, x0 = camx >> 3, y0 = camy >> 3;
    hide_sprites_from(0);
    sfx_noise(0xF2, 0x51);
    for (i = 0; i != 6; i++) {
        if (i & 1) set_bkg_palette(0, 7, cur->pals);
        else for (n = 0; n != 7; n++) set_bkg_palette(n, 1, white4);
        for (n = 0; n != 4; n++) tick();
    }
    while (l <= r && t <= b) {
        for (x = l; x <= r; x++) wipe_cell(x0 + x, y0 + t);
        for (y = t + 1; y <= b; y++) wipe_cell(x0 + r, y0 + y);
        if (t != b) for (x = r; x-- > l; ) wipe_cell(x0 + x, y0 + b);
        if (l != r) for (y = b; y-- > t + 1; ) wipe_cell(x0 + l, y0 + y);
        l++; t++; r--; b--;
    }
    for (n = 0; n != 14; n++) tick();
}

// Graphics are stored in ROM bank 2. These routines sit in bank 0, so they can
// switch that bank in, take what they need, and switch back.
void bank_copy(uint8_t bank, const uint8_t *src, uint8_t *dst, uint16_t n) NONBANKED {
    uint16_t i;
    uint8_t old = CURRENT_BANK;     // the caller may be the overworld (bank 1) or a battle (bank 5)
    CRITICAL {
        SWITCH_ROM(bank);
        for (i = 0; i != n; i++) dst[i] = src[i];
        SWITCH_ROM(old);
    }
}

void load_text(uint8_t id) NONBANKED {
    const char *t;
    uint16_t i = 0;
    uint8_t old = CURRENT_BANK;
    CRITICAL {
        SWITCH_ROM(DATA_BANK);
        t = texts[id];
        do { text_buf[i] = t[i]; } while (t[i++]);
        SWITCH_ROM(old);
    }
}

uint8_t say_t(uint8_t id) { load_text(id); return say(text_buf); }

void load_gfx(void) NONBANKED {      // at boot, before the music interrupt exists
    SWITCH_ROM(ART_BANK);
    VBK_REG = 1; set_bkg_data(96, 9, bar_tiles); VBK_REG = 0;      // HP bar pieces, VRAM bank 1
    SWITCH_ROM(PIC_BANK);
    set_sprite_data(0, N_SPR_TILES, spr_tiles);
    VBK_REG = 1; set_sprite_data(0, N_SPR2_TILES, spr2_tiles); VBK_REG = 0;     // the second sheet of sprites
    SWITCH_ROM(1);
}

// Outdoor and indoor maps have their own tile sets, swapped in when you change area.
void load_tileset(uint8_t id) {
    const uint8_t *src = id ? bg_tiles_in : bg_tiles_out;
    uint8_t n = id ? N_TILES_IN : N_TILES_OUT, first = TILE_BASE, k;
    if (id == cur_tileset) return;
    cur_tileset = id;
    while (n) {
        k = n > 64 ? 64 : n;
        bank_copy(ART_BANK, src, art_buf, (uint16_t)k << 4);
        set_bkg_data(first, k, art_buf);
        src += (uint16_t)k << 4; first += k; n -= k;
    }
}

