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

static uint8_t pick(uint8_t n, uint8_t can_cancel) {
    uint8_t c = 0, p;
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
    b0(); app("PBALLx"); appn(torcs); win_print(11, 2, buf);
    win_print(2, 4, "PMON");
    win_print(11, 4, "RUN");
    return pick(4, 0);
}

static uint8_t move_menu(void) {
    uint8_t i, n = 0;
    win_clear();
    for (i = 0; i != 4; i++)
        if (me->moves[i]) { win_print(slot_x[i] + 1, slot_y[i], moves[me->moves[i]].name); n++; }
    i = pick(n, 1);
    return i == 255 ? 255 : me->moves[i];
}

// ---------------------------------------------------------------- turns
static uint8_t use_move(uint8_t side, uint8_t mv) {     // returns 1 if the target fainted
    mon_t *a = side ? &foe : me, *d = side ? me : &foe;
    const move_t *m = &moves[mv];
    uint32_t dmg;
    uint8_t eff, sp;
    b0(); if (side) foe_prefix(); app(NAME(a)); app(" used\n"); app(m->name); app("!"); say(buf);
    if (rnd() % 100 >= m->acc) { say("But it missed!"); return 0; }
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

uint8_t battle(uint8_t sp, uint8_t lvl, const trainer_t *t) BANKED {
    uint8_t i, choice, mv = 0, fm, n, first, lost = 0;
    tr = t; tr_i = 0;
    trainer = t ? t->name : 0;
    if (t) mon_init(&foe, t->mons[0][0], t->mons[0][1]); else mon_init(&foe, sp, lvl);
    for (i = 0; i != party_n; i++) if (party[i].hp) break;
    me_i = i; me = &party[i];
    fought = 1 << i;

    music_play(SONG_BATTLE);
    battle_transition();
    DISPLAY_OFF;
    hide_sprites_from(0);
    move_bkg(0, 0);
    rect(0, 0, 32, 32, 0, 0);
    set_bkg_palette(0, 1, ui4); set_bkg_palette(3, 1, ui4); set_bkg_palette(4, 1, ui4);
    set_bkg_palette_entry(0, 1, RGB8(176, 176, 168));
    set_bkg_palette_entry(7, 1, RGB8(64, 144, 232));        // the XP bar borrows the dialog palette's spare colours
    set_bkg_palette_entry(7, 2, RGB8(200, 200, 200));
    stage[0][0] = stage[0][1] = stage[1][0] = stage[1][1] = 0;
    SHOW_BKG; DISPLAY_ON;
    win_keep = 1;
    if (trainer) {
        b0(); app(trainer); app(" wants\nto battle!"); say(buf);
        b0(); app(trainer); app(" sent out\n"); app(NAME(&foe)); app("!"); say(buf);
        send_out(1, 1);
    } else {
        send_out(1, 0);
        b0(); app("Wild "); app(NAME(&foe)); app("\nappeared!"); say(buf);
    }
    b0(); app("Go, "); app(NAME(me)); app("!"); say(buf);
    send_out(0, 1);

    while (1) {
        choice = main_menu();
        if (choice == 0) {
            mv = move_menu();
            if (mv == 255) continue;
        } else if (choice == 1) {
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
