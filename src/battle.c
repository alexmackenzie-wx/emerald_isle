// Wild and trainer battles: turn order, damage, type match-ups, catching, experience.
// This file lives in ROM bank 5. While it runs, bank 1 (the overworld code) is
// switched out, so it may only call routines and read tables that sit in bank 0.
#pragma bank 5
#include "game.h"

static mon_t foe;
static mon_t *me;
static uint8_t me_i;               // which party slot is out
static uint8_t fought;             // bit per party slot: who has faced the current foe
static const char *trainer;        // 0 in a wild battle
static const trainer_t *tr;        // the trainer and which of their team is out
static uint8_t tr_i;
static int8_t stage[2][2];          // [0 = mine, 1 = foe][0 = attack, 1 = defense]
static char buf[40];
static uint8_t bp;
static const palette_color_t ui4[4] = { RGB8(248, 248, 248), RGB8(72, 200, 72), RGB8(200, 200, 200), RGB8(24, 24, 32) };

// ---------------------------------------------------------------- text building
static void b0(void) { bp = 0; buf[0] = 0; }
static void app(const char *s) { while (*s) buf[bp++] = *s++; buf[bp] = 0; }
static void appn(uint16_t n) {
    char t[5]; uint8_t i = 0;
    do { t[i++] = '0' + n % 10; n /= 10; } while (n);
    while (i) buf[bp++] = t[--i];
    buf[bp] = 0;
}
#define NAME(m) (species[(m)->species].name)
static void foe_prefix(void) { app(trainer ? "Foe " : "Wild "); }

// ---------------------------------------------------------------- stats
static uint16_t calc_stat(uint8_t base, uint8_t lvl) { return ((uint16_t)base * 2 * lvl) / 100 + 5; }
uint16_t calc_hp(uint8_t base, uint8_t lvl) BANKED { return ((uint16_t)base * 2 * lvl) / 100 + lvl + 10; }
static uint32_t cube(uint8_t n) { return (uint32_t)n * n * n; }

static void learn(mon_t *m, uint8_t mv) {
    uint8_t i;
    for (i = 0; i != 4; i++) {
        if (m->moves[i] == mv) return;
        if (!m->moves[i]) { m->moves[i] = mv; return; }
    }
    for (i = 0; i != 3; i++) m->moves[i] = m->moves[i + 1];     // full: the oldest move makes way
    m->moves[3] = mv;
}

void teach(mon_t *m, uint8_t mv) BANKED { learn(m, mv); }

void mon_init(mon_t *m, uint8_t sp, uint8_t lvl) BANKED {
    uint8_t i;
    memset(m, 0, sizeof(mon_t));
    m->species = sp; m->level = lvl; m->exp = cube(lvl);
    for (i = 0; i != 4; i++)
        if (species[sp].learn[i][1] && species[sp].learn[i][0] <= lvl) learn(m, species[sp].learn[i][1]);
    m->maxhp = m->hp = calc_hp(species[sp].hp, lvl);
}

void heal_party(void) BANKED {
    uint8_t i;
    for (i = 0; i != party_n; i++) party[i].hp = party[i].maxhp;
}

void level_up(mon_t *m) BANKED {
    const species_t *sp = &species[m->species];
    uint16_t old = m->maxhp;
    uint8_t i;
    if (m->level >= 100) return;
    m->level++;
    if (m->exp < cube(m->level)) m->exp = cube(m->level);
    m->maxhp = calc_hp(sp->hp, m->level);
    m->hp += m->maxhp - old;
    for (i = 0; i != 4; i++)
        if (sp->learn[i][1] && sp->learn[i][0] == m->level) learn(m, sp->learn[i][1]);
}

static uint16_t eff_stat(mon_t *m, uint8_t side, uint8_t which, uint8_t special) {
    const species_t *s = &species[m->species];
    int8_t st = stage[side][which];
    uint16_t v = calc_stat(special ? s->spc : (which ? s->def : s->atk), m->level);
    if (st > 0) v = v * (2 + st) / 2; else if (st < 0) v = v * 2 / (2 - st);
    return v ? v : 1;
}

// ---------------------------------------------------------------- screen
static void draw_bar(uint8_t x, uint8_t y, uint16_t hp, uint16_t max, uint8_t pal) {
    uint8_t i, k;
    uint16_t fill = (uint32_t)hp * 48 / max;
    if (hp && !fill) fill = 1;
    set_bkg_palette_entry(pal, 1, fill > 24 ? RGB8(72, 200, 72) : fill > 10 ? RGB8(240, 200, 40) : RGB8(232, 64, 48));
    for (i = 0; i != 6; i++) {
        k = fill > 8 ? 8 : fill; fill -= k;
        VBK_REG = 1; set_bkg_tile_xy(x + i, y, pal | 0x08);
        VBK_REG = 0; set_bkg_tile_xy(x + i, y, 96 + k);
    }
}

