"""ポケコン1台ぶんのシミュレータ

画面(120x7ドット)、キー、フレームの時計を持つ。
programs/からはこのMachineだけが見えていればよく、pygameとPillowは
ここから外へ出さない。
"""

import math
import time

import pygame

from . import panel, sound
from .buffer import CELL_W, CELLS, HEIGHT, WIDTH, Buffer

FPS = 24

KEYMAP = {
    "UP": (pygame.K_UP, pygame.K_w),
    "DOWN": (pygame.K_DOWN, pygame.K_s),
    "LEFT": (pygame.K_LEFT, pygame.K_a),
    "RIGHT": (pygame.K_RIGHT, pygame.K_d),
    "SPACE": (pygame.K_SPACE,),
    "ENTER": (pygame.K_RETURN, pygame.K_KP_ENTER),
    "BRK": (pygame.K_ESCAPE,),
}

# 実機は数字と英字のキーを持っているので、こちらでも拾えるようにする。
# 矢印にWASDを割り当ててあるぶん、A S D W は矢印としても入る。
for _i in range(10):
    KEYMAP.setdefault(str(_i), (getattr(pygame, f"K_{_i}"),
                                getattr(pygame, f"K_KP{_i}")))
for _c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
    KEYMAP.setdefault(_c, (getattr(pygame, f"K_{_c.lower()}"),))


