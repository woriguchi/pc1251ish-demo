"""文字の出し方いろいろ。SPACEで次の画面へ。

    uv run play.py text

画面は5x7ドットの文字セルが24個ならんだ1行。セルとセルのあいだには1ドットの
すきまがあり、そこには何も書けない。文字を置くxは5の倍数にしておくと
セルにそろう。半端なxに置くと、文字がすきまで切られて汚くなる。
"""

from pc1251 import centered


def wait(m, frames=999):
    """SPACEが押されるまで、いま描いてある絵のまま待つ"""
    for _ in range(frames):
        if not m.tick():
            return False
        if m.pressed("SPACE") or m.pressed("ENTER"):
            return True
        if m.pressed("BRK"):
            return False
    return True


def main(m):
    # 1) 文字セルにそろえる / そろえない
    m.cls()
    m.text(0, "X=0 SOROU")        # 5の倍数。セルにきれいに入る
    m.text(52, "X=52 ZURERU")     # 半端な位置。すきまで切られる
    if not wait(m):
        return

    # 2) 中央ぞろえと右ぞろえ
    m.cls()
    s = "CENTER"
    m.text(centered(s), s)        # centered() が中央のxを返す
    if not wait(m):
        return

    m.cls()
    n = 1234
    m.text(m.WIDTH - 5 * len(f"{n}"), f"{n}")   # 右端にそろえる
    m.text(0, "MIGI ZOROE")
    if not wait(m):
        return

    # 3) 文字セルで位置を決める。cell_text は0..23のセル番号で置く
    m.cls()
    for cell in range(0, 24, 4):
        m.cell_text(cell, f"{cell:02d}")
    if not wait(m):
        return

    # 4) 電光掲示板。文字は動かさず、置くxを毎フレームずらすだけ
    msg = "THIS IS A 24 COLUMN DISPLAY.   "
    width = len(msg) * 5
    x = float(m.WIDTH)
    while True:
        m.cls()
        m.text(int(x), msg)
        m.text(int(x) + width, msg)    # 2枚つなげて、切れ目を無くす
        x -= 1.0
        if x <= -width:
            x += width
        if not m.tick():
            return
        if m.pressed("BRK") or m.pressed("SPACE"):
            return
