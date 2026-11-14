// Emerald Isle - an original creature-collecting RPG set in Ireland.
// Slice 2: title, name entry, James's house, the card pack opening, New Ross.
#include <gb/gb.h>
#include <gb/cgb.h>
#include <gbdk/font.h>
#include <string.h>
#include "gen/assets.h"

#define DIR_DOWN 0
#define DIR_UP 1
#define DIR_LEFT 2
#define DIR_RIGHT 3
#define NO_STARTER 255
#define NAME_MAX 7
#define MAX_NPC 4

static const map_t *cur;
static uint8_t cur_id;
static uint8_t px, py;          // player tile position
static uint16_t ppx, ppy;       // player pixel position (map space)
static uint8_t dir, moving, steps, speed;
static int16_t camx, camy;
static uint8_t frame_count, prev_joy;
static uint8_t blank_row[20];
static char name[NAME_MAX + 1] = "JAMES";
static uint8_t starter = NO_STARTER;
static uint16_t rng = 0x1D2B;

// ---------------------------------------------------------------- helpers
static uint8_t rnd(void) {
    rng = rng * 25173u + 13849u + DIV_REG;
    return rng >> 8;
}

static void fill_attr(uint8_t pal) {
    VBK_REG = 1;
    fill_bkg_rect(0, 0, 32, 32, pal);
    fill_win_rect(0, 0, 32, 32, pal);
    VBK_REG = 0;
}

static void rect(uint8_t x, uint8_t y, uint8_t w, uint8_t h, uint8_t tile, uint8_t attr) {
    VBK_REG = 1; fill_bkg_rect(x, y, w, h, attr);
    VBK_REG = 0; fill_bkg_rect(x, y, w, h, tile);
}

static void print_bkg(uint8_t x, uint8_t y, const char *s) {
    while (*s) set_bkg_tile_xy(x++, y, *s++ - 32);
}

static void print_centre(uint8_t x0, uint8_t w, uint8_t y, const char *s) {
    print_bkg(x0 + ((w - strlen(s)) >> 1), y, s);
}

static void tick(void) {
    frame_count++;
    if (cur_id == MAP_TOWN && (frame_count & 31) == 0)
        set_bkg_data(WATER_TILE, 1, water_anim[(frame_count >> 5) & 1]);
    vsync();
}

static uint8_t pressed(void) {      // buttons that went down this frame
    uint8_t joy = joypad(), p = joy & ~prev_joy;
    prev_joy = joy;
    return p;
}

static void hide_sprites_from(uint8_t first) {
    uint8_t i;
    for (i = first; i != 16; i++) move_sprite(i, 0, 0);
}

// ---------------------------------------------------------------- dialog box
static void clear_text(void) {
    uint8_t y;
    for (y = 1; y != 5; y++) set_win_tiles(1, y, 18, 1, blank_row);
}

static uint8_t wait_ab(void) {      // returns 1 for A, 0 for B
    uint8_t blink = 0, j;
    while (joypad() & (J_A | J_B)) tick();
    while (!((j = joypad()) & (J_A | J_B))) {
        set_win_tile_xy(18, 4, (blink++ & 16) ? 0 : FR_ARROW);
        tick();
    }
    set_win_tile_xy(18, 4, 0);
    return (j & J_A) ? 1 : 0;
}

