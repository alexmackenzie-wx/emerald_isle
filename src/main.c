// Tir Beo (working title) - an original creature-collecting RPG set in Ireland.
// Slice 1: title screen + New Ross overworld (walking, collision, signs, an NPC).
#include <gb/gb.h>
#include <gb/cgb.h>
#include <gbdk/font.h>
#include <string.h>
#include "gen/assets.h"

#define DIR_DOWN 0
#define DIR_UP 1
#define DIR_LEFT 2
#define DIR_RIGHT 3

static uint8_t px, py;          // player tile position
static uint16_t ppx, ppy;       // player pixel position (map space)
static uint8_t dir, moving, steps, speed;
static int16_t camx, camy;
static uint8_t frame_count, prev_joy;
static uint8_t blank_row[20];

// ---------------------------------------------------------------- helpers
static void fill_attr(uint8_t pal) {
    VBK_REG = 1;
    fill_bkg_rect(0, 0, 32, 32, pal);
    fill_win_rect(0, 0, 32, 32, pal);
    VBK_REG = 0;
}

static void print_bkg(uint8_t x, uint8_t y, const char *s) {
    while (*s) set_bkg_tile_xy(x++, y, *s++ - 32);
}

static void animate_water(void) {
    if ((frame_count & 31) == 0)
        set_bkg_data(WATER_TILE, 1, water_anim[(frame_count >> 5) & 1]);
}

static void tick(void) {
    frame_count++;
    animate_water();
    vsync();
}

// ---------------------------------------------------------------- dialog box
static void clear_text(void) {
    uint8_t y;
    for (y = 1; y != 5; y++) set_win_tiles(1, y, 18, 1, blank_row);
}

static void wait_a(void) {
    uint8_t blink = 0;
    while (joypad() & (J_A | J_B)) tick();
    while (!(joypad() & (J_A | J_B))) {
        set_win_tile_xy(18, 4, (blink++ & 16) ? 0 : FR_ARROW);
        tick();
    }
    set_win_tile_xy(18, 4, 0);
}

static void say(const char *s) {
    uint8_t col = 1, row = 2, c, i;
    set_win_tile_xy(0, 0, FR_TL); set_win_tile_xy(19, 0, FR_TR);
    set_win_tile_xy(0, 5, FR_BL); set_win_tile_xy(19, 5, FR_BR);
    for (i = 1; i != 19; i++) { set_win_tile_xy(i, 0, FR_T); set_win_tile_xy(i, 5, FR_B); }
    for (i = 1; i != 5; i++) { set_win_tile_xy(0, i, FR_L); set_win_tile_xy(19, i, FR_R); }
    clear_text();
    // the window sits above sprites' BG, so tuck away any NPC standing behind it
    if (shadow_OAM[2].y > 100) { move_sprite(2, 0, 0); move_sprite(3, 0, 0); }
    move_win(7, 96);
    SHOW_WIN;
    while (joypad() & J_A) tick();
    while ((c = *s++)) {
        if (c == '\n') { row = 4; col = 1; }
        else if (c == '\f') { wait_a(); clear_text(); row = 2; col = 1; }
        else {
            set_win_tile_xy(col++, row, c - 32);
            tick();
            if (!(joypad() & (J_A | J_B))) tick();
        }
    }
    wait_a();
    HIDE_WIN;
    while (joypad() & (J_A | J_B)) tick();
}

// ---------------------------------------------------------------- map
static void draw_map(void) {
    uint8_t x, y, m;
    for (y = 0; y != MAP_H; y++)
        for (x = 0; x != MAP_W; x++) {
            m = town_map[y * MAP_W + x];
            VBK_REG = 1; set_bkg_tiles(x << 1, y << 1, 2, 2, mt_attr[m]);
            VBK_REG = 0; set_bkg_tiles(x << 1, y << 1, 2, 2, mt_tiles[m]);
        }
}

static uint8_t flags_at(uint8_t x, uint8_t y) {
    if (x == NPC_X && y == NPC_Y) return F_SOLID;
    return mt_flags[town_map[y * MAP_W + x]];
}

// ---------------------------------------------------------------- sprites
static void place(uint8_t id, uint8_t frame, uint8_t flip, uint8_t pal, int16_t sx, int16_t sy) {
    uint8_t t = frame << 2, prop = pal | (flip ? S_FLIPX : 0);
    if (sx < -16 || sx > 160 || sy < -16 || sy > 144) {
        move_sprite(id, 0, 0); move_sprite(id + 1, 0, 0);
        return;
    }
    set_sprite_tile(id, flip ? t + 2 : t);
    set_sprite_tile(id + 1, flip ? t : t + 2);
    set_sprite_prop(id, prop); set_sprite_prop(id + 1, prop);
    move_sprite(id, sx + 8, sy + 12);        // drawn 4px up for a little depth
    move_sprite(id + 1, sx + 16, sy + 12);
}

