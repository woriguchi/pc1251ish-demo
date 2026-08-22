"""PC-インタープリタで書いたプログラムを選んで動かす

    uv run play.py pcint

progs/ にある.pciを左右で選び、SPACEで実行する。文法は「PC-インタープリタ」
(工学社「PiO」1986年8月号 169〜171ページ、Fan_PC-1251 氏)のもの。
処理系の中身はinterp.pyにある。

オリジナルのサンプルは末尾にBASICの行があって、CALL &C300 で呼んで戻ってきたら
PEEK で得点を表示していた。その役はこのファイルが受け持つ。どの番地を読むかは
.pciの先頭に #SCORE で書いておく。
"""

from . import interp

TITLE_X = 10
HINT_X = 75


def run(m, prog):
    """1本走らせて、終わりかたを表示する。続けてよければTrue"""
    machine = interp.Interp(m, prog)
    why, code, line = machine.run()
    if why == "QUIT":
        return False
    if why == "ERROR":
        msg = f"ERROR {code} IN {line}"
    elif why == "BREAK":
        msg = "BREAK"
    elif prog.score:
        v = 0
        for a in prog.score:
            v = v * 100 + machine.peek(a)
        msg = f"SCORE {v}"
    else:
        msg = "END"
    m.cls()
    m.text(0, msg)
    for _ in range(120):
        if not m.tick():
            return False
        if m.any_pressed():
            break
    return True


def main(m):
    progs = interp.programs()
    if not progs:
        m.cls()
        m.text(0, "NO PROGRAM")
        m.wait(48)
        return
    sel = 0
    while True:
        m.cls()
        m.text(TITLE_X, progs[sel].title)
        m.text(HINT_X, "ESC=END")
        m.text(0, "<")
        m.text(115, ">")
        if not m.tick():
            return
        if m.pressed("LEFT"):
            sel = (sel - 1) % len(progs)
            m.beep(1800, 22, 0.3)
        if m.pressed("RIGHT"):
            sel = (sel + 1) % len(progs)
            m.beep(1800, 22, 0.3)
        if m.pressed("SPACE") or m.pressed("ENTER"):
            m.flush_keys()
            if not run(m, progs[sel]):
                return
            m.flush_keys()
        if m.pressed("BRK"):
            return