// '\n' second line, '\f' new page, '@' player name, '$' partner name.
static uint8_t say(const char *s) {
    uint8_t col = 1, row = 2, c, i, r;
    const char *sub = 0;
    set_win_tile_xy(0, 0, FR_TL); set_win_tile_xy(19, 0, FR_TR);
    set_win_tile_xy(0, 5, FR_BL); set_win_tile_xy(19, 5, FR_BR);
    for (i = 1; i != 19; i++) { set_win_tile_xy(i, 0, FR_T); set_win_tile_xy(i, 5, FR_B); }
    for (i = 1; i != 5; i++) { set_win_tile_xy(0, i, FR_L); set_win_tile_xy(19, i, FR_R); }
    clear_text();
    // the window draws under sprites, so tuck away anyone standing behind it
    for (i = 0; i != 16; i++) if (shadow_OAM[i].y > 100) move_sprite(i, 0, 0);
    move_win(7, 96);
    SHOW_WIN;
    while (joypad() & J_A) tick();
    while (1) {
        if (sub) { c = *sub++; if (!c) { sub = 0; continue; } }
        else {
            c = *s++;
            if (!c) break;
            if (c == '@') { sub = name; continue; }
            if (c == '$') { sub = starter_cards[starter].name; continue; }
        }
        if (c == '\n') { row = 4; col = 1; }
        else if (c == '\f') { wait_ab(); clear_text(); row = 2; col = 1; }
        else {
            set_win_tile_xy(col++, row, c - 32);
            tick();
            if (!(joypad() & (J_A | J_B))) tick();
        }
    }
    r = wait_ab();
    HIDE_WIN;
    while (joypad() & (J_A | J_B)) tick();
    prev_joy = joypad();
    return r;
}

// ---------------------------------------------------------------- sprites + camera
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
    uint8_t f, i;
    const npc_t *n;
    camx = (int16_t)ppx - 72; camy = (int16_t)ppy - 64;
    if (camx > cur->w * 16 - 160) camx = cur->w * 16 - 160;
    if (camy > cur->h * 16 - 144) camy = cur->h * 16 - 144;
    if (camx < 0) camx = 0;
    if (camy < 0) camy = 0;
    move_bkg(camx, camy);

    f = (dir == DIR_DOWN) ? 0 : (dir == DIR_UP) ? 3 : 6;
    if (moving > 8) f += (dir < DIR_LEFT) ? 1 + (steps & 1) : 1;
    place(0, f, dir == DIR_RIGHT, 0, ppx - camx, ppy - camy);
    for (i = 0; i != cur->n_npc; i++) {
        n = &cur->npcs[i];
        place(2 + (i << 1), n->frame, n->flip, n->pal, n->x * 16 - camx, n->y * 16 - camy);
    }
}

// ---------------------------------------------------------------- maps
static void enter_map(uint8_t id, uint8_t x, uint8_t y) {
    uint8_t mx, my, m;
    DISPLAY_OFF;
    cur_id = id; cur = &maps[id];
    set_bkg_palette(0, 8, cur->pals);
    for (my = 0; my != cur->h; my++)
        for (mx = 0; mx != cur->w; mx++) {
            m = cur->data[my * cur->w + mx];
            VBK_REG = 1; set_bkg_tiles(mx << 1, my << 1, 2, 2, mt_attr[m]);
            VBK_REG = 0; set_bkg_tiles(mx << 1, my << 1, 2, 2, mt_tiles[m]);
        }
    px = x; py = y; ppx = x * 16; ppy = y * 16; moving = 0;
    hide_sprites_from(0);
    update_view();
    SHOW_BKG; SHOW_SPRITES; DISPLAY_ON;
}

static uint8_t flags_at(uint8_t x, uint8_t y) {
    uint8_t i;
    for (i = 0; i != cur->n_npc; i++)
        if (cur->npcs[i].x == x && cur->npcs[i].y == y) return F_SOLID;
    return mt_flags[cur->data[y * cur->w + x]];
}

// ---------------------------------------------------------------- name entry
static const char * const letters[3] = { "ABCDEFGHI", "JKLMNOPQR", "STUVWXYZ-" };