static void draw_hp(uint8_t side) {
    mon_t *m = side ? &foe : me;
    uint8_t x = side ? 1 : 10, y = side ? 1 : 8;
    draw_bar(x + 2, y + 2, m->hp, m->maxhp, side ? 3 : 4);
    if (!side) { b0(); appn(m->hp); app("/"); appn(m->maxhp); app("  "); print_bkg(x + 4, y + 1, buf); }
}

// The XP bar under my PMON's HP: how far it is from its last level to its next.
static void draw_xp(void) {
    uint32_t lo = cube(me->level), hi = cube(me->level + 1);
    uint8_t i, k, fill = 48;
    if (me->level < 100) fill = me->exp > lo ? (uint8_t)((me->exp - lo) * 48 / (hi - lo)) : 0;
    print_bkg(10, 11, "XP");
    for (i = 0; i != 6; i++) {
        k = fill > 8 ? 8 : fill; fill -= k;
        VBK_REG = 1; set_bkg_tile_xy(12 + i, 11, 7 | 0x08);
        VBK_REG = 0; set_bkg_tile_xy(12 + i, 11, 96 + k);
    }
}

static void draw_info(uint8_t side) {
    mon_t *m = side ? &foe : me;
    uint8_t x = side ? 1 : 10, y = side ? 1 : 8;
    fill_bkg_rect(x, y, 10, 2, 0);
    print_bkg(x, y, NAME(m));
    b0(); app("Lv"); appn(m->level); print_bkg(x, y + 1, buf);
    print_bkg(x, y + 2, "HP");
    draw_hp(side);
    if (!side) draw_xp();
}

static uint8_t me_flip;          // 1 when my PMON has no back view and is shown mirrored instead
static const uint8_t *mask[2];   // which tiles of each picture use its second palette

static void wait(uint8_t n) { while (n--) tick(); }

// Draw one side's picture, optionally nudged by a tile or mirrored (for gestures).
// The picture is drawn first and only the strips it has left behind are wiped,
// so nothing flickers.
static void pose(uint8_t side, int8_t dx, int8_t dy, uint8_t flip) {
    uint8_t zx = side ? 11 : 0, zy = side ? 0 : 3;          // each side owns a 9x9 patch of the screen
    uint8_t x = (side ? 12 : 0) + dx, y = (side ? 0 : 4) + dy;
    put_art(x, y, side ? 128 : 192, side ? 1 : 2, side ? 5 : 6, mask[side], side ? flip : flip ^ me_flip);
    if (y > zy) rect(zx, zy, 9, y - zy, 0, 0);
    if (y + 8 < zy + 9) rect(zx, y + 8, 9, zy + 1 - y, 0, 0);
    if (x > zx) rect(zx, zy, x - zx, 9, 0, 0);
    if (x + 8 < zx + 9) rect(x + 8, zy, zx + 1 - x, 9, 0, 0);
}

// Every species greets the battle in its own way.
static void gesture(uint8_t side) {
    mon_t *m = side ? &foe : me;
    int8_t fwd = side ? -1 : 1, up = side ? 1 : -1;
    uint8_t g = species[m->species].gesture, i;
    for (i = 0; i != 2; i++) {
        if (g == 0) pose(side, 0, up, 0);               // hop
        else if (g == 1) pose(side, fwd, 0, 0);         // lunge at the opponent
        else if (g == 2) pose(side, 0, 0, 1);           // twirl
        else { pose(side, fwd, 0, 0); wait(2); pose(side, 0, 0, 0); wait(2); pose(side, fwd, 0, 0); }   // shake
        if (g == 0) sfx_noise(0x41, 0x35);
        wait(g == 3 ? 2 : 7);
        pose(side, 0, 0, 0);
        wait(6);
    }
}

// A PBall spins across the screen to (tx, ty), springs open, and throws out sparks.
static void ball_at(uint8_t f, int16_t x, int16_t y) {
    set_sprite_tile(12, f << 2); set_sprite_tile(13, (f << 2) + 2);
    set_sprite_prop(12, 5); set_sprite_prop(13, 5);
    move_sprite(12, x, y + 8); move_sprite(13, x + 8, y + 8);
}

