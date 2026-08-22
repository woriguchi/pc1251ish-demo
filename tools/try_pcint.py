"""PC-インタープリタを自動操作して、動きを確かめるツール

    uv run tools/try_pcint.py jump

キーは人の代わりの関数が押す。画面は毎フレーム文字に起こして、
最後の1枚と、途中の1枚を表示する。試すためだけのツールなので
ここではpygameを使っている。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from pc1251 import Machine                       # noqa: E402
from programs.pcint import interp                # noqa: E402


class Auto(Machine):
    def __init__(self, limit=600):
        super().__init__(audio=False, persist=0.0)
        self.want = set()
        self.limit = limit
        self.n = 0
        self.pilot = lambda: set()
        self.shots = []

    def key(self, name):
        return name in self.want

    def pressed(self, name):
        return name in self.want

    def any_pressed(self):
        return bool(self.want)

    def tick(self):
        self.want = self.pilot()
        self.n += 1
        self.frame += 1
        self.shots.append(dump(self))
        return self.n < self.limit


def dump(m):
    rows = []
    for y in range(m.HEIGHT):
        rows.append("".join("#" if m.get(x, y) else "." for x in range(120)))
    return rows


def show(shot, tag=""):
    print(f"--- {tag}")
    for r in shot:
        print(r)


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "jump"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 600
    prog = [p for p in interp.programs() if p.name == name][0]
    m = Auto(limit)
    machine = interp.Interp(m, prog, seed=1)

    var_o = interp.VAR_BASE + ord("O") - 65
    var_j = interp.VAR_BASE + ord("J") - 65

    def pilot():
        # jump用。棒の位置Oと跳んでいるかJを覗いて、跳ぶところでSPCを押す
        o, j = machine.mem[var_o], machine.mem[var_j]
        return {"SPACE"} if 0x0E < o <= 0x1A and j == 0 else set()

    m.pilot = pilot
    why, code, line = machine.run()
    print(f"{name}: {why} code={code} line={line} frames={m.n}")
    print("Z(得点) =", machine.peek(0xC69F), " T,U =",
          machine.peek(0xC699), machine.peek(0xC69A))
    if m.shots:
        show(m.shots[len(m.shots) // 3], "途中")
        show(m.shots[-1], "最後")
    m.close()


if __name__ == "__main__":
    main()
