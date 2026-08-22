"""景色が右から左へ流れるだけ。

    uv run play.py scroll

絵をずらすのではなく、コースのどこを見ているかを数で持って、
毎フレーム描き直す。地形は配列で持たず、そのつど計算する。

流す量を減らすと遠くに見える。雲は0.3倍で流している。
"""

SPEED = 1.2         # 1フレームに何ドット流すか


def main(m):
    scroll = 0.0    # コースのどこを見ているか(ドット)

    while m.tick():
        if m.pressed("BRK"):
            return
        scroll += SPEED

        m.cls()
        for x in range(m.WIDTH):
            wx = int(scroll + x)            # 画面のx を 通し座標wx に直す
            m.px(x, 6)                      # 地面
            if wx % 23 == 0:                # 23ドットおきに木
                m.vline(x, 3, 5)
            elif wx % 23 == 1:
                m.px(x, 3)
            if int(scroll * 0.3 + x) % 31 < 5:   # 遠くの雲。ゆっくり流す
                m.px(x, 0)
