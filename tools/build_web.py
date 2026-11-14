#!/usr/bin/env python3
"""Builds web/emerald-isle-play.html: the ROM + a JS Game Boy Color emulator in one page.

The emulator core is serverboy (GPL-2.0, based on GameBoy-Online), bundled in
tools/vendor/serverboy.bundle.js. This page is for play-testing only.
"""
import base64, sys

rom = base64.b64encode(open(sys.argv[1], "rb").read()).decode()
core = open("tools/vendor/serverboy.bundle.js").read().replace("</script", "<\\/script")
version = sys.argv[2] if len(sys.argv) > 2 else "dev"

PAGE = r"""<title>Emerald Isle Playtest</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&family=Inter:wght@400;600&display=swap">
<style>
/* Layout: one handheld-shaped column: screen on top, controls under the thumbs. */
:root {
  --bg: #eef1e6; --fg: #1d2a1f; --muted: #5c6b5e;
  --shell: #6a3fa0; --shell-edge: #4c2a78; --shell-fg: #f5ecff;
  --bezel: #1b1d22; --key: #26222e; --key-fg: #f2eef8; --gold: #f2c230;
  --display: "Space Grotesk", system-ui, sans-serif; --body: Inter, system-ui, sans-serif;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg: #141a15; --fg: #e8efe6; --muted: #9aa89b; --shell: #5a3490; --shell-edge: #3b2060; color-scheme: dark } }
:root[data-theme="dark"] {
  --bg: #141a15; --fg: #e8efe6; --muted: #9aa89b; --shell: #5a3490; --shell-edge: #3b2060; color-scheme: dark }
body { background: var(--bg); color: var(--fg); font-family: var(--body);
  padding-block: 20px; padding-left: max(16px, env(safe-area-inset-left, 0px));
  padding-right: max(16px, env(safe-area-inset-right, 0px)); }
main { max-width: 440px; margin: 0 auto; display: flex; flex-direction: column; gap: 16px; }
h1 { font-family: var(--display); font-size: 1.5rem; margin: 0; }
h1 small { font-family: var(--body); font-weight: 400; font-size: .8rem; color: var(--muted); margin-left: .5em; }
.shell { background: var(--shell); border: 3px solid var(--shell-edge); border-radius: 18px 18px 48px 18px;
  padding: 18px; display: flex; flex-direction: column; gap: 22px; color: var(--shell-fg);
  touch-action: none; user-select: none; -webkit-user-select: none; }
.shell:focus-visible { outline: 3px solid var(--gold); outline-offset: 3px; }
.bezel { background: var(--bezel); border-radius: 10px; padding: 14px 22px; }
canvas { display: block; width: 100%; aspect-ratio: 160 / 144; image-rendering: pixelated; background: #000; border-radius: 3px; }
.pad { display: flex; justify-content: space-between; align-items: center; }
.dpad { display: grid; grid-template: repeat(3, 46px) / repeat(3, 46px); }
.k { background: var(--key); color: var(--key-fg); border: 0; font: 700 1rem var(--display);
  display: grid; place-items: center; cursor: pointer; touch-action: none; }
.k.on { background: var(--gold); color: #201828; }
.dpad .k { border-radius: 6px; }
.dpad [data-k="UP"] { grid-area: 1 / 2; } .dpad [data-k="LEFT"] { grid-area: 2 / 1; }
.dpad [data-k="RIGHT"] { grid-area: 2 / 3; } .dpad [data-k="DOWN"] { grid-area: 3 / 2; }
.dpad i { grid-area: 2 / 2; background: var(--key); }
.ab { display: flex; gap: 14px; align-items: center; transform: rotate(-18deg); }
.ab .k { width: 58px; height: 58px; border-radius: 50%; font-size: 1.15rem; }
.meta { display: flex; justify-content: center; gap: 18px; }
.meta .k { padding: 7px 16px; border-radius: 999px; font-size: .7rem; letter-spacing: .08em; }
.sound { align-self: center; background: none; color: var(--fg); border: 1px solid var(--muted);
  border-radius: 999px; padding: 6px 16px; font: 600 .85rem var(--body); cursor: pointer; }
.help { font-size: .9rem; line-height: 1.5; color: var(--muted); margin: 0; }
kbd { font: 600 .8rem var(--body); color: var(--fg); border: 1px solid var(--muted); border-radius: 4px; padding: 0 5px; }
</style>
<main>
  <h1>Emerald Isle <small>playtest build __VERSION__</small></h1>
  <div class="shell" id="shell" tabindex="0" aria-label="Game. Click here, then use the keyboard.">
    <div class="bezel"><canvas id="lcd" width="160" height="144"></canvas></div>
    <div class="pad">
      <div class="dpad">
        <button class="k" id="k-up" data-k="UP" aria-label="Up">▲</button>
        <button class="k" id="k-left" data-k="LEFT" aria-label="Left">◀</button><i></i>
        <button class="k" id="k-right" data-k="RIGHT" aria-label="Right">▶</button>
        <button class="k" id="k-down" data-k="DOWN" aria-label="Down">▼</button>
      </div>
      <div class="ab">
        <button class="k" id="k-b" data-k="B">B</button>
        <button class="k" id="k-a" data-k="A">A</button>
      </div>
    </div>
    <div class="meta">
      <button class="k" id="k-select" data-k="SELECT">SELECT</button>
      <button class="k" id="k-start" data-k="START">START</button>
    </div>
  </div>
  <button class="sound" id="sound" type="button">Sound: on</button>
  <p class="help">Sound starts the first time you press a key or button. Tap the buttons, or click the game and use the keyboard:
    <kbd>Arrows</kbd> or <kbd>WASD</kbd> to walk, <kbd>X</kbd> for A (talk, read),
    <kbd>Z</kbd> for B (hold to run), <kbd>Enter</kbd> for Start.</p>
</main>
<script>__CORE__</script>
<script>
(function () {
  var K = ServerBoy.KEYMAP, held = {};
  var bin = atob("__ROM__"), rom = new Uint8Array(bin.length);
  for (var i = 0; i < bin.length; i++) rom[i] = bin.charCodeAt(i);
  // Saved games: the cartridge's battery RAM is kept in this browser.
  var SAVE_KEY = "emerald-isle-save", lastSave = "";
  function readSave() {
    try { var t = localStorage.getItem(SAVE_KEY); if (t) { lastSave = t; return JSON.parse(t); } } catch (err) {}
    return null;
  }
  var gb = new ServerBoy(); gb.loadRom(rom, readSave() || undefined);
  setInterval(function () {
    try {
      var d = gb.getSaveData();
      if (!d || !d.length) return;
      var t = JSON.stringify(Array.prototype.slice.call(d));
      if (t !== lastSave) { localStorage.setItem(SAVE_KEY, t); lastSave = t; }
    } catch (err) {}
  }, 2000);

  // Sound: collect the emulator's samples and play them through Web Audio.
  var core = gb["_0.1"].gameboy;
  var rate = core.clocksPerSecond / core.audioResamplerFirstPassFactor;
  var N = 32768, qL = new Float32Array(N), qR = new Float32Array(N), wr = 0, rd = 0, actx = null, muted = false;
  core.outputAudio = function () {
    qL[wr] = (this.downsampleInput >>> 16) * this.downSampleInputDivider - 1;
    qR[wr] = (this.downsampleInput & 0xFFFF) * this.downSampleInputDivider - 1;
    wr = (wr + 1) % N;
    this.downsampleInput = 0;
  };
  function startAudio() {
    if (actx) { if (actx.state === "suspended") actx.resume(); return; }
    var AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return;
    try {
      actx = new AC();
      var node = actx.createScriptProcessor(2048, 0, 2), step = rate / actx.sampleRate, pos = 0;
      var target = rate * 0.09, started = false, inL = -1, inR = -1, hpL = 0, hpR = 0;       // hold about 90 ms in hand so playback never runs dry
      node.onaudioprocess = function (e) {
        var L = e.outputBuffer.getChannelData(0), R = e.outputBuffer.getChannelData(1), i = 0, n;
        var avail = (wr - rd + N) % N;
        if (!started && avail >= target) started = true;
        if (avail > rate * 0.3) { rd = (wr - Math.floor(target) + N) % N; avail = (wr - rd + N) % N; }
        // nudge the playback speed by up to 1% to keep the buffer near its target
        var adj = step * (1 + Math.max(-0.01, Math.min(0.01, (avail - target) / target * 0.02)));
        var x;
        if (started && !muted) {
          for (; i < L.length; i++) {
            if (avail < 3) { started = false; break; }
            n = (rd + 1) % N;                           // blend neighbouring samples: no stair-step fuzz
            // The raw signal rests at -1, not 0. Filter that offset out, or every
            // pause and resume would land as a click.
            x = qL[rd] * (1 - pos) + qL[n] * pos; hpL = x - inL + 0.999 * hpL; inL = x; L[i] = hpL * 0.6;
            x = qR[rd] * (1 - pos) + qR[n] * pos; hpR = x - inR + 0.999 * hpR; inR = x; R[i] = hpR * 0.6;
            pos += adj;
            while (pos >= 1 && avail > 2) { pos -= 1; rd = (rd + 1) % N; avail--; }
          }
        }
        for (; i < L.length; i++) L[i] = R[i] = 0;
      };
      node.connect(actx.destination);
    } catch (err) { actx = null; }
  }
  var soundBtn = document.getElementById("sound");
  soundBtn.addEventListener("click", function () {
    muted = !muted; startAudio();
    soundBtn.textContent = muted ? "Sound: off" : "Sound: on";
  });
  addEventListener("pointerdown", startAudio); addEventListener("keydown", startAudio);

  var ctx = document.getElementById("lcd").getContext("2d");
  var img = ctx.createImageData(160, 144);
  var keys = { ArrowUp: "UP", ArrowDown: "DOWN", ArrowLeft: "LEFT", ArrowRight: "RIGHT",
    w: "UP", s: "DOWN", a: "LEFT", d: "RIGHT", x: "A", z: "B", Enter: "START", Shift: "SELECT" };
  function set(name, on) {
    held[name] = on;
    var b = document.querySelector('[data-k="' + name + '"]');
    if (b) b.classList.toggle("on", on);
  }
  function key(e, on) {
    var n = keys[e.key.length === 1 ? e.key.toLowerCase() : e.key];
    if (!n || e.metaKey || e.ctrlKey) return;
    e.preventDefault(); set(n, on);
  }
  addEventListener("keydown", function (e) { key(e, true); });
  addEventListener("keyup", function (e) { key(e, false); });
  addEventListener("blur", function () { for (var n in held) set(n, false); });
  document.querySelectorAll(".k").forEach(function (b) {
    var n = b.dataset.k;
    b.addEventListener("pointerdown", function (e) { e.preventDefault(); b.setPointerCapture(e.pointerId); set(n, true); });
    ["pointerup", "pointercancel", "lostpointercapture"].forEach(function (t) {
      b.addEventListener(t, function () { set(n, false); });
    });
    b.addEventListener("contextmenu", function (e) { e.preventDefault(); });
  });

  // One emulator step is a fixed slice of Game Boy time (8 ms), not one screen
  // refresh, so pace the steps by the clock to run at true speed.
  var FRAME = core.baseCPUCyclesPerIteration / core.clocksPerSecond * 1000, last = performance.now(), acc = 0;
  function frame() {
    var pressed = [];
    for (var n in held) if (held[n]) pressed.push(K[n]);
    gb.pressKeys(pressed);
    return gb.doFrame();
  }
  function loop(now) {
    acc += Math.min(now - last, 100); last = now;
    var screen = null;
    while (acc >= FRAME) { screen = frame(); acc -= FRAME; }
    if (screen) { img.data.set(screen); ctx.putImageData(img, 0, 0); }
    requestAnimationFrame(loop);
  }
  img.data.set(frame()); ctx.putImageData(img, 0, 0);
  requestAnimationFrame(loop);
  window.__gb = { held: held, queued: function () { return (wr - rd + N) % N; }, written: function () { return wr; }, rate: rate };
})();
</script>
"""
out = PAGE.replace("__CORE__", core).replace("__ROM__", rom).replace("__VERSION__", version)
open("web/emerald-isle-play.html", "w").write(out)
print(f"web/emerald-isle-play.html: {len(out) // 1024} KB")
