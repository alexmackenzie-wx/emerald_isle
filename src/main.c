// Emerald Isle - an original creature-collecting RPG set in Ireland.
// The overworld: maps, characters, the card pack, saving, the pause and title screens.
// This file lives in ROM bank 1, which is mapped whenever a battle is not running.
#pragma bank 1
#include <gbdk/font.h>
#include "core.h"

// Explore mode, for testing: no wild encounters, no trainer battles, you can walk
// through people, and the pause screen can jump between maps. Never saved.
static uint8_t explore;
static const uint8_t spawn[][2] = { {12, 13}, {4, 6}, {9, 14}, {7, 14}, {1, 4}, {4, 7}, {4, 7}, {4, 7} };   // a safe spot on each map

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
    uint8_t f, i, d;
    int16_t sy;
    const npc_t *n;
    camx = (int16_t)ppx - 72; camy = (int16_t)ppy - 64;
    if (camx > cur->w * 16 - 160) camx = cur->w * 16 - 160;
    if (camy > cur->h * 16 - 144) camy = cur->h * 16 - 144;
    if (camx < 0) camx = 0;
    if (camy < 0) camy = 0;
    move_bkg(camx, camy);

    // long grass closes over the player's legs, and rustles as they step in
    f = (moving > 8) ? opx : px; i = (moving > 8) ? opy : py;
    if (mt_flags[map_ram[i * cur->w + f]] & F_GRASS)
        place(0, moving ? F_GRASS_A : F_GRASS_B, 0, 6, f * 16 - camx, i * 16 - camy);
    else { move_sprite(0, 0, 0); move_sprite(1, 0, 0); }

    f = (dir == DIR_DOWN) ? 0 : (dir == DIR_UP) ? 3 : 6;
    if (moving > 8) f += (dir < DIR_LEFT) ? 1 + (steps & 1) : 1;
    place(2, f, dir == DIR_RIGHT, 0, ppx - camx, ppy - camy);
    for (i = 0; i != cur->n_npc; i++) {
        n = &cur->npcs[i];
        sy = npy[i] - camy;
        if (nx[i] == 255) { move_sprite(4 + (i << 1), 0, 0); move_sprite(5 + (i << 1), 0, 0); }
        else if (n->anim) place(4 + (i << 1), n->frame + (n->anim == 2 ? (frame_count >> 5) & 1 : (frame_count >> 3) % 3 == 0),
                                n->flip, n->pal, npx[i] - camx, sy);
        else if (n->wander) {
            d = ndir[i];
            f = (d == DIR_DOWN) ? 0 : (d == DIR_UP) ? 3 : 6;
            if (nmove[i] > 8) f += (d < DIR_LEFT) ? 1 + ((nx[i] + ny[i]) & 1) : 1;
            place(4 + (i << 1), f, d == DIR_RIGHT, n->pal, npx[i] - camx, sy);
        } else {
            if (((frame_count + i * 41) & 127) < 10) sy--;      // a little idle bob
            place(4 + (i << 1), n->frame, n->flip, n->pal, npx[i] - camx, sy);
        }
    }
    if (cur->outdoor && !cur->weather) {
        set_sprite_tile(12, BFLY_TILE + ((frame_count & 8) ? 2 : 0));
        set_sprite_prop(12, 5);
        if (bx + 8 > camx && bx < camx + 160 && by + 16 > camy && by < camy + 144)
            move_sprite(12, bx - camx + 8, by - camy + 16);
        else move_sprite(12, 0, 0);
    }
}

// ---------------------------------------------------------------- maps
static void enter_map(uint8_t id, uint8_t x, uint8_t y) {
    uint8_t mx, my, m;
    DISPLAY_OFF;
    cur_id = id; cur = &maps[id];
    load_tileset(cur->tileset);
    load_extra(id);
    bank_copy(DATA_BANK, map_cells[id], map_ram, 256);
    set_bkg_palette(0, 8, cur->pals);
    for (my = 0; my != cur->h; my++)
        for (mx = 0; mx != cur->w; mx++) {
            m = map_ram[my * cur->w + mx];
            VBK_REG = 1; set_bkg_tiles(mx << 1, my << 1, 2, 2, mt_attr[m]);
            VBK_REG = 0; set_bkg_tiles(mx << 1, my << 1, 2, 2, mt_tiles[m]);
        }
    for (mx = 0; mx != cur->n_npc; mx++) {
        nx[mx] = (flags & cur->npcs[mx].hide) ? 255 : cur->npcs[mx].x;     // 255 = not here
        ny[mx] = cur->npcs[mx].y;
        npx[mx] = nx[mx] * 16; npy[mx] = ny[mx] * 16;
        ndir[mx] = DIR_DOWN; nmove[mx] = 0; ntimer[mx] = 90;
    }
    w_on = 0; w_wait = 120; lean_t = 0; still = 0;
    music_play(cur->outdoor ? SONG_TOWN : SONG_HOME);
    bx = 12 * 16; by = 9 * 16;
    px = x; py = y; opx = x; opy = y; ppx = x * 16; ppy = y * 16; moving = 0;
    hide_sprites_from(0);
    update_view();
    SHOW_BKG; SHOW_SPRITES; DISPLAY_ON;
}