static void toss(int16_t x0, int16_t y0, int16_t tx, int16_t ty) {
    uint8_t t, i;
    sfx_note(44, 0x80, 0x53);
    for (t = 0; t != 29; t++) {
        ball_at(F_BALL + ((t >> 2) & 1), x0 + (tx - x0) * t / 28, y0 + (ty - y0) * t / 28 - (t * (28 - t)) / 6);
        tick();
    }
    sfx_noise(0xC2, 0x52);
    ball_at(F_BALL + 2, tx, ty);
    wait(8);
    for (i = 12; i != 16; i++) { set_sprite_tile(i, SPARK_TILE); set_sprite_prop(i, 5); }
    for (t = 1; t != 13; t++) {                         // four sparks fly out from where it opened
        for (i = 0; i != 4; i++)
            move_sprite(12 + i, tx + 4 + ((i & 1) ? t << 1 : -(t << 1)), ty + 12 + ((i & 2) ? t << 1 : -(t << 1)));
        tick();
    }
    for (i = 12; i != 16; i++) move_sprite(i, 0, 0);
}

// Bring a PMON onto the field: thrown from a PBall (or stepping out of the grass,
// if it is wild), a flash, its cry, then its gesture.
static void send_out(uint8_t side, uint8_t ball) {
    mon_t *m = side ? &foe : me;
    uint8_t pal = side ? 1 : 2, back = !side && species[m->species].back != NO_BACK, i;
    if (!side) me_flip = !back;
    mask[side] = back ? back_mask[species[m->species].back] : art_mask[m->species];
    if (ball) { if (side) toss(168, 10, 124, 28); else toss(-8, 96, 28, 64); }
    load_art(m->species, side ? 128 : 192, back);
    set_bkg_palette(pal, 1, white4);
    pose(side, 0, 0, 0);
    set_bkg_palette(pal + 4, 1, white4);
    for (i = 0; i != 3; i++) {                          // burst of light, fading in
        set_bkg_palette(pal, 1, white4); set_bkg_palette(pal + 4, 1, white4); wait(3);
        set_bkg_palette(pal, 1, art_pals[m->species]); set_bkg_palette(pal + 4, 1, art_pals2[m->species]); wait(3);
    }
    cry(m->species, 0);
    gesture(side);
    draw_info(1);
    if (!side) draw_info(0);
}

static void hide_mon(uint8_t side) {
    if (side) rect(12, 0, 8, 8, 0, 0); else rect(0, 4, 8, 8, 0, 0);
}

static void hurt(uint8_t side, uint16_t dmg) {
    mon_t *m = side ? &foe : me;
    uint8_t i, pal = side ? 1 : 2;
    sfx_noise(0x81, 0x44);
    for (i = 0; i != 6; i++) {
        set_bkg_palette(pal, 1, (i & 1) ? art_pals[m->species] : white4);
        set_bkg_palette(pal + 4, 1, (i & 1) ? art_pals2[m->species] : white4);
        tick(); tick(); tick();
    }
    set_bkg_palette(pal, 1, art_pals[m->species]); set_bkg_palette(pal + 4, 1, art_pals2[m->species]);
    while (dmg && m->hp) { m->hp--; dmg--; draw_hp(side); tick(); }
}

static void jingle(void) {
    uint8_t i, f;
    static const uint8_t notes[4] = { 49, 53, 56, 61 };
    for (i = 0; i != 4; i++) { sfx_note(notes[i], 0x80, 0xA2); for (f = 0; f != 5; f++) tick(); }
}

// ---------------------------------------------------------------- menus
static const uint8_t slot_x[4] = { 1, 10, 1, 10 }, slot_y[4] = { 2, 2, 4, 4 };

static uint8_t pick(uint8_t n, uint8_t can_cancel, uint8_t c) {
    uint8_t p;
    if (c >= n) c = 0;
    while (1) {
        set_win_tile_xy(slot_x[c], slot_y[c], '>' - 32);
        do { tick(); p = pressed(); } while (!p);
        set_win_tile_xy(slot_x[c], slot_y[c], 0);
        if (p & J_A) { sfx_blip(); return c; }
        if ((p & J_B) && can_cancel) { sfx_type(); return 255; }
        if ((p & (J_LEFT | J_RIGHT)) && (c ^ 1) < n) { c ^= 1; sfx_type(); }
        if ((p & (J_UP | J_DOWN)) && (c ^ 2) < n) { c ^= 2; sfx_type(); }
    }
}

static uint8_t main_menu(void) {
    win_clear();
    win_print(2, 2, "FIGHT");
    win_print(11, 2, "ITEMS");
    win_print(2, 4, "PMON");
    win_print(11, 4, "RUN");
    return pick(4, 0, 0);
}

