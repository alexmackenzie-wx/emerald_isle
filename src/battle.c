// Wild battles: turn order, damage, type match-ups, catching, experience.
#include "game.h"

static mon_t foe;
static mon_t *me;
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

// ---------------------------------------------------------------- stats
static uint16_t calc_stat(uint8_t base, uint8_t lvl) { return ((uint16_t)base * 2 * lvl) / 100 + 5; }
uint16_t calc_hp(uint8_t base, uint8_t lvl) { return ((uint16_t)base * 2 * lvl) / 100 + lvl + 10; }
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

void mon_init(mon_t *m, uint8_t sp, uint8_t lvl) {
    uint8_t i;
    memset(m, 0, sizeof(mon_t));
    m->species = sp; m->level = lvl; m->exp = cube(lvl);
    for (i = 0; i != 4; i++)
        if (species[sp].learn[i][1] && species[sp].learn[i][0] <= lvl) learn(m, species[sp].learn[i][1]);
    m->maxhp = m->hp = calc_hp(species[sp].hp, lvl);
}

void heal_party(void) {
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
    if (!side) { b0(); appn(m->hp); app("/"); appn(m->maxhp); app("   "); print_bkg(x + 2, y + 3, buf); }
}

static void draw_info(uint8_t side) {
    mon_t *m = side ? &foe : me;
    uint8_t x = side ? 1 : 10, y = side ? 1 : 8;
    fill_bkg_rect(x, y, 10, 2, 0);
    print_bkg(x, y, NAME(m));
    b0(); app("Lv"); appn(m->level); print_bkg(x, y + 1, buf);
    print_bkg(x, y + 2, "HP");
    draw_hp(side);
}

static void show_mon(uint8_t side) {
    mon_t *m = side ? &foe : me;
    set_bkg_palette(side ? 1 : 2, 1, art_pals[m->species]);
    load_art(m->species, side ? 128 : 192);
    if (side) put_art(12, 0, 128, 1, 0); else put_art(0, 4, 192, 2, 1);
    draw_info(side);
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
        tick(); tick(); tick();
    }
    set_bkg_palette(pal, 1, art_pals[m->species]);
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
    b0(); app("TORC x"); appn(torcs); win_print(11, 2, buf);
    win_print(2, 4, "RUN");
    return pick(3, 0);
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
    b0(); if (side) app("Wild "); app(NAME(a)); app(" used\n"); app(m->name); app("!"); say(buf);
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

static void won(void) {
    uint16_t gain = (uint16_t)species[foe.species].yield * foe.level / 7, old;
    uint8_t i;
    hide_mon(1);
    b0(); app("Wild "); app(NAME(&foe)); app("\nfainted!"); say(buf);
    b0(); app(NAME(me)); app(" gained\n"); appn(gain); app(" EXP!"); say(buf);
    me->exp += gain;
    while (me->level < 100 && me->exp >= cube(me->level + 1)) {
        me->level++;
        old = me->maxhp;
        me->maxhp = calc_hp(species[me->species].hp, me->level);
        me->hp += me->maxhp - old;
        draw_info(0);
        jingle();
        b0(); app(NAME(me)); app(" grew to\nlevel "); appn(me->level); app("!"); say(buf);
        for (i = 0; i != 4; i++)
            if (species[me->species].learn[i][1] && species[me->species].learn[i][0] == me->level) {
                learn(me, species[me->species].learn[i][1]);
                b0(); app(NAME(me)); app(" learned\n"); app(moves[species[me->species].learn[i][1]].name); app("!"); say(buf);
            }
    }
}

static uint8_t next_mon(void) {         // 0 if nobody is left standing
    uint8_t i;
    hide_mon(0);
    b0(); app(NAME(me)); app(" fainted!"); say(buf);
    for (i = 0; i != party_n; i++)
        if (party[i].hp) {
            me = &party[i];
            stage[0][0] = stage[0][1] = 0;
            show_mon(0);
            b0(); app("Go, "); app(NAME(me)); app("!"); say(buf);
            return 1;
        }
    return 0;
}

static uint8_t throw_torc(void) {       // 1 if caught
    uint16_t f = (uint32_t)species[foe.species].rate * (3 * foe.maxhp - 2 * foe.hp) / (3 * foe.maxhp);
    uint8_t ok = f >= 255 || rnd() <= f, shakes = ok ? 3 : rnd() % 3, i, t;
    torcs--;
    b0(); app(name); app(" threw\na TORC!"); say(buf);
    hide_mon(1);
    for (i = 0; i != shakes; i++) {
        sfx_note(37, 0x80, 0x52);
        for (t = 0; t != 36; t++) tick();
    }
    if (!ok) { put_art(12, 0, 128, 1, 0); say("Argh! It broke\nfree!"); return 0; }
    jingle();
    b0(); app("Gotcha! "); app(NAME(&foe)); app("\nwas caught!"); say(buf);
    party[party_n++] = foe;
    return 1;
}

uint8_t battle(uint8_t sp, uint8_t lvl) {
    uint8_t i, choice, mv = 0, fm, n, first, lost = 0;
    mon_init(&foe, sp, lvl);
    for (i = 0; i != party_n; i++) if (party[i].hp) break;
    me = &party[i];

    music_play(SONG_BATTLE);
    sfx_noise(0xF2, 0x51);
    for (i = 0; i != 8; i++) {                      // the screen blinks before a battle
        if (i & 1) { SHOW_BKG; } else { HIDE_BKG; }
        for (n = 0; n != 5; n++) tick();
    }
    DISPLAY_OFF;
    hide_sprites_from(0);
    move_bkg(0, 0);
    rect(0, 0, 32, 32, 0, 0);
    set_bkg_palette(0, 1, ui4); set_bkg_palette(3, 1, ui4); set_bkg_palette(4, 1, ui4);
    set_bkg_palette_entry(0, 1, RGB8(176, 176, 168));
    stage[0][0] = stage[0][1] = stage[1][0] = stage[1][1] = 0;
    show_mon(1); show_mon(0);
    SHOW_BKG; DISPLAY_ON;
    win_keep = 1;
    cry(foe.species, 0);
    b0(); app("Wild "); app(NAME(&foe)); app("\nappeared!"); say(buf);
    b0(); app("Go, "); app(NAME(me)); app("!"); say(buf);

    while (1) {
        choice = main_menu();
        if (choice == 0) {
            mv = move_menu();
            if (mv == 255) continue;
        } else if (choice == 1) {
            if (!torcs) { say("No TORCs left!"); continue; }
            if (party_n == MAX_PARTY) { say("Your party\nis full!"); continue; }
            if (throw_torc()) break;
        } else {
            sfx_noise(0x52, 0x33);
            say("Got away safely!");
            break;
        }
        for (n = 0; n != 4 && foe.moves[n]; n++);
        fm = foe.moves[rnd() % n];
        first = choice == 0 && calc_stat(species[me->species].spd, me->level) >= calc_stat(species[foe.species].spd, foe.level);
        if (first && use_move(0, mv)) { won(); break; }
        if (use_move(1, fm)) {
            if (!next_mon()) { lost = 1; break; }
            continue;
        }
        if (choice == 0 && !first && use_move(0, mv)) { won(); break; }
    }
    win_keep = 0;
    HIDE_WIN;
    return lost;
}
