"""ドットバッファ

画面は5x7ドットの文字セルが24個ならび、セル間が1ドットあいている。
プログラムから触れるのは24x5 = 120x7ドットで、セル間のすきまは書けない。
Bufferの高さは7ドットに固定していないので、画面より大きい仮想画面を作って
その一部を画面へ写す、という使い方ができる。
"""

from .font import FONT

WIDTH = 120
HEIGHT = 7
CELLS = 24
CELL_W = 5


class Buffer:
    __slots__ = ("h", "d")

    def __init__(self, h: int = HEIGHT):
        self.h = h
        self.d = [bytearray(WIDTH) for _ in range(h)]

    def cls(self) -> None:
        for row in self.d:
            for i in range(WIDTH):
                row[i] = 0

    def px(self, x: int, y: int, on: bool = True) -> None:
        if 0 <= x < WIDTH and 0 <= y < self.h:
            self.d[y][x] = 1 if on else 0

    def get(self, x: int, y: int) -> int:
        if 0 <= x < WIDTH and 0 <= y < self.h:
            return self.d[y][x]
        return 0

    def hline(self, x0: int, x1: int, y: int, on: bool = True) -> None:
        for x in range(int(x0), int(x1) + 1):
            self.px(x, y, on)

    def vline(self, x: int, y0: int, y1: int, on: bool = True) -> None:
        for y in range(int(y0), int(y1) + 1):
            self.px(x, y, on)

    def box(self, x0: int, y0: int, x1: int, y1: int, on: bool = True) -> None:
        for y in range(int(y0), int(y1) + 1):
            for x in range(int(x0), int(x1) + 1):
                self.px(x, y, on)

    def outline(self, x0: int, y0: int, x1: int, y1: int,
                on: bool = True) -> None:
        self.hline(x0, x1, y0, on)
        self.hline(x0, x1, y1, on)
        self.vline(x0, y0, y1, on)
        self.vline(x1, y0, y1, on)

    def invert(self, x0: int = 0, y0: int = 0, x1: int = WIDTH - 1,
               y1: int | None = None) -> None:
        if y1 is None:
            y1 = self.h - 1
        for y in range(max(0, y0), min(self.h - 1, y1) + 1):
            row = self.d[y]
            for x in range(max(0, x0), min(WIDTH - 1, x1) + 1):
                row[x] ^= 1

    def sprite(self, x: int, y: int, rows, on: bool = True) -> None:
        """rowsは"#"が点、それ以外が消灯の文字列リスト"""
        for j, r in enumerate(rows):
            for i, ch in enumerate(r):
                if ch == "#":
                    self.px(x + i, y + j, on)

    def erase(self, x: int, y: int, w: int, h: int, margin: int = 0) -> None:
        """marginを付けると、スプライトの縁を消して白フチにできる"""
        for j in range(-margin, h + margin):
            for i in range(-margin, w + margin):
                self.px(x + i, y + j, False)

    def char(self, x: int, c: str, y: int = 0, scale: int = 1) -> None:
        g = FONT.get(c.upper(), FONT["?"])
        for j in range(7):
            for i in range(5):
                if not g[j][i]:
                    continue
                if scale == 1:
                    self.px(x + i, y + j)
                else:
                    for a in range(scale):
                        for b in range(scale):
                            self.px(x + i * scale + b, y + j * scale + a)

    def text(self, x: int, s: str, y: int = 0, scale: int = 1) -> None:
        """x, yはドット単位。文字は5ドット幅で詰めて置く。"""
        for k, c in enumerate(s):
            self.char(x + k * CELL_W * scale, c, y, scale)

    def cell_text(self, cell: int, s: str) -> None:
        """文字セルの番号(0..23)を指定して文字を置く"""
        self.text(cell * CELL_W, s)

    def gprint(self, x: int, cols) -> None:
        """列データを並べる。1要素が縦7ドットで、bit0が上端。"""
        for i, v in enumerate(cols):
            for y in range(7):
                if v >> y & 1:
                    self.px(x + i, y)

    def window(self, top: int, dst: "Buffer") -> None:
        """自分のy=topからdstの高さぶんをdstへ写す"""
        top = int(round(top))
        blank = bytearray(WIDTH)
        for j in range(dst.h):
            y = top + j
            dst.d[j][:] = self.d[y] if 0 <= y < self.h else blank


def centered(s: str, scale: int = 1) -> int:
    """文字列を文字セルの境目にそろえて中央に置くx座標"""
    return ((WIDTH - len(s) * CELL_W * scale) // 2 // CELL_W) * CELL_W