static uint8_t item_menu(void) {        // 0 PBall, 1 Potion, 255 back
    win_clear();
    b0(); app("PBALL x"); appn(torcs); win_print(2, 2, buf);
    b0(); app("POTION x"); appn(potions); win_print(2, 4, buf);
    win_print(11, 2, "BACK");
    switch (pick(3, 1, 0)) {               // slots: 0 top left, 1 top right, 2 bottom left
        case 0: return 0;
        case 2: return 1;
    }
    return 255;
}

static uint8_t last_move;

static uint8_t move_menu(void) {     // one move to a line, so long names fit
    uint8_t i, n = 0, c = last_move, p;
    win_clear();
    for (i = 0; i != 4; i++)
        if (me->moves[i]) { win_print(3, 1 + i, moves[me->moves[i]].name); n++; }
    if (c >= n) c = 0;
    while (1) {
        set_win_tile_xy(2, 1 + c, '>' - 32);
        do { tick(); p = pressed(); } while (!p);
        set_win_tile_xy(2, 1 + c, 0);
        if (p & J_A) { sfx_blip(); last_move = c; return me->moves[c]; }    // next time the arrow starts here
        if (p & J_B) { sfx_type(); return 255; }
        if ((p & J_UP) && c) { c--; sfx_type(); }
        if ((p & J_DOWN) && c + 1 < n) { c++; sfx_type(); }
    }
}

// ---------------------------------------------------------------- turns
// Every move has its own look. Effects use sprites 26-31 as three 16x16 pieces.
static void fx_set(uint8_t f, uint8_t pal, uint8_t flipy) {
    uint8_t i, tile = (f >= 32) ? (f - 32) << 2 : f << 2, prop = pal | (f >= 32 ? 0x08 : 0) | (flipy ? S_FLIPY : 0);
    for (i = 26; i != 32; i++) { set_sprite_tile(i, tile + ((i & 1) ? 2 : 0)); set_sprite_prop(i, prop); }
}
static void fx_at(uint8_t i, int16_t x, int16_t y) {
    move_sprite(26 + (i << 1), x + 8, y + 16); move_sprite(27 + (i << 1), x + 16, y + 16);
}
static void fx_off(void) {
    uint8_t i;
    for (i = 26; i != 32; i++) move_sprite(i, 0, 0);
}
static void hit_star(uint8_t target) {              // a flash of impact on the target
    fx_set(F_STAR, 5, 0);
    fx_at(0, target ? 120 : 24, target ? 24 : 56);
    sfx_noise(0xA1, 0x53);
    wait(6);
    fx_off();
}

