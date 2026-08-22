"""起動用。マシンを1台立ち上げて、その上でプログラムを走らせる。

    uv run play.py               メニューから選ぶ
    uv run play.py sky_cave      直接その1本を動かす
    uv run play.py --scale 0.7   ウィンドウを小さくする(2.0 で大きくもできる)
    uv run play.py --mute        音を鳴らさない
    uv run play.py --persist 0   残像を切る([ ]キーで動かしても変えられる)
    uv run play.py car           examples/ の入門用の例も同じように動く
    uv run play.py pcint         PC-インタープリタの文法で書いたものを動かす
"""

import argparse
import importlib

from pc1251 import Machine

PACKAGES = ("programs", "examples")


def find(name):
    """programs/ を先に見て、無ければ examples/ から探す"""
    for pkg in PACKAGES:
        try:
            return importlib.import_module(f"{pkg}.{name}")
        except ModuleNotFoundError as e:
            if e.name != f"{pkg}.{name}":   # 中のimportが失敗したのなら通す
                raise
    raise SystemExit(f"{name} は programs/ にも examples/ にも無い")


def build_parser():
    p = argparse.ArgumentParser(description="SHARP PC-1251 game collection")
    p.add_argument("program", nargs="?", default="menu",
                   help="programs/ か examples/ の中のモジュール名")
    p.add_argument("--scale", type=float, default=1.0,
                   help="ウィンドウの拡大率(既定1.0)。デスクトップに"
                        "入らないときは自動で下げる")
    p.add_argument("--mute", action="store_true",
                   help="ブザーを鳴らさない")
    p.add_argument("--persist", type=float, default=1.0,
                   help="残像の強さ。0で切る、1.0が実測どおり(既定1.0)")
    return p


def main():
    args = build_parser().parse_args()
    prog = find(args.program)
    m = Machine(scale=args.scale, audio=not args.mute,
                persist=args.persist)
    if m.scale < args.scale - 0.01:
        print(f"デスクトップに入らないので拡大率は {m.scale:.2f} にした")
    try:
        prog.main(m)
    finally:
        m.close()


if __name__ == "__main__":
    main()
