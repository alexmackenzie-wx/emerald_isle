// Emerald Isle - trading cards: opening packs, the binder, and the badge screen.
// This file lives in ROM bank 7 and calls only the shared engine in bank 0.
#pragma bank 7
#include "core.h"

#define CARD_SPECIES 8          // cards exist for the first eight PMON so far

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

// A PMON's own card, as found in booster packs.
static void draw_mon_card(uint8_t sp, uint8_t shiny, uint8_t fresh) {
    draw_frame(shiny ? K_SHINY : K_CARD);
    print_centre(CARD_X, CARD_W, CARD_Y + 1, species[sp].name);
    load_art(sp, 128, 0);
    set_bkg_palette(K_GRASS, 1, art_pals[sp]);          // both off screen while the card is drawn
    set_bkg_palette(K_FOIL, 1, art_pals2[sp]);
    put_art(CARD_X + 2, CARD_Y + 3, 128, K_GRASS, K_FOIL, art_mask[sp], 0);
    print_centre(CARD_X, CARD_W, CARD_Y + 12, type_names[species[sp].type]);
    if (shiny) print_centre(CARD_X, CARD_W, CARD_Y + 14, "* SHINY *");
    else if (fresh) print_centre(CARD_X, CARD_W, CARD_Y + 14, "NEW!");
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
// boost: 0 the starter pack; 1 a bought pack, PMON cards among the energy; 2 a gold pack, no energy and rarer PMON
void open_pack(uint8_t boost) BANKED {
    uint8_t i, pick, order[3], k = 0, bit;
    DISPLAY_OFF;
    still = 1;                  // outdoors, keep the breeze from drawing over the cards
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
    tick(); tick(); tick(); tick();
    set_bkg_palette(0, 8, pack_pals);               // after the flash, while the first card is still off screen
    for (i = 0; i != 4; i++) {
        if (!boost) draw_card(i == 3, i == 3 ? pick : order[i]);
        else {
            // FAOLAN and GANDAL (the last two) are the rare ones: only gold packs hold them
            if (boost == 2) k = (rnd() & 1) ? CARD_SPECIES - 2 + (rnd() & 1) : rnd() % (CARD_SPECIES - 2);
            else k = rnd() % (i == 3 ? CARD_SPECIES - 2 : CARD_SPECIES + 1);
            if (k >= CARD_SPECIES - 2 && boost == 1) draw_card(0, k - (CARD_SPECIES - 2));       // an energy card
            else {
                bit = 1 << k;
                draw_mon_card(k, i == 3, !(cards & bit));
                if (i == 3) shiny_cards |= bit; else cards |= bit;
            }
        }
        if (i == 3) { for (; frame_count & 31; ) tick(); }   // a beat before the last card
        sfx_noise(0x41, 0x22);                                  // card slides in
        slide(128, i == 3);
        if (i == 3) cry(boost ? k : pick, 1);
        wait_card(i == 3);
        if (i != 3) slide(0, 0);
    }
    hide_sprites_from(12);
    if (boost) return;
    starter = pick;
    say_t(TXT_CARD);
}


// The binder: every card there is to find, one to a page. LEFT and RIGHT turn the pages.
void binder(void) BANKED {
    uint8_t i = 0, p, shown = 255, sp = 0, own = 0;
    DISPLAY_OFF;
    still = 1;
    hide_sprites_from(0);
    set_bkg_palette(0, 8, pack_pals);
    rect(0, 0, 32, 32, 0, K_DARK);
    move_bkg(0, 0);
    print_bkg(0, 17, "<");  print_bkg(19, 17, ">");
    DISPLAY_ON;
    while (1) {
        if (shown != i) {
            shown = i; sp = i & 7;
            own = ((i & 8) ? shiny_cards : cards) & (1 << sp);
            hide_sprites_from(12);
            if (own) draw_mon_card(sp, i & 8, 0);
            else {
                draw_frame(K_CARD);
                print_centre(CARD_X, CARD_W, CARD_Y + 6, "?");
                print_centre(CARD_X, CARD_W, CARD_Y + 12, (i & 8) ? "A SHINY" : "A CARD");
                print_centre(CARD_X, CARD_W, CARD_Y + 14, "NOT FOUND");
            }
            print_bkg(2, 17, "No.");
            set_bkg_tile_xy(5, 17, '0' + (i + 1) / 10 - 32); set_bkg_tile_xy(6, 17, '0' + (i + 1) % 10 - 32);
            print_bkg(12, 17, "B:BACK");
        }
        if (own && (i & 8)) sparkle();
        tick();
        p = pressed();
        if (p & (J_B | J_START)) break;
        if (p & J_RIGHT) { i = (i + 1) & 15; sfx_type(); }
        if (p & J_LEFT) { i = (i - 1) & 15; sfx_type(); }
    }
    hide_sprites_from(12);
}

// ---------------------------------------------------------------- the START menu's screens
static void box(uint8_t x, uint8_t y, uint8_t w, uint8_t h) {       // a framed panel on the background
    uint8_t i, x1 = x + w - 1, y1 = y + h - 1;
    rect(x, y, w, h, 0, P_UI);
    for (i = x + 1; i != x1; i++) { set_bkg_tile_xy(i, y, FR_T); set_bkg_tile_xy(i, y1, FR_B); }
    for (i = y + 1; i != y1; i++) { set_bkg_tile_xy(x, i, FR_L); set_bkg_tile_xy(x1, i, FR_R); }
    set_bkg_tile_xy(x, y, FR_TL); set_bkg_tile_xy(x1, y, FR_TR);
    set_bkg_tile_xy(x, y1, FR_BL); set_bkg_tile_xy(x1, y1, FR_BR);
}

static void num(uint8_t x, uint8_t y, uint16_t n, uint8_t w) {      // right-aligned in w places
    uint8_t i;
    for (i = w; i--; ) { set_bkg_tile_xy(x + i, y, (n || i == w - 1) ? '0' + n % 10 - 32 : 0); n /= 10; }
}

// ITEMS: a list with how many of each, and a few words on whichever the arrow is at.
static const char * const item_name[4] = { "POTION", "CREAM SODA", "BIRD WHISTLE", "TM SUPERSOAK" };
static const char * const item_help[4][2] = {
    { "Restores 20 HP to", "a hurt PMON." },
    { "Raises your lead", "PMON by one level." },
    { "A tune for calling", "birds. Play it!" },
    { "Teaches SUPERSOAK", "to your lead PMON." } };

static uint8_t item_have(uint8_t i) {
    return i == 0 ? potions : i == 1 ? sodas : i == 2 ? (flags & FLAG_WHISTLE) != 0 : tms & 1;
}

void bag(void) BANKED {
    static const uint8_t tune[6] = { 61, 65, 68, 65, 68, 73 };
    uint8_t c = 0, p, i, k, redraw = 1, shown = 255;
    char b[32];
    still = 1;
    hide_sprites_from(0);
    move_bkg(0, 0);
    while (1) {
        if (redraw) {
            redraw = 0; shown = 255;
            rect(0, 0, 20, 18, 0, P_UI);
            print_bkg(7, 1, "ITEMS");
            for (i = 1; i != 19; i++) set_bkg_tile_xy(i, 2, FR_B);
            for (i = 0; i != 4; i++) {
                print_bkg(3, 4 + (i << 1), item_have(i) ? item_name[i] : "?");
                if (i < 2 && item_have(i)) { set_bkg_tile_xy(15, 4 + (i << 1), 'x' - 32); num(16, 4 + (i << 1), i ? sodas : potions, 2); }
            }
            box(0, 12, 20, 6);
        }
        if (shown != c) {                           // what it does, in the panel underneath
            shown = c;
            print_bkg(1, 14, "                  "); print_bkg(1, 15, "                  ");
            if (item_have(c)) { print_bkg(1, 14, item_help[c][0]); print_bkg(1, 15, item_help[c][1]); }
        }
        set_bkg_tile_xy(1, 4 + (c << 1), '>' - 32);
        do { tick(); p = pressed(); } while (!p);
        set_bkg_tile_xy(1, 4 + (c << 1), 0);
        if (p & (J_B | J_START | J_LEFT)) break;
        if ((p & J_UP) && c) { c--; sfx_type(); }
        if ((p & J_DOWN) && c != 3) { c++; sfx_type(); }
        if (!(p & J_A)) continue;
        redraw = 1;
        if (c == 0 && potions) {                    // 20 HP for the first hurt PMON still standing
            for (i = 0; i != party_n; i++) if (party[i].hp && party[i].hp < party[i].maxhp) break;
            if (i == party_n) { say_t(TXT_NOPOTION); continue; }
            potions--;
            party[i].hp += 20;
            if (party[i].hp > party[i].maxhp) party[i].hp = party[i].maxhp;
            sfx_blip();
            say_t(TXT_POTION);
        } else if (c == 1 && sodas) {               // one level for the PMON at the front
            if (!party_n) { say_t(TXT_NOSODA); continue; }
            sodas--;
            level_up(&party[0]);
            sfx_note(49, 0x80, 0x92); for (k = 0; k != 8; k++) tick();
            sfx_note(61, 0x80, 0x92);
            say_num = party[0].level;
            say_t(TXT_SODA);
        } else if (c == 2 && (flags & FLAG_WHISTLE)) {
            for (i = 0; i != 6; i++) { sfx_note(tune[i], 0x40, 0x83); for (k = 0; k != 8; k++) tick(); }
            say_t(TXT_WHISTLE);
        } else if (c == 3 && (tms & 1)) {           // a TM can be used again and again
            if (!party_n) { say_t(TXT_NOSODA); continue; }
            teach(&party[0], MV_SUPERSOAK);
            sfx_note(56, 0x80, 0x92); for (k = 0; k != 8; k++) tick();
            sfx_note(68, 0x80, 0x92);
            strcpy(b, species[party[0].species].name); strcat(b, " learned\nSUPERSOAK!");
            say(b);
        } else { sfx_note(30, 0x40, 0x52); say_t(TXT_NOITEM); }
    }
}

// PMON: the party, each with its level and an HP bar. Pick one, then another, to swap their places.
void party_screen(void) BANKED {
    uint8_t c = 0, p, i, k, held = 255, redraw = 1, y;
    uint16_t fill;
    mon_t t;
    still = 1;
    hide_sprites_from(0);
    move_bkg(0, 0);
    while (1) {
        if (redraw) {
            redraw = 0;
            rect(0, 0, 20, 18, 0, P_UI);
            for (i = 0; i != party_n; i++) {
                y = 1 + (i << 1);
                print_bkg(2, y, species[party[i].species].name);
                set_bkg_tile_xy(10, y, 'L' - 32); set_bkg_tile_xy(11, y, 'v' - 32); num(12, y, party[i].level, 3);
                num(12, y + 1, party[i].hp, 3); set_bkg_tile_xy(15, y + 1, '/' - 32); num(16, y + 1, party[i].maxhp, 3);
                print_bkg(2, y + 1, "HP");
                // the bar, in a palette of its own so each can have its colour
                fill = (uint32_t)party[i].hp * 48 / party[i].maxhp;
                if (party[i].hp && !fill) fill = 1;
                set_bkg_palette(i, 1, cur->pals + 28);
                set_bkg_palette_entry(i, 1, fill > 24 ? RGB8(72, 200, 72) : fill > 10 ? RGB8(240, 200, 40) : RGB8(232, 64, 48));
                set_bkg_palette_entry(i, 2, RGB8(200, 200, 200));
                for (k = 0; k != 6; k++) {
                    p = fill > 8 ? 8 : fill; fill -= p;
                    VBK_REG = 1; set_bkg_tile_xy(4 + k, y + 1, i | 0x08);
                    VBK_REG = 0; set_bkg_tile_xy(4 + k, y + 1, 96 + p);
                }
                if (i == held) set_bkg_tile_xy(0, y, '*' - 32);
            }
            box(0, 13, 20, 5);
            print_bkg(1, 15, !party_n ? "No PMON yet." : held == 255 ? "Choose a PMON." : "Move it where?");
        }
        if (party_n) set_bkg_tile_xy(1, 1 + (c << 1), '>' - 32);
        do { tick(); p = pressed(); } while (!p);
        set_bkg_tile_xy(1, 1 + (c << 1), 0);
        if (p & (J_B | J_START)) { if (held != 255) { held = 255; redraw = 1; sfx_type(); continue; } break; }
        if ((p & J_UP) && c) { c--; sfx_type(); }
        if ((p & J_DOWN) && c + 1 < party_n) { c++; sfx_type(); }
        if ((p & J_A) && party_n) {
            sfx_blip();
            if (held == 255) held = c;
            else { t = party[held]; party[held] = party[c]; party[c] = t; held = 255; }
            redraw = 1;
        }
    }
}

// The trainer's own card: name, money, badges, what is in the bag and the binder.
void trainer_card(void) BANKED {
    uint8_t n = 0, b;
    still = 1;
    hide_sprites_from(0);
    move_bkg(0, 0);
    rect(0, 0, 20, 18, 0, P_UI);
    box(1, 1, 18, 14);
    print_bkg(3, 3, "TRAINER"); print_bkg(11, 3, name);
    print_bkg(3, 5, "MONEY"); set_bkg_tile_xy(11, 5, FR_EURO); num(12, 5, money, 5);
    print_bkg(3, 7, "BADGES"); num(14, 7, (flags & FLAG_BADGE) ? 1 : 0, 3);
    if (flags & FLAG_BADGE) print_bkg(3, 8, " FEATHER");
    print_bkg(3, 10, "PBALLS"); num(14, 10, torcs, 3);
    for (b = 1; b; b <<= 1) { if (cards & b) n++; if (shiny_cards & b) n++; }
    print_bkg(3, 12, "CARDS"); num(11, 12, n, 3); print_bkg(14, 12, "/16");
    print_bkg(6, 16, "B:BACK");
    while (!(pressed() & (J_A | J_B | J_START))) tick();
}

// The Feather Badge, large, on a dark screen, its edge shimmering.
void badge_scene(void) BANKED {
    static const uint8_t fan[8] = { 49, 53, 56, 61, 56, 61, 65, 68 };
    uint8_t x, y, t = 128;
    DISPLAY_OFF;
    music_stop();
    hide_sprites_from(0);
    set_bkg_palette(0, 8, pack_pals);
    set_bkg_palette(K_SHINY, 1, badge_pal);
    rect(0, 0, 32, 32, 0, K_DARK);
    move_bkg(0, 0);
    bank_copy(PIC_BANK, badge_art, art_buf, 1024);
    VBK_REG = 1; set_bkg_data(128, 64, art_buf); VBK_REG = 0;
    cur_extra = 255;
    for (y = 0; y != 8; y++)
        for (x = 0; x != 8; x++, t++) {
            VBK_REG = 1; set_bkg_tile_xy(6 + x, 2 + y, K_SHINY | 0x08);
            VBK_REG = 0; set_bkg_tile_xy(6 + x, 2 + y, t);
        }
    print_bkg(3, 11, "FEATHER  BADGE");
    still = 1;
    DISPLAY_ON;
    for (x = 0; x != 200; x++) {
        if (x < 128 && (x & 15) == 0) sfx_note(fan[x >> 4], 0x80, 0xA3);
        sparkle(); tick();
    }
    say_t(TXT_BADGE);
    hide_sprites_from(12);
}