static void update_view(void) {
    uint8_t f;
    camx = (int16_t)ppx - 72; camy = (int16_t)ppy - 64;
    if (camx < 0) camx = 0;
    if (camx > MAP_W * 16 - 160) camx = MAP_W * 16 - 160;
    if (camy < 0) camy = 0;
    if (camy > MAP_H * 16 - 144) camy = MAP_H * 16 - 144;
    move_bkg(camx, camy);

    f = (dir == DIR_DOWN) ? 0 : (dir == DIR_UP) ? 3 : 6;
    if (moving > 8) f += (dir < DIR_LEFT) ? 1 + (steps & 1) : 1;
    place(0, f, dir == DIR_RIGHT, 0, ppx - camx, ppy - camy);
    place(2, 8, 0, 1, NPC_X * 16 - camx, NPC_Y * 16 - camy);
}

// ---------------------------------------------------------------- overworld
static void interact(uint8_t tx, uint8_t ty) {
    uint8_t i;
    for (i = 0; i != N_INTERACT; i++)
        if (interacts[i].x == tx && interacts[i].y == ty) { say(texts[interacts[i].text]); return; }
    if (flags_at(tx, ty) & F_DOOR) say(texts[TXT_LOCKED]);
}

static void overworld(void) {
    uint8_t joy, pressed;
    int8_t dx, dy;
    uint8_t tx, ty;

    while (1) {
        joy = joypad();
        pressed = joy & ~prev_joy;
        prev_joy = joy;

        if (moving) {
            if (dir == DIR_DOWN) ppy += speed; else if (dir == DIR_UP) ppy -= speed;
            else if (dir == DIR_LEFT) ppx -= speed; else ppx += speed;
            moving -= speed;
        } else {
            dx = 0; dy = 0;
            if (joy & J_DOWN) { dir = DIR_DOWN; dy = 1; }
            else if (joy & J_UP) { dir = DIR_UP; dy = -1; }
            else if (joy & J_LEFT) { dir = DIR_LEFT; dx = -1; }
            else if (joy & J_RIGHT) { dir = DIR_RIGHT; dx = 1; }

            if (pressed & J_A) {
                tx = px + (dir == DIR_RIGHT) - (dir == DIR_LEFT);
                ty = py + (dir == DIR_DOWN) - (dir == DIR_UP);
                if (tx < MAP_W && ty < MAP_H) { update_view(); interact(tx, ty); }
            } else if (dx || dy) {
                tx = px + dx; ty = py + dy;
                if (tx >= MAP_W || ty >= MAP_H) {       // unsigned wrap catches -1
                    update_view();
                    say(texts[dy < 0 ? TXT_NORTH : dy > 0 ? TXT_SOUTH : dx > 0 ? TXT_EAST : TXT_WEST]);
                } else if (!(flags_at(tx, ty) & F_SOLID)) {
                    px = tx; py = ty;
                    speed = (joy & J_B) ? 2 : 1;        // hold B to run
                    moving = 16; steps++;
                }
            }
        }
        update_view();
        tick();
    }
}

static void title(void) {
    uint8_t blink = 0;
    print_bkg(6, 4, "TIR  BEO");
    print_bkg(3, 6, "-- LIVING LAND --");
    print_bkg(2, 9, "A New Ross Adventure");
    print_bkg(1, 16, "working title  v0.1");
    SHOW_BKG; DISPLAY_ON;
    while (!(joypad() & (J_START | J_A))) {
        print_bkg(4, 13, (blink++ & 32) ? "            " : "PRESS  START");
        vsync();
    }
}

void main(void) {
    DISPLAY_OFF;
    font_init();
    font_load(font_spect);
    set_bkg_palette(0, 8, bg_pals);
    set_sprite_palette(0, 2, obj_pals);
    fill_attr(P_UI);
    title();

    DISPLAY_OFF;
    set_bkg_data(TILE_BASE, N_TILES, bg_tiles);
    set_sprite_data(0, N_SPR_TILES, spr_tiles);
    draw_map();
    px = START_X; py = START_Y; ppx = px * 16; ppy = py * 16; dir = DIR_DOWN;
    SPRITES_8x16;
    update_view();
    SHOW_BKG; SHOW_SPRITES; DISPLAY_ON;
    overworld();
}
