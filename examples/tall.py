"""画面より大きい仮想画面を、↑↓で動かす窓から見る。

    uv run play.py tall

Buffer は好きな高さで作れる。これを仮想画面と呼ぶ。そこへ大きい絵を
描いておいて、m.show(buf, top) で縦7ドットぶんを切り取って画面に写す。
top が切り取る位置。絵は最初に1回描くだけで、あとは top を変えていく。
"""

from pc1251 import Buffer

WH = 30             # 仮想画面の高さ(ドット)
SPEED = 0.5         # 窓を動かす速さ。1ドット/フレームだと残像で潰れる


def build(vscr):
    """仮想画面に塔を1回だけ描く"""
    vscr.cls()
    vscr.outline(10, 0, 44, WH - 1)
    for y in range(3, WH - 3, 4):        # 階
        vscr.hline(11, 43, y)
    for y in range(3, WH - 3, 4):        # 窓
        vscr.px(20, y - 1, False)
        vscr.px(34, y - 1, False)
    vscr.text(50, "TOP", 0)
    vscr.text(50, "SHITA", WH - 7)


def main(m):
    vscr = Buffer(WH)
    build(vscr)
    top = 0.0           # 仮想画面のどこを切り取っているか

    while m.tick():
        if m.pressed("BRK"):
            return
        if m.key("UP"):
            top -= SPEED
        if m.key("DOWN"):
            top += SPEED
        top = max(0.0, min(WH - m.HEIGHT, top))   # 仮想画面の外は見ない

        m.cls()
        m.show(vscr, int(round(top)))