static uint8_t flags_at(uint8_t x, uint8_t y) {
    uint8_t i;
    for (i = 0; i != cur->n_npc; i++)
        if (nx[i] == x && ny[i] == y && !explore) return F_SOLID;
    return mt_flags[map_ram[y * cur->w + x]];
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
        if (p & (J_A | J_B | J_START)) sfx_blip(); else sfx_type();
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
static const palette_color_t shiny_cols[6] = {
    RGB8(248, 200, 40), RGB8(248, 120, 60), RGB8(232, 72, 160),
    RGB8(120, 96, 232), RGB8(48, 176, 232), RGB8(72, 200, 96) };
static uint8_t spark_t;

void sparkle(void) {         // rainbow frame + twinkles for the shiny card
    uint8_t i;
    spark_t++;
    if ((spark_t & 7) == 0) set_bkg_palette_entry(K_SHINY, 3, shiny_cols[(spark_t >> 3) % 6]);
    if ((spark_t & 3) == 0) {
        i = 12 + ((spark_t >> 2) & 3);
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

static void draw_icon(const uint8_t *data, uint8_t x0, uint8_t y0, uint8_t pal) {
    uint8_t x, y, t = 128;
    bank_copy(ART_BANK, data, art_buf, 256);
    VBK_REG = 1; set_bkg_data(128, 16, art_buf); VBK_REG = 0;
    cur_extra = 255;
    for (y = 0; y != 4; y++)
        for (x = 0; x != 4; x++, t++) {
            VBK_REG = 1; set_bkg_tile_xy(x0 + x, y0 + y, pal | 0x08);
            VBK_REG = 0; set_bkg_tile_xy(x0 + x, y0 + y, t);
        }
}

static void draw_card(uint8_t shiny, uint8_t which) {
    const card_t *c = shiny ? &starter_cards[which] : &icon_cards[which];
    draw_frame(shiny ? K_SHINY : K_CARD);
    print_centre(CARD_X, CARD_W, CARD_Y + 1, c->name);
    if (shiny) {
        load_art(which, 128, 0);
        set_bkg_palette(K_FOIL, 1, art_pals2[which]);       // the foil pack is off screen by now
        put_art(CARD_X + 2, CARD_Y + 3, 128, c->pal, K_FOIL, art_mask[which], 0);
        print_centre(CARD_X, CARD_W, CARD_Y + 12, c->type);
        print_centre(CARD_X, CARD_W, CARD_Y + 14, "* SHINY *");
    } else {
        rect(CARD_X + 2, CARD_Y + 3, 8, 8, 0, c->pal);
        draw_icon(icon_art[which], CARD_X + 4, CARD_Y + 5, c->pal);
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

// Each creature has its own cry: a short run of notes on the effects channel.
static void open_pack(void) {
    uint8_t i, pick, order[3];
    DISPLAY_OFF;
    music_stop();
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
        if ((i & 3) == 0) sfx_note(30 + (i >> 1), 0x80, 0x51);      // rising rattle
        tick();
    }
    sfx_noise(0xF3, 0x62);                                      // the pack tears open
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
        sfx_noise(0x41, 0x22);                                  // card slides in
        slide(128, i == 3);
        if (i == 3) cry(pick, 1);
        wait_card(i == 3);
        if (i != 3) slide(0, 0);
    }
    starter = pick;
    hide_sprites_from(12);
    say_t(TXT_GOT);
}

// ---------------------------------------------------------------- overworld
static void use_pack(void) {
    if (flags & FLAG_LEFT_HOME) { say_t(TXT_PACK_DONE); return; }
    if (starter != NO_STARTER && !say_t(TXT_PACK_AGAIN)) return;
    open_pack();
    mon_init(&party[0], starter, 5);
    party_n = 1;
    enter_map(cur_id, px, py);
}

static void heal_jingle(void) {
    uint8_t i, f;
    static const uint8_t n[5] = { 49, 49, 56, 53, 61 };
    for (i = 0; i != 5; i++) { sfx_note(n[i], 0x80, 0x92); for (f = 0; f != 7; f++) tick(); }
}

static const uint8_t aria[8] = { 49, 53, 56, 61, 60, 56, 58, 61 };
static void perform(uint8_t what) { // 0: a bar of jig rhythm on the bodhran; 1: a phrase of an aria
    uint8_t i, f;
    if (what) music_stop();
    for (i = 0; i != (what ? 8 : 12); i++) {
        if (what) sfx_note(aria[i], 0x80, 0xC4);
        else sfx_noise((i % 3 == 0) ? 0x91 : 0x41, (i % 3 == 0) ? 0x55 : 0x45);
        for (f = 0; f != (what ? 18 : 7); f++) { update_view(); tick(); }
    }
    if (what) { sfx_off(); music_play(SONG_HOME); }
}

static void after_battle(uint8_t lost) {
    if (lost) {                     // everyone fainted: wake up at home, patched up
        heal_party();
        enter_map(MAP_HOME, 4, 6);
        dir = DIR_UP;
        update_view();
        say_t(TXT_BLACKOUT);
    } else enter_map(cur_id, px, py);
}

static void run_trainer(uint8_t id) {
    const trainer_t *t = &trainers[id];
    uint8_t lost;
    still = 1;
    lost = battle(0, 0, t);
    if (!lost) { flags |= t->flag; torcs += t->prize; }
    after_battle(lost);
    if (!lost) say_t(t->text_win);
}

static void talk(uint8_t i) {
    const npc_t *n = &cur->npcs[i];
    uint8_t lost;
    if (n->wander) { ndir[i] = dir ^ 1; update_view(); }       // turn to face you
    if (n->script == 3) perform(n->param);
    if (n->script == 5) {                                       // a one-off gift of potions (flag bit in sight)
        if (flags & ((uint16_t)1 << n->sight)) say_t(n->text1);
        else { flags |= (uint16_t)1 << n->sight; potions += n->param; sfx_blip(); say_t(n->text0); }
        return;
    }
    if (n->script == 2) {                                       // a trainer: battle once, then small talk
        if (explore) say_t(n->text0);                           // explore mode: all talk, no battle
        else if (flags & trainers[n->param].flag) say_t(n->text1);
        else { say_t(n->text0); run_trainer(n->param); }
        return;
    }
    say_t(starter == NO_STARTER ? n->text0 : n->text1);
    if (n->script == 1 && starter != NO_STARTER) {             // Mom and Ruth look after your PMONs
        heal_party();
        heal_jingle();
        say_t(TXT_HEALED);
        if (n->param && !(flags & FLAG_TORCS)) { flags |= FLAG_TORCS; torcs += 5; say_t(TXT_MOM_TORCS); }
    } else if (n->script == 4 && !explore) {                    // woken up: param = species, sight = level
        still = 1;
        lost = battle(n->param, n->sight, 0);
        if (!lost) flags |= n->hide;
        after_battle(lost);
    }
}

// A trainer looking down the path spots you walking up it.
static void check_sight(void) {
    uint8_t i, f;
    const npc_t *n;
    if (explore) return;
    for (i = 0; i != cur->n_npc; i++) {
        n = &cur->npcs[i];
        if (n->script != 2 || !n->sight || nx[i] != px || py <= ny[i] || py - ny[i] > n->sight) continue;
        if (flags & trainers[n->param].flag) continue;
        dir = DIR_UP;
        update_view();
        set_sprite_tile(15, BANG_TILE); set_sprite_prop(15, 1);
        move_sprite(15, npx[i] - camx + 12, npy[i] - camy + 2);
        sfx_note(61, 0x80, 0xA2);
        for (f = 0; f != 45; f++) tick();
        move_sprite(15, 0, 0);
        say_t(n->text0);
        run_trainer(n->param);
        return;
    }
}

static void interact(uint8_t tx, uint8_t ty) {
    uint8_t i, t;
    for (i = 0; i != cur->n_npc; i++)
        if (nx[i] == tx && ny[i] == ty) { talk(i); return; }
    for (i = 0; i != cur->n_int; i++)
        if (cur->ints[i].x == tx && cur->ints[i].y == ty) {
            t = cur->ints[i].text;
            if (t == TXT_PACK) use_pack();
            else if (!cur->ints[i].flag) say_t(t);
            else if (flags & cur->ints[i].flag) say_t(TXT_EMPTY);
            else { flags |= cur->ints[i].flag; torcs += cur->ints[i].give; sfx_blip(); say_t(t); }     // a one-off find
            return;
        }
    if (flags_at(tx, ty) & F_DOOR) say_t(TXT_LOCKED);
}

static const warp_t *warp_at(uint8_t x, uint8_t y) {
    uint8_t i;
    for (i = 0; i != cur->n_warp; i++)
        if (cur->warps[i].x == x && cur->warps[i].y == y) return &cur->warps[i];
    return 0;
}

static void update_life(void) {
    uint8_t i, d, tx, ty;
    for (i = 0; i != cur->n_npc; i++) {
        if (!cur->npcs[i].wander || nx[i] == 255) continue;
        if (nmove[i]) {
            d = ndir[i];
            if (d == DIR_DOWN) npy[i]++; else if (d == DIR_UP) npy[i]--;
            else if (d == DIR_LEFT) npx[i]--; else npx[i]++;
            nmove[i]--;
        } else if (!--ntimer[i]) {
            ntimer[i] = 50 + (rnd() & 127);
            d = rnd() & 3;
            ndir[i] = d;
            tx = nx[i] + (d == DIR_RIGHT) - (d == DIR_LEFT);
            ty = ny[i] + (d == DIR_DOWN) - (d == DIR_UP);
            // stay near home, off the long grass, and out of everyone's way
            if (tx < cur->w && ty < cur->h && tx + 2 >= cur->npcs[i].x && tx <= cur->npcs[i].x + 2
                && ty + 2 >= cur->npcs[i].y && ty <= cur->npcs[i].y + 2 && !(tx == px && ty == py)
                && !(flags_at(tx, ty) & (F_SOLID | F_GRASS)) && !warp_at(tx, ty)) {
                nx[i] = tx; ny[i] = ty; nmove[i] = 16;
            }
        }
    }
    if (cur->outdoor) {             // the butterfly drifts about
        if ((frame_count & 15) == 0) { bvx = (rnd() % 3) - 1; bvy = (rnd() % 3) - 1; }
        if (frame_count & 1) {
            bx += bvx; by += bvy;
            if (bx < 72) bx = 72;
            if (bx > 232) bx = 232;
            if (by < 24) by = 24;
            if (by > 232) by = 232;
        }
    }
}

// ---------------------------------------------------------------- save game (battery RAM)
typedef struct {
    uint8_t magic;
    char name[NAME_MAX + 1];
    uint8_t starter, torcs, party_n, map, x, y, dir, potions;
    uint16_t flags;
    mon_t party[MAX_PARTY];
    uint8_t sum;
} save_t;
#define SAV ((save_t *)0xA000)
#define SAVE_MAGIC 0xE3

static uint8_t save_sum(void) {
    const uint8_t *p = (const uint8_t *)SAV;
    uint8_t n = sizeof(save_t) - 1, s = 0x5A;
    while (n--) s += *p++;
    return s;
}

static void save_game(void) {
    ENABLE_RAM; SWITCH_RAM(0);
    SAV->magic = SAVE_MAGIC;
    memcpy(SAV->name, name, NAME_MAX + 1);
    SAV->potions = potions; SAV->starter = starter; SAV->flags = flags; SAV->torcs = torcs; SAV->party_n = party_n;
    SAV->map = cur_id; SAV->x = px; SAV->y = py; SAV->dir = dir;
    memcpy(SAV->party, party, sizeof(party));
    SAV->sum = save_sum();
    DISABLE_RAM;
}

static uint8_t save_exists(void) {
    uint8_t ok;
    ENABLE_RAM; SWITCH_RAM(0);
    ok = SAV->magic == SAVE_MAGIC && SAV->sum == save_sum();
    DISABLE_RAM;
    return ok;
}

static void load_game(void) {       // call only when save_exists()
    uint8_t m, x, y;
    ENABLE_RAM; SWITCH_RAM(0);
    memcpy(name, SAV->name, NAME_MAX + 1);
    potions = SAV->potions; starter = SAV->starter; flags = SAV->flags; torcs = SAV->torcs; party_n = SAV->party_n;
    m = SAV->map; x = SAV->x; y = SAV->y; dir = SAV->dir;
    memcpy(party, SAV->party, sizeof(party));
    DISABLE_RAM;
    enter_map(m, x, y);
}

// ---------------------------------------------------------------- pause screen
static void print_num(uint8_t x, uint8_t y, uint16_t n) {      // right-aligned, 3 wide
    uint8_t i;
    for (i = 3; i--; ) { set_bkg_tile_xy(x + i, y, (n || i == 2) ? '0' + n % 10 - 32 : 0); n /= 10; }
}

static void pause_screen(void) {
    uint8_t i, p, k;
    uint32_t need;
    still = 1;
    DISPLAY_OFF;
    hide_sprites_from(0);
    move_bkg(0, 0);
    rect(0, 0, 20, 18, 0, P_UI);
    print_bkg(1, 1, name); print_bkg(9, 1, "PBALLS"); print_num(16, 1, torcs);
    print_bkg(1, 3, "PMON     LV   HP");
    for (i = 0; i != party_n; i++) {
        print_bkg(1, 5 + (i << 1), species[party[i].species].name);
        print_num(9, 5 + (i << 1), party[i].level);
        print_num(13, 5 + (i << 1), party[i].hp);
        set_bkg_tile_xy(16, 5 + (i << 1), '/' - 32);
        print_num(17, 5 + (i << 1), party[i].maxhp);
        need = (uint32_t)(party[i].level + 1) * (party[i].level + 1) * (party[i].level + 1);       // XP for the next level
        need = need > party[i].exp ? need - party[i].exp : 0;
        print_bkg(3, 6 + (i << 1), "next Lv in");
        for (k = 5; k--; ) { set_bkg_tile_xy(13 + k, 6 + (i << 1), (need || k == 4) ? '0' + need % 10 - 32 : 0); need /= 10; }
        print_bkg(18, 6 + (i << 1), "XP");
    }
    if (flags & FLAG_BADGE) print_bkg(1, 2, "FEATHER BADGE");
    if (potions) { print_bkg(1, 15, "<:use POTION x"); print_num(14, 15, potions); }
    print_bkg(1, 16, explore ? "EXPLORE: >=next map" : "SELECT:explore mode");
    print_bkg(1, 17, "A:SAVE     B:BACK");
    DISPLAY_ON;
    while (1) {
        do { tick(); p = pressed(); } while (!p);
        if (p & J_A) { save_game(); sfx_blip(); say_t(TXT_SAVED); }
        else if (p & (J_B | J_START)) break;
        else if ((p & J_LEFT) && potions) {         // a potion: 20 HP for the first hurt PMON still standing
            for (i = 0; i != party_n; i++) if (party[i].hp && party[i].hp < party[i].maxhp) break;
            if (i == party_n) { say_t(TXT_NOPOTION); continue; }
            potions--;
            party[i].hp += 20;
            if (party[i].hp > party[i].maxhp) party[i].hp = party[i].maxhp;
            sfx_blip();
            say_t(TXT_POTION);
            pause_screen();                         // redraw with the new numbers
            return;
        }
        else if (p & J_SELECT) {                    // toggle explore mode
            explore ^= 1;
            sfx_blip();
            print_bkg(1, 16, explore ? "EXPLORE: >=next map" : "SELECT:explore mode");
        } else if ((p & J_RIGHT) && explore) {      // jump to the next map
            i = (cur_id + 1) % (sizeof(spawn) / 2);
            sfx_noise(0x62, 0x44);
            enter_map(i, spawn[i][0], spawn[i][1]);
            return;
        }
    }
    sfx_type();
    enter_map(cur_id, px, py);
}

static void wild_encounter(void) {
    const wild_t *w = &cur->wild[rnd() % cur->n_wild];
    update_view();
    still = 1;
    after_battle(battle(w->species, w->lo + rnd() % (w->hi - w->lo + 1), 0));
}

static void phone_call(void) {      // Mom rings as you set out on the Wexford road
    uint8_t i, f;
    flags |= FLAG_CALL;
    for (i = 0; i != 6; i++) {
        sfx_note((i & 1) ? 61 : 65, 0x80, 0xA1);
        for (f = 0; f != 6 + ((i & 1) ? 14 : 0); f++) tick();
    }
    say_t(TXT_CALL);
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
            if (!moving) {
                if (!explore && starter != NO_STARTER && cur->n_wild && (mt_flags[map_ram[py * cur->w + px]] & F_GRASS) && rnd() < 30)
                    wild_encounter();
                else check_sight();
            }
        } else {
            dx = 0; dy = 0;
            if (joy & J_DOWN) { dir = DIR_DOWN; dy = 1; }
            else if (joy & J_UP) { dir = DIR_UP; dy = -1; }
            else if (joy & J_LEFT) { dir = DIR_LEFT; dx = -1; }
            else if (joy & J_RIGHT) { dir = DIR_RIGHT; dx = 1; }

            if (p & J_START) pause_screen();
            else if (p & J_A) {
                tx = px + (dir == DIR_RIGHT) - (dir == DIR_LEFT);
                ty = py + (dir == DIR_DOWN) - (dir == DIR_UP);
                if (tx < cur->w && ty < cur->h) { update_view(); interact(tx, ty); }
            } else if (dx || dy) {
                tx = px + dx; ty = py + dy;
                update_view();
                if (tx >= cur->w || ty >= cur->h) {     // unsigned wrap catches -1
                    e = dy < 0 ? 0 : dy > 0 ? 1 : dx > 0 ? 2 : 3;
                    if (cur->conn[e] != 255) {          // walk on into the neighbouring map
                        tx = cur->conn[e];
                        enter_map(tx, dx ? (dx > 0 ? 0 : maps[tx].w - 1) : px, dy ? (dy > 0 ? 0 : maps[tx].h - 1) : py);
                        if (maps[tx].weather && !(flags & FLAG_CALL) && !explore) phone_call();
                    } else if (cur->edge[e] != NO_TEXT) say_t(cur->edge[e]);
                } else if ((w = warp_at(tx, ty))) {
                    if (cur_id == MAP_HOME && starter == NO_STARTER && !explore) say_t(TXT_MOM0);
                    else { flags |= FLAG_LEFT_HOME; sfx_noise(0x62, 0x44); enter_map(w->map, w->tx, w->ty); }
                } else if (!(flags_at(tx, ty) & F_SOLID)) {
                    opx = px; opy = py; px = tx; py = ty;
                    speed = (joy & J_B) ? 2 : 1;        // hold B to run
                    moving = 16; steps++;
                }
            }
        }
        update_life();
        update_view();
        tick();
    }
}

static uint8_t title(void) {         // returns 1 to continue a saved game
    uint8_t blink = 0, has = save_exists(), c = 0, p;
    print_bkg(4, 4, "EMERALD ISLE");
    print_bkg(4, 6, "------------");
    print_bkg(0, 9, "A New Ross Adventure");
    print_bkg(5, 16, "build v0.20");
    print_bkg(0, 17, "SELECT: explore mode");
    if (has) { print_bkg(6, 12, "CONTINUE"); print_bkg(6, 14, "NEW GAME"); }
    SHOW_BKG; DISPLAY_ON;
    music_play(SONG_HOME);
    while (1) {
        if (has) set_bkg_tile_xy(4, 12 + (c << 1), '>' - 32);
        else print_bkg(4, 13, (blink++ & 32) ? "            " : "PRESS  START");
        rnd();
        vsync();
        p = pressed();
        if (has && (p & (J_UP | J_DOWN))) { set_bkg_tile_xy(4, 12 + (c << 1), 0); c ^= 1; sfx_type(); }
        if (p & J_SELECT) { explore = 1; break; }     // straight into explore mode, skipping the opening
        if (p & (J_START | J_A)) break;
    }
    sfx_blip();
    while (joypad()) vsync();
    prev_joy = 0;
    return explore ? 2 : (has && c == 0);
}

void main(void) {
    uint8_t p;
    DISPLAY_OFF;
    SWITCH_ROM(1);              // make the bank register and its shadow agree from the start
    cur_id = 255;
    font_init();
    font_load(font_spect);
    load_gfx();
    sound_init();
    set_bkg_palette(0, 8, bg_pals);
    set_sprite_palette(0, 8, obj_pals);
    SPRITES_8x16;
    fill_attr(P_UI);
    p = title();
    if (p == 2) { dir = DIR_DOWN; enter_map(MAP_TOWN, spawn[MAP_TOWN][0], spawn[MAP_TOWN][1]); }
    else if (p) load_game();
    else {
        name_entry();
        dir = DIR_UP;
        enter_map(MAP_HOME, 4, 6);
        say_t(TXT_INTRO);
    }
    overworld();
}