static void move_fx(uint8_t target, uint8_t mv, mon_t *a) {
    uint8_t att = !target, i, t, type = moves[mv].type;
    int8_t fwd = att ? -1 : 1, up = att ? 1 : -1;
    int16_t x, y, l = target ? 100 : 4, b = target ? 48 : 80;      // the target's left edge and feet
    int16_t cx = target ? 120 : 24, cy = target ? 24 : 56;          // ...and its middle
    int16_t ax = att ? 120 : 24, ay = att ? 24 : 56;                // the attacker's middle
    switch (mv) {
    case MV_TACKLE:                                 // a run-up and a body slam
        wait(4);                                    // (a picture can only shift towards the middle of the screen)
        pose(att, fwd, 0, 0); wait(3);
        pose(att, fwd, up, 0); hit_star(target);
        pose(att, 0, 0, 0);
        return;
    case MV_JAB:
    case MV_PECK:                                   // two quick jabs
        for (i = 0; i != 2; i++) { pose(att, fwd, 0, 0); hit_star(target); pose(att, 0, 0, 0); wait(3); }
        return;
    case MV_SCRATCH:                                // claws rake down across the target, twice
        fx_set(F_SLASH, 5, 0);
        for (i = 0; i != 2; i++) {
            sfx_noise(0x71, 0x23);
            for (t = 0; t != 8; t++) { fx_at(0, cx + 12 - t * 4 + i * 8, cy - 20 + t * 4); fx_at(1, cx + 24 - t * 4 + i * 8, cy - 14 + t * 4); tick(); }
        }
        break;
    case MV_NIP:                                    // jaws close on it
        for (t = 0; t != 12; t++) {
            fx_set(F_FANG, 5, 0); fx_at(0, cx - 8, cy - 34 + t * 2); fx_at(1, cx + 8, cy - 34 + t * 2);
            set_sprite_prop(30, 5 | 0x08 | S_FLIPY); set_sprite_prop(31, 5 | 0x08 | S_FLIPY);
            fx_at(2, cx, cy + 22 - t * 2);
            tick();
        }
        sfx_noise(0xC1, 0x41); wait(8);
        break;
    case MV_SODKICK:                                // a hop, and clods of earth fly over
        pose(att, 0, up, 0);
        fx_set(F_CLOD, 5, 0);
        for (t = 0; t != 26; t++) {
            if (t == 4) pose(att, 0, 0, 0);
            for (i = 0; i != 3; i++) {
                x = (t > i * 3) ? t - i * 3 : 0; if (x > 20) x = 20;
                fx_at(i, ax + (cx - ax) * x / 20, ay + (cy - ay) * x / 20 - (x * (20 - x)) / 5);
            }
            if ((t & 7) == 0) sfx_noise(0x61, 0x55);
            tick();
        }
        break;
    case MV_SQUALL:                                 // whirling gusts sweep across it
        fx_set(F_WHIRL_A, 7, 0);
        for (t = 0; t != 30; t++) {
            if ((t & 3) == 0) { sfx_noise(0x42, 0x30 + (t & 12)); fx_set((t & 4) ? F_WHIRL_B : F_WHIRL_A, 7, 0); }
            for (i = 0; i != 3; i++) fx_at(i, l + t * 3 - 30 + i * 14, b - 44 + i * 14 + ((t + i * 5) & 7));
            tick();
        }
        break;
    case MV_SUPERSOAK:                              // a jet of water, shot straight across
        fx_set(F_WAVE, 3, 0);
        for (t = 0; t != 30; t++) {
            if ((t & 3) == 0) sfx_noise(0x62, 0x34);
            for (i = 0; i != 3; i++) {
                x = (t * 2 + i * 7) % 21;
                fx_at(i, ax + (cx - ax) * x / 20, ay + (cy - ay) * x / 20 - 6);
            }
            tick();
        }
        break;
    case MV_BELLOW:                                 // it shakes with the roar, and the sound rolls out
        fx_set(F_WHIRL_A, 7, 0);
        for (t = 0; t != 24; t++) {
            if ((t & 3) == 0) { pose(att, (t & 4) ? fwd : 0, 0, 0); sfx_note(6 + (t & 4), 0x00, 0xC2); }
            fx_at(0, ax + (cx - ax) * t / 24, ay + (cy - ay) * t / 24 - 8);
            tick();
        }
        pose(att, 0, 0, 0);
        break;
    case MV_GLARE:                                  // its eyes flash, and the target is caught in the look
        for (i = 0; i != 3; i++) {
            set_bkg_palette(att ? 1 : 2, 1, white4); set_bkg_palette(att ? 5 : 6, 1, white4); sfx_note(68, 0x80, 0x61); wait(3);
            set_bkg_palette(att ? 1 : 2, 1, art_pals[a->species]); set_bkg_palette(att ? 5 : 6, 1, art_pals2[a->species]); wait(3);
        }
        hit_star(target);
        return;
    default:                                        // by element: waves, flames, leaves
        if (type == T_WATER) fx_set(F_WAVE, 3, 0);
        else if (type == T_FIRE) fx_set(F_FLAME, 5, 0);
        else if (type == T_GRASS) fx_set(F_LEAF, 2, 0);
        else return;
        for (t = 0; t != 28; t++) {
            if ((t & 3) == 0) sfx_noise(type == T_WATER ? 0x73 : 0x51, type == T_WATER ? 0x44 + (t >> 2) : type == T_FIRE ? 0x62 : 0x21);
            for (i = 0; i != 3; i++) {
                if (type == T_WATER) { x = l + i * 22 + t * 2 - 28; y = b - 10 - ((t + i * 3) & 7); }
                else if (type == T_FIRE) { x = l + 4 + i * 18 + ((t >> 1) & 1) * 2; y = b - t; }
                else { x = l + i * 20 + t * 2 - 12; y = b - 52 + t * 2 + i * 5; }
                fx_at(i, x, y);
            }
            tick();
        }
    }
    fx_off();
}

// A trainer's team shown as a row of PBalls while they stand on the field.
static void team_balls(uint8_t side, uint8_t n) {
    uint8_t i, first = side ? 20 : 32;
    for (i = 0; i != 6; i++) {
        set_sprite_tile(first + i, (F_DOT - 32) << 2); set_sprite_prop(first + i, 5 | 0x08);
        if (i < n) move_sprite(first + i, (side ? 20 : 100) + i * 9, side ? 24 : 92);
        else move_sprite(first + i, 0, 0);
    }
}