class Machine:
    WIDTH = WIDTH
    HEIGHT = HEIGHT
    CELLS = CELLS
    CELL_W = CELL_W
    FPS = FPS

    # 残像の強さ。1.0が実測の時定数どおり、0で残像なし
    PERSIST_STEPS = (0.0, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0)

    def __init__(self, scale: float = 1.0, title: str = "SHARP PC-1251",
                 audio: bool = True, persist: float = 1.0):
        if audio:
            pygame.mixer.pre_init(sound.RATE, -16, 1, 512)
        pygame.init()
        pygame.display.set_caption(title)
        # 圧電ブザーは1つしかないので、鳴らせる音も常に1つ
        self._buzzer = None
        if audio:
            try:
                pygame.mixer.init(sound.RATE, -16, 1, 512)
                self._buzzer = pygame.mixer.Channel(0)
            except pygame.error:
                pass
        self._tones = {}
        self.scale = scale = self._fit(scale)
        size = (int(panel.IMG_W * scale), int(panel.IMG_H * scale))
        self._window = pygame.display.set_mode(size)
        self._canvas = pygame.Surface((panel.IMG_W, panel.IMG_H))

        body = panel.make_body()
        self._canvas.blit(to_surface(body), (0, 0))
        self._glass = to_surface(panel.glass_patch(body))
        self._ann_bg = to_surface(panel.ann_patch(body))
        self._ann_cache = {}
        self._dots = [self._dot_image(lv) for lv in range(panel.LEVELS)]
        self._rects = panel.dot_rects()

        self.screen = Buffer(HEIGHT)
        self._level = [[0.0] * WIDTH for _ in range(HEIGHT)]
        self._persist = 1.0
        self.persist = persist
        self._osd = 0
        self._osd_cache = {}

        self._clock = pygame.time.Clock()
        self._held = set()
        self._edge = set()
        self._symbols = {"RUN", "DEG"}
        self.frame = 0
        self._t0 = time.monotonic()

    @property
    def persist(self) -> float:
        """残像の強さ。時定数にかける倍率。0で残像なし。"""
        return self._persist

    @persist.setter
    def persist(self, value: float) -> None:
        self._persist = max(0.0, min(4.0, float(value)))
        dt = 1000.0 / FPS
        if self._persist == 0.0:
            self._rise = self._fall = 1.0
        else:
            self._rise = 1.0 - math.exp(-dt / (panel.TAU_RISE_MS
                                               * self._persist))
            self._fall = 1.0 - math.exp(-dt / (panel.TAU_FALL_MS
                                               * self._persist))

    def _step_persist(self, direction: int) -> None:
        steps = self.PERSIST_STEPS
        i = min(range(len(steps)),
                key=lambda k: abs(steps[k] - self._persist))
        self.persist = steps[max(0, min(len(steps) - 1, i + direction))]
        self._osd = FPS * 2

    @staticmethod
    def _fit(scale: float) -> float:
        """デスクトップに入る範囲まで拡大率を落とす"""
        # 80と120はウィンドウ枠とタスクバーのぶん。てきとう
        try:
            dw, dh = pygame.display.get_desktop_sizes()[0]
        except (pygame.error, IndexError):
            return scale
        room = min((dw - 80) / panel.IMG_W, (dh - 120) / panel.IMG_H)
        return min(scale, max(0.35, room))

    @staticmethod
    def _dot_image(level: int) -> pygame.Surface:
        s = pygame.Surface((panel.DOT, panel.DOT), pygame.SRCALPHA)
        s.fill(panel.DOT_INK + (panel.DOT_ALPHA[level],))
        return s

    def cls(self) -> None:
        self.screen.cls()

    def px(self, x: int, y: int, on: bool = True) -> None:
        self.screen.px(x, y, on)

    def get(self, x: int, y: int) -> int:
        return self.screen.get(x, y)

    def hline(self, x0: int, x1: int, y: int, on: bool = True) -> None:
        self.screen.hline(x0, x1, y, on)

    def vline(self, x: int, y0: int, y1: int, on: bool = True) -> None:
        self.screen.vline(x, y0, y1, on)

    def box(self, x0: int, y0: int, x1: int, y1: int, on: bool = True) -> None:
        self.screen.box(x0, y0, x1, y1, on)

    def outline(self, x0: int, y0: int, x1: int, y1: int,
                on: bool = True) -> None:
        self.screen.outline(x0, y0, x1, y1, on)

    def sprite(self, x: int, y: int, rows, on: bool = True) -> None:
        self.screen.sprite(x, y, rows, on)

    def erase(self, x: int, y: int, w: int, h: int, margin: int = 0) -> None:
        self.screen.erase(x, y, w, h, margin)

    def text(self, x: int, s: str, y: int = 0, scale: int = 1) -> None:
        self.screen.text(x, s, y, scale)

    def cell_text(self, cell: int, s: str) -> None:
        self.screen.cell_text(cell, s)

    def gprint(self, x: int, cols) -> None:
        self.screen.gprint(x, cols)

    def invert(self, x0: int = 0, y0: int = 0, x1: int = WIDTH - 1,
               y1: int = HEIGHT - 1) -> None:
        self.screen.invert(x0, y0, x1, y1)

    def show(self, buf: Buffer, top: int = 0) -> None:
        """画面より高いバッファの一部を画面へ写す"""
        buf.window(top, self.screen)

    def symbol(self, name: str, on: bool = True) -> None:
        """BUSY / RUN / DEGなどのインジケータ"""
        if on:
            self._symbols.add(name)
        else:
            self._symbols.discard(name)

    def key(self, name: str) -> bool:
        return name in self._held

    def pressed(self, name: str) -> bool:
        """このフレームで押された瞬間だけTrue"""
        return name in self._edge

    def any_pressed(self) -> bool:
        return bool(self._edge)

    def flush_keys(self) -> None:
        """溜まっているキーを捨てる

        別のプログラムへ移るときに呼ぶ。呼ばないと、前のプログラムを
        終わらせたキーを次のプログラムがそのまま読んでしまう。
        """
        self._edge.clear()
        self._held.clear()

    def inkey(self) -> str:
        """押されているキーを1つ返す。なければ空文字。"""
        for name in self._held:
            return name
        return ""

    def beep(self, hz: float, ms: int = 60, vol: float = 0.5) -> None:
        """圧電ブザーを鳴らす

        出せるのは矩形波だけで、音程は待ちループの回数nで決まる
        f = 36000/n の飛び飛びの値になる。指定した高さはいちばん近い
        ものに丸まる。鳴っている音があれば止めて、この音に切り替える。
        """
        if self._buzzer is None:
            return
        key = (sound.quantize(hz)[1], ms, round(vol, 2))
        snd = self._tones.get(key)
        if snd is None:
            snd = pygame.mixer.Sound(buffer=sound.render(hz, ms, vol))
            self._tones[key] = snd
        self._buzzer.play(snd)

    def seconds(self) -> float:
        return time.monotonic() - self._t0

    def wait(self, frames: int) -> bool:
        """画面をそのままにして指定フレーム待つ"""
        for _ in range(frames):
            if not self.tick():
                return False
        return True

    def tick(self) -> bool:
        """今の画面を出して次のフレームまで待つ。Falseなら終了。"""
        self._present()
        self._clock.tick(FPS)
        self.frame += 1
        self._edge.clear()
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                return False
            if ev.type == pygame.KEYDOWN:
                # 残像の量はマシン側の設定なのでプログラムには渡さない
                if ev.key == pygame.K_LEFTBRACKET:
                    self._step_persist(-1)
                elif ev.key == pygame.K_RIGHTBRACKET:
                    self._step_persist(+1)
                for name, codes in KEYMAP.items():
                    if ev.key in codes:
                        self._held.add(name)
                        self._edge.add(name)
            elif ev.type == pygame.KEYUP:
                for name, codes in KEYMAP.items():
                    if ev.key in codes:
                        self._held.discard(name)
        return True

    def close(self) -> None:
        pygame.quit()

    def _draw_osd(self, dst: pygame.Surface) -> None:
        """残像の設定値を表示する。インジケータの空いている右側を使う。"""
        v = self._persist
        text = f"PERSIST {v:g}" if v else "PERSIST OFF"
        surf = self._osd_cache.get(text)
        if surf is None:
            surf = to_surface(panel.osd_img(text))
            self._osd_cache[text] = surf
        x = panel.MAT_X + panel.MAT_W - surf.get_width()
        dst.blit(surf, (x, panel.ANN_Y))

    def _present(self) -> None:
        # 消灯しているドットの枡目は下地に焼き込んであるので、
        # ここでは輝度が残っているものだけ重ねる。
        rise, fall = self._rise, self._fall
        level = self._level
        dst = self._canvas
        dst.blit(self._glass, (panel.MAT_X, panel.MAT_Y))
        mx, my = panel.MAT_X, panel.MAT_Y
        dots = self._dots
        rects = self._rects
        top = panel.LEVELS - 1
        for y in range(HEIGHT):
            row, lrow, rrow = self.screen.d[y], level[y], rects[y]
            for x in range(WIDTH):
                v = lrow[x]
                if row[x]:
                    v += (1.0 - v) * rise
                else:
                    v -= v * fall
                    if v < 0.004:
                        v = 0.0
                lrow[x] = v
                step = int(v * top + 0.5)
                if step:
                    r = rrow[x]
                    dst.blit(dots[step], (mx + r[0], my + r[1]))

        key = tuple(sorted(self._symbols))
        surf = self._ann_cache.get(key)
        if surf is None:
            surf = to_surface(panel.ann_overlay(key))
            self._ann_cache[key] = surf
        dst.blit(self._ann_bg, (panel.MAT_X, panel.ANN_Y))
        dst.blit(surf, (panel.MAT_X, panel.ANN_Y))
        if self._osd > 0:
            self._osd -= 1
            self._draw_osd(dst)

        if self.scale == 1.0:
            self._window.blit(dst, (0, 0))
        elif self.scale > 1.0:
            # 拡大は補間しない。ドットの角を残したいので最近傍で伸ばす
            pygame.transform.scale(dst, self._window.get_size(), self._window)
        else:
            pygame.transform.smoothscale(dst, self._window.get_size(),
                                         self._window)
        pygame.display.flip()


def to_surface(img) -> pygame.Surface:
    mode = img.mode
    if mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA")
        mode = "RGBA"
    surf = pygame.image.fromstring(img.tobytes(), img.size, mode)
    return surf.convert_alpha() if mode == "RGBA" else surf.convert()
