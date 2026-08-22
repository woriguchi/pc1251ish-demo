"""落ちてくる荷物を受けるだけのゲーム。3回落とすと終わり。

    uv run play.py catch

当たり判定と得点の見本。当たったかどうかは、四角どうしの重なりではなく
中心の距離で見ている。そのほうが1ドットのずれで外れることがなく、
受けたつもりのものがちゃんと受けられる。

落ちてくるのは左の60ドットのなか。画面のどこにでも落ちてくると、
端から端まで走っても間に合わない。落ちる時間と受け皿の速さから、
届く幅を決めてある。
"""

import random

CART = ["#...#", "#####"]      # 受け皿。5x2ドット
PX = 59                        # 落ちてくる範囲の右端。ここから右は得点
FALL = 0.22                    # 落ちる速さ(ドット/フレーム)
CART_SPEED = 3.0               # 受け皿の速さ
RATE = 0.02                    # 1フレームに荷物が降ってくる割合。0.5個/秒
# y=0からy=5まで 5/FALL = 23フレーム。そのあいだに受け皿は
# 23*3 = 69ドット動けるので、PX=59 の端から端まで間に合う。


def main(m):
    rnd = random.Random()
    cart = 40.0
    items = []                 # 落ちてくるもの [x, y]
    score = 0
    miss = 0

    while m.tick():
        if m.pressed("BRK"):
            return
        if m.key("LEFT"):
            cart -= CART_SPEED
        if m.key("RIGHT"):
            cart += CART_SPEED
        cart = max(0.0, min(PX - 5.0, cart))

        if rnd.random() < RATE:
            items.append([rnd.uniform(0, PX - 1), 0.0])
        for it in items:
            it[1] += FALL

        for it in list(items):
            if it[1] < 5.0:                       # まだ受け皿の高さではない
                continue
            if abs(it[0] - (cart + 2)) < 4:       # 中心どうしの距離で判定
                score += 10
                m.beep(2400, 25, 0.4)
            else:
                miss += 1
                m.beep(300, 120, 0.4)
            items.remove(it)

        m.cls()
        for it in items:
            m.px(int(it[0]), int(it[1]))
        m.sprite(int(cart), 5, CART)
        for y in range(m.HEIGHT):                 # 得点の場所を空ける
            for x in range(PX + 1, m.WIDTH):
                m.px(x, y, False)
        m.text(65, f"MISS{miss} {min(score, 9999):04d}")

        if miss >= 3:
            m.beep(180, 400, 0.6)
            m.wait(24)
            return
