"""ランチャー。1行しかないので、左右の矢印で1本ずつ見せる。"""

from . import character, jump_hero, pcint, side_break, sky_cave

TITLES = [
    ("1 SKY CAVE", sky_cave),
    ("2 JUMP HERO", jump_hero),
    ("3 SIDE BREAK", side_break),
    ("4 CHARACTER", character),
    ("5 PC-INT", pcint),
]

# 題名は左詰め。いちばん長い「3 SIDE BREAK」でも12文字=60ドットなので、
# 10..69 に収まる。案内はその右の 75 から。題名は常に出しておく。
TITLE_X = 10
HINT_X = 75


def main(m):
    sel = 0
    while True:
        m.symbol("BUSY", False)
        title, mod = TITLES[sel]
        m.cls()
        m.text(TITLE_X, title)
        m.text(HINT_X, "ESC=END")
        m.text(0, "<")
        m.text(115, ">")
        if not m.tick():
            return
        if m.pressed("LEFT"):
            sel = (sel - 1) % len(TITLES)
            m.beep(1800, 22, 0.3)
        if m.pressed("RIGHT"):
            sel = (sel + 1) % len(TITLES)
            m.beep(1800, 22, 0.3)
        for i, key in enumerate("12345"):
            if m.pressed(key) and i < len(TITLES):
                sel = i
        if m.pressed("SPACE") or m.pressed("ENTER"):
            mod.main(m)
            # ゲームを終わらせたESCをメニューがそのまま読まないよう捨てる
            m.flush_keys()
            continue
        if m.pressed("BRK") or m.pressed("Q"):
            return