static uint8_t use_move(uint8_t side, uint8_t mv) {     // returns 1 if the target fainted
    mon_t *a = side ? &foe : me, *d = side ? me : &foe;
    const move_t *m = &moves[mv];
    uint32_t dmg;
    uint8_t eff, sp;
    b0(); if (side) foe_prefix(); app(NAME(a)); app(" used\n"); app(m->name); app("!"); say(buf);
    if (rnd() % 100 >= m->acc) { say("But it missed!"); return 0; }
    move_fx(!side, mv, a);
    if (m->effect) {
        if (stage[!side][m->effect - 1] > -6) {
            stage[!side][m->effect - 1]--;
            sfx_note(30, 0x40, 0x72);
            b0(); app(NAME(d)); app("'s\n"); app(m->effect == 1 ? "ATTACK fell!" : "DEFENSE fell!"); say(buf);
        } else say("Nothing happened!");
        return 0;
    }
    eff = type_chart[m->type][species[d->species].type];
    if (!eff) { say("It had no effect!"); return 0; }
    sp = type_special[m->type];
    dmg = (uint32_t)(2 * a->level / 5 + 2) * m->power * eff_stat(a, side, 0, sp) / eff_stat(d, !side, 1, sp) / 50 + 2;
    if (m->type == species[a->species].type) dmg += dmg >> 1;      // same-type bonus
    dmg = dmg * eff / 10;
    dmg = dmg * (217 + rnd() % 39) / 255;
    if (!dmg) dmg = 1;
    hurt(!side, dmg);
    if (eff > 10) say("It's super\neffective!");
    else if (eff < 10) say("It's not very\neffective...");
    return d->hp == 0;
}

// Choose a party member from a 2x3 grid in the dialog box. Fainted PMONs are
// marked and can't be picked, nor can the one already out.
static uint8_t party_menu(uint8_t can_cancel) {
    uint8_t i, c = 0, p, x, y;
    win_clear();
    for (i = 0; i != party_n; i++) {
        b0(); app(NAME(&party[i])); if (!party[i].hp) app("-");
        win_print(2 + (i & 1) * 9, 1 + (i >> 1), buf);
    }
    while (1) {
        x = 1 + (c & 1) * 9; y = 1 + (c >> 1);
        set_win_tile_xy(x, y, '>' - 32);
        do { tick(); p = pressed(); } while (!p);
        set_win_tile_xy(x, y, 0);
        if (p & J_A) {
            if (party[c].hp && (c != me_i || !me->hp)) { sfx_blip(); return c; }
            sfx_note(30, 0x40, 0x52);
        }
        if ((p & J_B) && can_cancel) { sfx_type(); return 255; }
        if ((p & (J_LEFT | J_RIGHT)) && (c ^ 1) < party_n) { c ^= 1; sfx_type(); }
        if ((p & J_UP) && c >= 2) { c -= 2; sfx_type(); }
        if ((p & J_DOWN) && c + 2 < party_n) { c += 2; sfx_type(); }
    }
}

static void bring_out(uint8_t i) {
    me_i = i; me = &party[i];
    last_move = 0;
    fought |= 1 << i;
    stage[0][0] = stage[0][1] = 0;
    b0(); app("Go, "); app(NAME(me)); app("!"); say(buf);
    send_out(0, 1);
}

static const char * const stat_names[4] = { "ATK +", "DEF +", "SPD +", "SPC +" };

// Give one party member its share of experience, with any level-ups.
static void award(uint8_t idx, uint16_t gain) {
    mon_t *m = &party[idx];
    const species_t *sp = &species[m->species];
    uint8_t i, base[4];
    uint16_t old;
    base[0] = sp->atk; base[1] = sp->def; base[2] = sp->spd; base[3] = sp->spc;
    b0(); app(NAME(m)); app(" gained\n"); appn(gain); app(" EXP!"); say(buf);
    if (m == me) {
        for (i = 0; i != 12; i++) {                 // the XP bar fills as the points come in
            m->exp += gain / 12 + (i == 0 ? gain % 12 : 0);
            if (m->exp < cube(m->level + 1)) draw_xp();
            sfx_note(49 + i, 0x80, 0x31);
            tick(); tick(); tick();
        }
    } else m->exp += gain;
    while (m->level < 100 && m->exp >= cube(m->level + 1)) {
        m->level++;
        old = m->maxhp;
        m->maxhp = calc_hp(sp->hp, m->level);
        m->hp += m->maxhp - old;
        if (m == me) draw_info(0);
        jingle();
        b0(); app(NAME(m)); app(" grew to\nlevel "); appn(m->level); app("!"); say(buf);
        win_clear();                                // what the new level brought
        b0(); app("HP  +"); appn(m->maxhp - old); win_print(2, 1, buf);
        for (i = 0; i != 4; i++) {
            b0(); app(stat_names[i]); appn(calc_stat(base[i], m->level) - calc_stat(base[i], m->level - 1));
            win_print((i & 1) ? 2 : 11, 1 + ((i + 1) >> 1), buf);
        }
        win_wait();
        for (i = 0; i != 4; i++)
            if (sp->learn[i][1] && sp->learn[i][0] == m->level) {
                learn(m, sp->learn[i][1]);
                b0(); app(NAME(m)); app(" learned\n"); app(moves[sp->learn[i][1]].name); app("!"); say(buf);
            }
    }
}

