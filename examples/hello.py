"""文字を出すだけの例

    uv run play.py hello

m.tick() が1フレームの区切り。いま描いてある絵を液晶へ出して、
次のフレームまで待って、キーの状態を新しくする。
窓が閉じられると False を返すので、そのときは return する。
"""


def main(m):
    while m.tick():
        m.cls()                       # 前のフレームの絵を消す
        m.text(0, "HELLO PC-1251")    # x=0 から文字を置く
        if m.pressed("BRK"):          # BRK は ESC キー
            return