static void name_entry(void) {
    uint8_t cx = 0, cy = 0, len = strlen(name), p, i, done = 0;
    rect(0, 0, 20, 18, 0, P_UI);
    print_bkg(1, 1, "WHAT'S YOUR NAME?");
    for (i = 0; i != 3; i++)
        for (p = 0; p != 9; p++) set_bkg_tile_xy(2 + (p << 1), 7 + (i << 1), letters[i][p] - 32);
    print_bkg(3, 14, "DELETE");
    print_bkg(12, 14, "OK");
    print_bkg(1, 16, "A:pick B:del START");
    while (!done) {
        for (i = 0; i != NAME_MAX; i++) set_bkg_tile_xy(6 + i, 4, (i < len ? name[i] : '_') - 32);
        set_bkg_tile_xy(cy == 3 ? (cx < 5 ? 2 : 11) : 1 + (cx << 1), cy == 3 ? 14 : 7 + (cy << 1), '>' - 32);
        do { tick(); p = pressed(); } while (!p);
        set_bkg_tile_xy(cy == 3 ? (cx < 5 ? 2 : 11) : 1 + (cx << 1), cy == 3 ? 14 : 7 + (cy << 1), 0);
        if (p & J_RIGHT) { if (cy == 3) cx = 5; else cx = (cx + 1) % 9; }
        if (p & J_LEFT) { if (cy == 3) cx = 0; else cx = (cx + 8) % 9; }
        if (p & J_DOWN) cy = (cy + 1) & 3;
        if (p & J_UP) cy = (cy + 3) & 3;
        if (p & J_START) done = 1;
        if ((p & J_B) && len) len--;
        if (p & J_A) {
            if (cy == 3) { if (cx < 5) { if (len) len--; } else done = 1; }
            else if (len < NAME_MAX) name[len++] = letters[cy][cx];
        }
    }
    name[len] = 0;
    if (!len) strcpy(name, "JAMES");
}

// ---------------------------------------------------------------- card pack
#define CARD_X 4
#define CARD_Y 1
#define CARD_W 12
#define CARD_H 16
static const palette_color_t white4[4] = { 0x7FFF, 0x7FFF, 0x7FFF, 0x7FFF };
static const palette_color_t shiny_cols[6] = {
    RGB8(248, 200, 40), RGB8(248, 120, 60), RGB8(232, 72, 160),
    RGB8(120, 96, 232), RGB8(48, 176, 232), RGB8(72, 200, 96) };
static uint8_t spark_t;

static void sparkle(void) {         // rainbow frame + twinkles for the shiny card
    uint8_t i;
    spark_t++;
    if ((spark_t & 7) == 0) set_bkg_palette_entry(K_SHINY, 3, shiny_cols[(spark_t >> 3) % 6]);
    if ((spark_t & 3) == 0) {
        i = 10 + ((spark_t >> 2) & 3);
        set_sprite_tile(i, SPARK_TILE + ((spark_t & 16) ? 2 : 0));
        set_sprite_prop(i, 5);
        if ((spark_t & 31) < 4) move_sprite(i, 30 + rnd() % 108, 26 + rnd() % 120);
    }
}

static void draw_frame(uint8_t pal) {
    uint8_t i, x1 = CARD_X + CARD_W - 1, y1 = CARD_Y + CARD_H - 1;
    rect(CARD_X, CARD_Y, CARD_W, CARD_H, 0, K_CARD);
    VBK_REG = 1;
    fill_bkg_rect(CARD_X, CARD_Y, CARD_W, 1, pal); fill_bkg_rect(CARD_X, y1, CARD_W, 1, pal);
    fill_bkg_rect(CARD_X, CARD_Y, 1, CARD_H, pal); fill_bkg_rect(x1, CARD_Y, 1, CARD_H, pal);
    VBK_REG = 0;
    for (i = CARD_X + 1; i != x1; i++) { set_bkg_tile_xy(i, CARD_Y, FR_T); set_bkg_tile_xy(i, y1, FR_B); }
    for (i = CARD_Y + 1; i != y1; i++) { set_bkg_tile_xy(CARD_X, i, FR_L); set_bkg_tile_xy(x1, i, FR_R); }
    set_bkg_tile_xy(CARD_X, CARD_Y, FR_TL); set_bkg_tile_xy(x1, CARD_Y, FR_TR);
    set_bkg_tile_xy(CARD_X, y1, FR_BL); set_bkg_tile_xy(x1, y1, FR_BR);
}