// The foe is down: everyone who faced it and is still standing shares the experience.
static void won(void) {
    uint16_t gain = (uint16_t)species[foe.species].yield * foe.level / 5;
    uint8_t i, n = 0;
    hide_mon(1);
    if (trainer) gain += gain >> 1;                 // trained PMONs are worth more
    b0(); foe_prefix(); app(NAME(&foe)); app("\nfainted!"); say(buf);
    for (i = 0; i != party_n; i++) if (((fought >> i) & 1) && party[i].hp) n++;
    gain /= n;
    if (!gain) gain = 1;
    for (i = 0; i != party_n; i++) if (((fought >> i) & 1) && party[i].hp) award(i, gain);
}

static uint8_t next_mon(void) {         // 0 if nobody is left standing
    uint8_t i;
    hide_mon(0);
    b0(); app(NAME(me)); app(" fainted!"); say(buf);
    for (i = 0; i != party_n; i++) if (party[i].hp) break;
    if (i == party_n) return 0;
    bring_out(party_menu(0));           // you choose who goes in next
    return 1;
}

static uint8_t next_foe(void) {         // a trainer's next PMON, if they have one
    if (!tr || ++tr_i >= tr->n) return 0;
    mon_init(&foe, tr->mons[tr_i][0], tr->mons[tr_i][1]);
    stage[1][0] = stage[1][1] = 0;
    fought = 1 << me_i;
    b0(); app(trainer); app(" sent out\n"); app(NAME(&foe)); app("!"); say(buf);
    send_out(1, 1);
    return 1;
}

static uint8_t throw_torc(void) {       // 1 if caught
    uint16_t f = (uint32_t)species[foe.species].rate * (3 * foe.maxhp - 2 * foe.hp) / (3 * foe.maxhp);
    uint8_t ok = f >= 255 || rnd() <= f, shakes = ok ? 3 : rnd() % 3, i, t;
    torcs--;
    b0(); app(name); app(" threw\na PBALL!"); say(buf);
    toss(24, 80, 124, 28);
    hide_mon(1);
    for (i = 0; i != shakes; i++) {
        sfx_note(37, 0x80, 0x52);
        for (t = 0; t != 36; t++) tick();
    }
    if (!ok) { pose(1, 0, 0, 0); draw_info(1); say("Argh! It broke\nfree!"); return 0; }
    jingle();
    b0(); app("Gotcha! "); app(NAME(&foe)); app("\nwas caught!"); say(buf);
    party[party_n++] = foe;
    return 1;
}

// Each trainer stands on the field (7x7 tiles) until their PMON is thrown out, then steps off.
static uint8_t pic_of[2];        // which picture each side is showing

static void pic_draw(uint8_t side, int8_t dx) {
    uint8_t x, y, t = side ? 128 : 192, x0 = (side ? 12 : 1) + dx, y0 = side ? 1 : 5;
    for (y = 0; y != 7; y++)
        for (x = 0; x != 7; x++, t++) {
            VBK_REG = 1; set_bkg_tile_xy((x0 + x) & 31, y0 + y, ((side ? 1 : 2) + ((pic_masks[pic_of[side]][y] >> x) & 1 ? 4 : 0)) | 0x08);
            VBK_REG = 0; set_bkg_tile_xy((x0 + x) & 31, y0 + y, t);
        }
}

static void pic_load(uint8_t side, uint8_t pic) {
    bank_copy(PIC_BANK, trainer_pics[pic], art_buf, 784);
    VBK_REG = 1; set_bkg_data(side ? 128 : 192, 49, art_buf); VBK_REG = 0;
    set_bkg_palette(side ? 1 : 2, 1, pic_pals[pic]);
    set_bkg_palette(side ? 5 : 6, 1, pic_pals2[pic]);       // skin tones, for the tiles that hold a face
    pic_of[side] = pic;
    pic_draw(side, 0);
}

static void pic_leave(uint8_t side) {
    int8_t d;
    for (d = 1; d != 9; d++) {
        pic_draw(side, side ? d : -d);
        if (side) rect(11 + d, 1, 1, 7, 0, 0);          // wipe the column just left behind
        else rect(8 - d, 5, 1, 7, 0, 0);
        wait(2);
    }
}

