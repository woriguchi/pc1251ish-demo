"""READMEに載せる画像を撮る。

    uv run tools/record_gif.py             全部撮る
    uv run tools/record_gif.py sky_cave    1本だけ

自動操作でプログラムを動かし、液晶のところだけを切り出した各プログラムの
GIFと、筐体ごと写した pc1251.png を docs/ に書く。
撮るためだけのツールなので、ここではpygameもPILも使っている。

自機の位置のような、ゲームのなかの値は sys._getframe で覗いている。
きれいではないが、そのためにゲーム側へ手を入れたくないので、
汚い部分はこのファイルに閉じ込めてある。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402
from PIL import Image  # noqa: E402

from pc1251 import Machine, panel  # noqa: E402

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "docs")
SCALE = 0.62        # 液晶の切り出しをこの倍率で書き出す
EVERY = 2           # 何フレームに1枚残すか。24fps を 12fps にする


def caller_locals(names):
    """呼び出し元をさかのぼって、names を全部持つフレームの局所変数を返す"""
    f = sys._getframe(2)
    while f is not None:
        if all(n in f.f_locals for n in names):
            return f.f_locals
        f = f.f_back
    return {}


def pilot_sky_cave(m):
    from programs import sky_cave as sc
    v = caller_locals(("sy", "scroll"))
    if not v:
        return {"SPACE"}       # タイトル画面。押して始める
    sy, boss, shots = v["sy"], v.get("boss"), v.get("shots") or []
    if boss is not None:
        want = boss.y + sc.CORE_DY
        for sh in shots:                       # 迫ってくる弾は避ける
            eta = (sh[0] - sc.SHIP_X - 2) / 2.4
            if 0 < eta < 16 and abs(sh[1] + sh[2] * eta - sy) < 2.4:
                want = sy + (4.0 if sh[1] < sy else -4.0)
                break
    else:
        t, b = sc.ceil_floor(v["scroll"] + sc.SHIP_X + 26)
        want = (t + b) / 2.0
    want = max(1.0, min(sc.WH - 2.0, want))
    keys = {"SPACE"}
    if sy > want + 0.6:
        keys.add("UP")
    elif sy < want - 0.6:
        keys.add("DOWN")
    return keys


def pilot_jump_hero(m):
    from programs import jump_hero as jh
    v = caller_locals(("hero", "world", "scroll"))
    if not v:
        return {"SPACE"}       # タイトル画面。押して始める
    hero, world, scroll = v["hero"], v["world"], v["scroll"]
    fx = scroll + jh.HX + jh.HERO_W
    near = None
    for kind, wx, _ in world.items:
        if kind not in ("pit", "block", "foe", "roof"):
            continue
        d = wx - fx
        if d < -(jh.ROOF_W if kind == "roof" else 8):
            continue
        if near is None or d < near[1]:
            near = (kind, d)
    if near is None or near[0] == "roof":
        return set()
    kind, d = near
    if not hero.on_ground:
        hold = hero.vy < 0 and (kind == "pit" or hero.y > 1.0)
    else:
        hold = -2 <= d <= 6
    return {"SPACE"} if hold else set()


def pilot_side_break(m):
    from programs import side_break as sb
    v = caller_locals(("pad", "balls"))
    if not v:
        return {"SPACE"}       # タイトル画面。押して始める
    pad, balls = v["pad"], v["balls"]
    if not balls:
        return {"SPACE"}
    inbound = [b for b in balls if b.vx < 0] or balls
    b = min(inbound, key=lambda b: b.x)
    want = b.y + b.vy * (b.x / max(0.2, abs(b.vx))) - (sb.PAD_H - 1) / 2.0
    while want < 0 or want > sb.ROWS - 1:
        want = -want if want < 0 else 2 * (sb.ROWS - 1) - want
    keys = {"SPACE"}
    if pad < want - 0.4:
        keys.add("DOWN")
    elif pad > want + 0.4:
        keys.add("UP")
    return keys


def pilot_none(m):
    return set()


PILOTS = {
    "sky_cave": pilot_sky_cave,
    "jump_hero": pilot_jump_hero,
    "side_break": pilot_side_break,
    "character": pilot_none,
}

# (プログラム名, 何フレーム撮るか, 最初に何フレーム捨てるか)
SHOTS = [
    ("sky_cave", 260, 40),
    ("jump_hero", 260, 60),
    ("side_break", 260, 60),
    ("character", 300, 0),
    ("pcint", 260, 120),
]


class Recorder(Machine):
    """自動操作で動かしながら、液晶のところを1枚ずつ溜めるMachine"""

    def __init__(self, pilot, frames, skip):
        super().__init__(audio=False, persist=1.0)
        self.pilot = pilot
        self.left = frames
        self.skip = skip
        self.n = 0
        self.want = set()
        self.shots = []
        b = panel.LCD_BOX
        self.rect = pygame.Rect(b[0], b[1], b[2] - b[0] + 1, b[3] - b[1] + 1)

    def key(self, name):
        return name in self.want

    def pressed(self, name):
        return name in self.want and self.n % 6 == 0

    def any_pressed(self):
        return False

    def tick(self):
        self.want = self.pilot(self)
        self._present()
        self.frame += 1
        self.n += 1
        if self.n > self.skip:
            if (self.n - self.skip) % EVERY == 0:
                self.shots.append(self._canvas.subsurface(self.rect).copy())
            self.left -= 1
        return self.left > 0


def to_pil(surf, size):
    raw = pygame.image.tostring(surf, "RGB")
    im = Image.frombytes("RGB", surf.get_size(), raw)
    return im.resize(size, Image.LANCZOS)


def record_pcint(frames, skip, prog_name="wave"):
    """PC-インタープリタは自分で走らせる。waveはキーを使わない"""
    from programs.pcint import interp
    prog = [p for p in interp.programs() if p.name == prog_name][0]
    m = Recorder(lambda _m: set(), frames, skip)
    machine = interp.Interp(m, prog, seed=3)
    machine.run()
    m.close()
    return m


def record(name, frames, skip):
    if name == "pcint":
        m = record_pcint(frames, skip)
    else:
        import importlib
        prog = importlib.import_module(f"programs.{name}")
        m = Recorder(PILOTS[name], frames, skip)
        try:
            prog.main(m)
        except SystemExit:
            pass
        finally:
            m.close()
    if not m.shots:
        raise SystemExit(f"{name}: 1枚も撮れなかった")

    w, h = m.shots[0].get_size()
    size = (int(w * SCALE), int(h * SCALE))
    ims = [to_pil(s, size) for s in m.shots]
    # 全部のコマで同じ色を使うため、1枚目から作った色表を使いまわす
    base = ims[0].quantize(colors=64, method=Image.MEDIANCUT)
    ims = [im.quantize(palette=base, dither=Image.NONE) for im in ims]
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, f"{name}.gif")
    ims[0].save(path, save_all=True, append_images=ims[1:],
                duration=int(1000 / 24 * EVERY), loop=0, optimize=True)
    kb = os.path.getsize(path) / 1024
    print(f"{path}  {len(ims)}コマ  {size[0]}x{size[1]}  {kb:.0f}KB")


def still(name="sky_cave", at=200):
    """筐体ごと1枚だけ。READMEのいちばん上に置く"""
    import importlib
    prog = importlib.import_module(f"programs.{name}")
    m = Recorder(PILOTS[name], at, 0)
    m.shots = []                       # 液晶の切り出しは要らない
    try:
        prog.main(m)
    except SystemExit:
        pass
    im = to_pil(m._canvas, (int(panel.IMG_W * 0.5), int(panel.IMG_H * 0.5)))
    m.close()
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, "pc1251.png")
    im.save(path, optimize=True)
    print(f"{path}  {im.size[0]}x{im.size[1]}  "
          f"{os.path.getsize(path) / 1024:.0f}KB")


def main():
    want = sys.argv[1:]
    for name, frames, skip in SHOTS:
        if want and name not in want:
            continue
        record(name, frames, skip)
    if not want:
        still()


if __name__ == "__main__":
    main()