// Card art lives in VRAM bank 1 (tiles 128+), so it never competes with map tiles.
static void draw_art(const uint8_t *data, uint8_t size, uint8_t x0, uint8_t y0, uint8_t pal) {
    uint8_t x, y, t = 128;
    VBK_REG = 1; set_bkg_data(128, size * size, data); VBK_REG = 0;
    for (y = 0; y != size; y++)
        for (x = 0; x != size; x++, t++) {
            VBK_REG = 1; set_bkg_tile_xy(x0 + x, y0 + y, pal | 0x08);
            VBK_REG = 0; set_bkg_tile_xy(x0 + x, y0 + y, t);
        }
}

static void draw_card(uint8_t shiny, uint8_t which) {
    const card_t *c = shiny ? &starter_cards[which] : &icon_cards[which];
    draw_frame(shiny ? K_SHINY : K_CARD);
    print_centre(CARD_X, CARD_W, CARD_Y + 1, c->name);
    if (shiny) {
        draw_art(starter_art[which], 8, CARD_X + 2, CARD_Y + 3, c->pal);
        print_centre(CARD_X, CARD_W, CARD_Y + 12, c->type);
        print_centre(CARD_X, CARD_W, CARD_Y + 14, "* SHINY *");
    } else {
        rect(CARD_X + 2, CARD_Y + 3, 8, 8, 0, c->pal);
        draw_art(icon_art[which], 4, CARD_X + 4, CARD_Y + 5, c->pal);
        print_centre(CARD_X, CARD_W, CARD_Y + 13, c->type);
    }
}

static void slide(uint8_t from, uint8_t shiny) {    // 0 -> 128 exits left, 128 -> 0 enters from the right
    uint8_t i;
    for (i = 0; i != 17; i++) {
        move_bkg(from + (i << 3), 0);
        if (shiny) sparkle();
        tick();
    }
}

static void wait_card(uint8_t shiny) {
    while (joypad() & J_A) { if (shiny) sparkle(); tick(); }
    while (!(joypad() & J_A)) { if (shiny) sparkle(); tick(); }
}

static void open_pack(void) {
    uint8_t i, pick, order[3];
    DISPLAY_OFF;
    hide_sprites_from(0);
    set_bkg_palette(0, 8, pack_pals);
    rect(0, 0, 32, 32, 0, K_DARK);
    move_bkg(0, 0);
    // the sealed pack
    rect(6, 2, 8, 12, PK_FOIL, K_FOIL);
    fill_bkg_rect(6, 2, 8, 1, PK_CRIMP); fill_bkg_rect(6, 13, 8, 1, PK_CRIMP);
    fill_bkg_rect(6, 5, 8, 1, PK_GOLD); fill_bkg_rect(6, 10, 8, 1, PK_GOLD);
    fill_bkg_rect(6, 6, 8, 4, 0);
    print_bkg(6, 7, "EMERALD"); print_bkg(8, 8, "ISLE");
    print_bkg(4, 16, "A: OPEN PACK");
    DISPLAY_ON;
    while (joypad() & J_A) tick();
    while (!(joypad() & J_A)) tick();

    for (i = 0; i != 44; i++) {                     // shake, harder as it goes
        move_bkg((i & 2) ? (i >> 3) + 1 : 255 - (i >> 3), 0);
        tick();
    }
    for (i = 0; i != 7; i++) set_bkg_palette(i, 1, white4);     // flash
    move_bkg(0, 0);
    rect(0, 0, 32, 18, 0, K_DARK);

    pick = rnd() % 3;
    order[0] = rnd() % 3; order[1] = (order[0] + 1 + (rnd() & 1)) % 3; order[2] = 3 - order[0] - order[1];
    move_bkg(128, 0);
    for (i = 0; i != 4; i++) {
        draw_card(i == 3, i == 3 ? pick : order[i]);
        if (i == 0) set_bkg_palette(0, 8, pack_pals);
        if (i == 3) { for (; frame_count & 31; ) tick(); }   // a beat before the last card
        slide(128, i == 3);
        wait_card(i == 3);
        if (i != 3) slide(0, 0);
    }
    starter = pick;
    hide_sprites_from(10);
    say(texts[TXT_GOT]);
}