static void stage_on(void) {            // the bare battle screen
    DISPLAY_OFF;
    hide_sprites_from(0);
    move_bkg(0, 0);
    rect(0, 0, 32, 32, 0, 0);
    set_bkg_palette(0, 1, ui4); set_bkg_palette(3, 1, ui4); set_bkg_palette(4, 1, ui4);
    set_bkg_palette_entry(0, 1, RGB8(176, 176, 168));
    set_bkg_palette_entry(7, 1, RGB8(64, 144, 232));        // the XP bar borrows the dialog palette's spare colours
    set_bkg_palette_entry(7, 2, RGB8(200, 200, 200));
    SHOW_BKG; DISPLAY_ON;
}

// The Professor's gift: the PMON bursts out of its PBall, cries and shows off.
void present(uint8_t sp) BANKED {
    mon_init(&foe, sp, 5);
    me = &party[0];
    trainer = 0;
    still = 1;
    stage_on();
    wait(20);
    send_out(1, 1);
    gesture(1);
    win_keep = 0;
    say_t(TXT_PROF2);
}

uint8_t battle(uint8_t sp, uint8_t lvl, const trainer_t *t) BANKED {
    uint8_t i, choice, mv = 0, fm, n, first, lost = 0;
    tr = t; tr_i = 0;
    trainer = t ? t->name : 0;
    if (t) mon_init(&foe, t->mons[0][0], t->mons[0][1]); else mon_init(&foe, sp, lvl);
    for (i = 0; i != party_n; i++) if (party[i].hp) break;
    me_i = i; me = &party[i];
    fought = 1 << i;

    last_move = 0;
    music_play(t ? t->song : SONG_BATTLE);
    battle_transition();
    stage_on();
    stage[0][0] = stage[0][1] = stage[1][0] = stage[1][1] = 0;
    win_keep = 1;
    if (trainer) {
        pic_load(1, t->pic);
        team_balls(1, t->n);
        b0(); app(trainer); app(" wants\nto battle!"); say(buf);
        b0(); app(trainer); app(" sent out\n"); app(NAME(&foe)); app("!"); say(buf);
        team_balls(1, 0);
        pic_leave(1);
        send_out(1, 1);
    } else {
        send_out(1, 0);
        b0(); app("Wild "); app(NAME(&foe)); app("\nappeared!"); say(buf);
    }
    pic_load(0, PIC_ME);
    if (trainer) team_balls(0, party_n);
    b0(); app("Go, "); app(NAME(me)); app("!"); say(buf);
    team_balls(0, 0);
    pic_leave(0);
    send_out(0, 1);

    while (1) {
        choice = main_menu();
        if (choice == 0) {
            mv = move_menu();
            if (mv == 255) continue;
        } else if (choice == 1) {
            i = item_menu();
            if (i == 255) continue;
            if (i == 1) {                           // a potion: 20 HP, and it costs you the turn
                if (!potions) { say("No POTIONs left!"); continue; }
                if (me->hp == me->maxhp) { b0(); app(NAME(me)); app(" is\nat full health!"); say(buf); continue; }
                potions--;
                me->hp += 20;
                if (me->hp > me->maxhp) me->hp = me->maxhp;
                jingle();
                draw_hp(0);
                b0(); app("Used a POTION!\n"); app(NAME(me)); app(" perked up!"); say(buf);
                goto foe_turn;
            }
            if (trainer) { say("You can't catch\nanother's PMON!"); continue; }
            if (!torcs) { say("No PBALLs left!"); continue; }
            if (party_n == MAX_PARTY) { say("Your party\nis full!"); continue; }
            if (throw_torc()) break;
        } else if (choice == 2) {                  // swap PMONs: it costs you the turn
            i = party_menu(1);
            if (i == 255) continue;
            b0(); app("Come back,\n"); app(NAME(me)); app("!"); say(buf);
            hide_mon(0);
            bring_out(i);
        } else {
            if (trainer) { say("No running from\na trainer!"); continue; }
            sfx_noise(0x52, 0x33);
            say("Got away safely!");
            break;
        }
foe_turn:
        for (n = 0; n != 4 && foe.moves[n]; n++);
        fm = foe.moves[rnd() % n];
        first = choice == 0 && calc_stat(species[me->species].spd, me->level) >= calc_stat(species[foe.species].spd, foe.level);
        if (first && use_move(0, mv)) { won(); if (next_foe()) continue; goto done; }
        if (use_move(1, fm)) {
            if (!next_mon()) { lost = 1; break; }
            continue;
        }
        if (choice == 0 && !first && use_move(0, mv)) { won(); if (next_foe()) continue; goto done; }
    }
    goto out;
done:
    if (trainer) { b0(); app(trainer); app(" was\ndefeated!"); say(buf); }
out:
    win_keep = 0;
    HIDE_WIN;
    return lost;
}