// ---------------------------------------------------------------- overworld
static void use_pack(void) {
    if (starter != NO_STARTER && !say(texts[TXT_PACK_AGAIN])) return;
    open_pack();
    enter_map(cur_id, px, py);
}

static void interact(uint8_t tx, uint8_t ty) {
    uint8_t i, t;
    for (i = 0; i != cur->n_npc; i++)
        if (cur->npcs[i].x == tx && cur->npcs[i].y == ty) {
            say(texts[starter == NO_STARTER ? cur->npcs[i].text0 : cur->npcs[i].text1]);
            return;
        }
    for (i = 0; i != cur->n_int; i++)
        if (cur->ints[i].x == tx && cur->ints[i].y == ty) {
            t = cur->ints[i].text;
            if (t == TXT_PACK) use_pack(); else say(texts[t]);
            return;
        }
    if (flags_at(tx, ty) & F_DOOR) say(texts[TXT_LOCKED]);
}

static const warp_t *warp_at(uint8_t x, uint8_t y) {
    uint8_t i;
    for (i = 0; i != cur->n_warp; i++)
        if (cur->warps[i].x == x && cur->warps[i].y == y) return &cur->warps[i];
    return 0;
}

static void overworld(void) {
    uint8_t joy, p, tx, ty, e;
    int8_t dx, dy;
    const warp_t *w;

    while (1) {
        joy = joypad();
        p = joy & ~prev_joy;
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

            if (p & J_A) {
                tx = px + (dir == DIR_RIGHT) - (dir == DIR_LEFT);
                ty = py + (dir == DIR_DOWN) - (dir == DIR_UP);
                if (tx < cur->w && ty < cur->h) { update_view(); interact(tx, ty); }
            } else if (dx || dy) {
                tx = px + dx; ty = py + dy;
                update_view();
                if (tx >= cur->w || ty >= cur->h) {     // unsigned wrap catches -1
                    e = cur->edge[dy < 0 ? 0 : dy > 0 ? 1 : dx > 0 ? 2 : 3];
                    if (e != NO_TEXT) say(texts[e]);
                } else if ((w = warp_at(tx, ty))) {
                    if (cur_id == MAP_HOME && starter == NO_STARTER) say(texts[TXT_MOM0]);
                    else enter_map(w->map, w->tx, w->ty);
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
    print_bkg(4, 4, "EMERALD ISLE");
    print_bkg(4, 6, "------------");
    print_bkg(0, 9, "A New Ross Adventure");
    print_bkg(5, 16, "build v0.3");
    SHOW_BKG; DISPLAY_ON;
    while (!(joypad() & (J_START | J_A))) {
        print_bkg(4, 13, (blink++ & 32) ? "            " : "PRESS  START");
        rnd();
        vsync();
    }
    while (joypad()) vsync();
    prev_joy = 0;
}

void main(void) {
    DISPLAY_OFF;
    cur_id = 255;
    font_init();
    font_load(font_spect);
    set_bkg_palette(0, 8, bg_pals);
    set_sprite_palette(0, 6, obj_pals);
    set_bkg_data(TILE_BASE, N_TILES, bg_tiles);
    set_sprite_data(0, N_SPR_TILES, spr_tiles);
    SPRITES_8x16;
    fill_attr(P_UI);
    title();
    name_entry();

    dir = DIR_UP;
    enter_map(MAP_HOME, 4, 6);
    say(texts[TXT_INTRO]);
    overworld();
}
