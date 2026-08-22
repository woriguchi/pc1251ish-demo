"""走って跳ぶアクション。SPACEか ↑ でジャンプ、長く押すと高く跳ぶ。

一定距離まで走るとゴールの旗が立っている。通ると次の面。
面が上がるごとに速くなる。
"""

import random

from pc1251 import centered

from . import flip

PX = 92          # プレイ領域の右端。その右はスコア
HX = 14          # 自機のxは固定
GY = 6           # 地面のy
HERO_W, HERO_H = 6, 3

HERO_A = [".####.", "######", ".#..#."]
HERO_B = [".####.", "######", "..##.."]
HERO_J = [".####.", "######", "#....#"]
FOE_A = ["#.#.#", "#####"]
FOE_B = [".#.#.", "#####"]
COIN = [".#.", "#.#", ".#."]
# コインの弧。両端は走ったまま拾えるが、真ん中は跳ばないと届かない
COIN_ARC = (2, 1, 0, 1, 2)

ROOF_W = 12      # 天井から下がっている岩。下をくぐる
ROOF_Y = 1.2     # 頭がこれより上がると当たる。1フレームだけの軽い
                 # ジャンプ(頂点1.61)なら通れるが、2フレーム押すと届かない
PIT_DEPTH = 1.0  # 穴にこれだけ落ちたらもう上がれない

# 跳べる高さは3ドットが上限(画面が縦7ドットしかないので)。その範囲で
# 滞空をなるべく長くとると踏み切りの猶予が広がるので、重力を小さくしてある。
GRAVITY = 0.11
JUMP_V = -0.82   # 押しっぱなしで3.48ドット、1フレームだけなら1.39ドット
CUT_V = -0.30    # 途中でボタンを離したときの上昇速度の上限
COYOTE = 3       # 地面を離れてから跳べる猶予フレーム
BUFFER = 4       # 着地前に押した入力を覚えておくフレーム

SPEED_MIN = 1.3
SPEED_MAX = 2.3
SPEED_PER_STAGE = 0.18   # 面が1つ上がるごとに増える速さ

STAGE_LEN = 1600.0       # ゴールまでの距離(ドット)
RUN_IN = 120.0           # ゴール手前は何も置かない。助走のため


class World:
    """地形とアイテム。通し座標wxはゲーム開始からの通算ドット数。"""

    def __init__(self, seed=None):
        self.rnd = random.Random(seed)
        self.items = []          # [kind, wx, param]
        self.next_wx = 190.0

    def extend(self, until):
        """必要なぶんだけ前方を生成する。ゴールの手前では止める。"""
        until = min(until, STAGE_LEN - RUN_IN)
        while self.next_wx < until:
            wx = self.next_wx
            kind = self.rnd.choice(
                ["block", "pit", "foe", "coin", "coin", "roof"])
            if kind == "coin":
                for k, cy in enumerate(COIN_ARC):
                    self.items.append(["coin", wx + k * 8, cy])
                self.next_wx = wx + 32 + self.rnd.randint(54, 72)
            elif kind == "block":
                self.items.append(["block", wx, 0])
                self.next_wx = wx + self.rnd.randint(60, 80)
            elif kind == "pit":
                # 全力で跳べば越えられ、走り抜けようとすると落ちる幅
                self.items.append(["pit", wx, self.rnd.randint(9, 13)])
                self.next_wx = wx + self.rnd.randint(70, 90)
            elif kind == "roof":
                # 地面には何も置かない。ここでは跳ばないのが正解
                self.items.append(["roof", wx, 0])
                self.next_wx = wx + self.rnd.randint(70, 90)
            else:
                self.items.append(["foe", wx, 0])
                self.next_wx = wx + self.rnd.randint(64, 84)

    def forget(self, before):
        self.items = [it for it in self.items if it[1] > before - 20]

    def pit_at(self, wx):
        for it in self.items:
            if it[0] == "pit" and it[1] <= wx < it[1] + it[2]:
                return True
        return False

    def roof_at(self, wx, margin=0):
        for it in self.items:
            if it[1] - margin <= wx < it[1] + ROOF_W + margin \
                    and it[0] == "roof":
                return True
        return False


class Hero:
    FLOOR = float(GY - HERO_H)

    def __init__(self):
        self.y = self.FLOOR
        self.vy = 0.0
        self.on_ground = True
        self.coyote = 0
        self.buffered = 0
        self.fallen = False

    def update(self, jump, over_pit):
        self.buffered = BUFFER if jump and self.buffered <= 0 \
            else self.buffered - 1
        if self.buffered > 0 and (self.on_ground or self.coyote > 0):
            self.vy = JUMP_V
            self.on_ground = False
            self.coyote = 0
            self.buffered = 0
        if not jump and self.vy < CUT_V:
            self.vy = CUT_V

        was_ground = self.on_ground
        self.y += self.vy
        self.vy += GRAVITY
        if self.y >= self.FLOOR:
            if over_pit:
                self.on_ground = False
                # 穴の底までは戻れない。向こう岸に届いても助からない
                if self.y > self.FLOOR + PIT_DEPTH:
                    self.fallen = True
            elif not self.fallen:
                self.y, self.vy, self.on_ground = self.FLOOR, 0.0, True
        self.coyote = COYOTE if was_ground and not self.on_ground \
            else self.coyote - 1

    def sprite(self, frame):
        if not self.on_ground:
            return HERO_J
        return HERO_A if (frame // 3) % 2 else HERO_B


def hits_obstacle(world, scroll, hero):
    """地面の障害物は、足が下から2ドット目まで降りているときだけ当たりにする

    縦7ドットしかないので、矩形どうしで厳密に判定すると跳んだ直後と
    着地直前が理不尽に当たってしまう。天井の岩は逆に、頭が上がりすぎた
    ときだけ当たる。跳ばなければ当たらず、跳びすぎると当たる。
    """
    x0, x1 = scroll + HX, scroll + HX + HERO_W - 1
    if hero.y < ROOF_Y:
        for kind, wx, _ in world.items:
            if kind == "roof" and x1 >= wx and x0 <= wx + ROOF_W - 1:
                return True
    if hero.y + HERO_H - 1 < GY - 1:
        return False
    for kind, wx, _ in world.items:
        if kind in ("block", "foe") and x1 >= wx and x0 <= wx + 4:
            return True
    return False


def take_coins(world, scroll, hero):
    """拾ったコインの得点を返す。判定は矩形ではなく中心間の距離。

    縦は1.5ドットしか許さない。緩くすると、跳ばずに弧の全部が拾えてしまう。
    """
    got = 0
    for it in world.items:
        if it[0] == "coin" and it[2] >= 0:
            if (abs(it[1] - (scroll + HX + 3)) < 5
                    and abs(it[2] - hero.y) < 1.5):
                got += 100 - it[2] * 25      # 高いものほど高得点
                it[2] = -1
    return got


def draw(m, world, scroll, hero, score):
    m.cls()
    for x in range(PX + 1):
        # 遠くの雲。0.32倍で遅く流す。岩の近くには出さない(つながって見える)
        if int(scroll * 0.32 + x) % 41 < 6 and not world.roof_at(scroll + x, 8):
            m.px(x, 0)
    for x in range(PX + 1):
        if not world.pit_at(scroll + x):
            m.px(x, GY)
            if int(scroll + x) % 9 == 0:         # 地面の草
                m.px(x, GY - 1)
    gx = int(STAGE_LEN - scroll)             # ゴールの旗
    if -8 <= gx <= PX:
        m.vline(gx, 1, GY)
        m.box(gx + 1, 1, gx + 5, 2)
        m.px(gx + 6, 2)
    for kind, wx, param in world.items:
        sx = int(wx - scroll)
        if sx < -12 or sx > PX:
            continue
        if kind == "roof":
            # 上2ドットだけ。3ドット目は空けておかないと、くぐる自機と
            # くっついて見えて当たったのか通れたのか分からなくなる
            m.box(sx, 0, sx + ROOF_W - 1, 0)
            m.box(sx + 1, 1, sx + ROOF_W - 2, 1)
        elif kind == "block":
            m.box(sx, GY - 2, sx + 4, GY - 1)
            m.px(sx + 2, GY - 3)
        elif kind == "foe":
            m.sprite(sx, GY - 2, FOE_A if (m.frame // 4) % 2 else FOE_B)
        elif kind == "coin" and param >= 0:
            m.sprite(sx, param, COIN)
    m.sprite(HX, int(round(hero.y)), hero.sprite(m.frame))
    if hero.on_ground and (m.frame // 3) % 2:    # 走ったときの砂けむり
        m.px(HX - 2, GY - 1)
    for y in range(m.HEIGHT):                    # スコアの場所を空ける
        for x in range(PX + 1, m.WIDTH):
            m.px(x, y, False)
    m.text(95, f"{score:05d}")


def title(m):
    for _ in range(400):
        m.cls()
        m.text(0, "JUMP HERO")
        m.text(60, "ESC=END" if flip(m) else "PUSH SPACE")
        if not m.tick():
            return False
        if m.pressed("SPACE") or m.pressed("UP") or m.pressed("ENTER"):
            m.beep(1200, 70)
            return True
        if m.pressed("BRK"):
            return False
    return True


def game_over(m, score, best):
    for f in range(240):
        m.cls()
        if f <= 30:
            m.text(centered("GAME OVER"), "GAME OVER")
        elif flip(m, 60):
            m.text(0, "SPACE=AGAIN")
            m.text(70, "ESC=END")
        else:
            m.text(0, f"SCORE {score:05d}")
            m.text(65, f"HI {best:05d}")
        if not m.tick():
            return False
        if f > 24 and (m.pressed("SPACE") or m.pressed("ENTER")):
            return True
        if m.pressed("BRK"):
            return False
    return True


def play(m, stage, score):
    """1面ぶん走る。得点と、抜けた理由(clear / dead / quit)を返す。"""
    world = World()
    hero = Hero()
    scroll = 0.0
    slow = SPEED_MIN + SPEED_PER_STAGE * stage
    fast = SPEED_MAX + SPEED_PER_STAGE * stage
    speed = slow

    while True:
        m.symbol("BUSY", (m.frame // 5) % 2 == 0)
        world.extend(scroll + 260)
        world.forget(scroll)

        was_ground = hero.on_ground
        hero.update(m.key("SPACE") or m.key("UP"),
                    world.pit_at(scroll + HX + HERO_W // 2))
        if was_ground and not hero.on_ground and hero.vy < 0:
            m.beep(1440, 32, 0.35)
        got = take_coins(world, scroll, hero)
        if got:
            m.beep(2400, 26, 0.4)
        score += got
        dead = hero.fallen or hits_obstacle(world, scroll, hero)

        scroll += speed
        speed = min(fast, slow + scroll / 3000.0)
        score += 1
        if scroll + HX >= STAGE_LEN:
            draw(m, world, scroll, hero, score)
            if not m.tick():
                return score, "quit"
            return score, "clear"

        draw(m, world, scroll, hero, score)
        if dead:
            m.beep(180, 420, 0.6)
            for _ in range(6 if hero.fallen else 0):
                # 穴に落ちたときは、画面から沈んでいくところまで見せる
                hero.y += hero.vy
                hero.vy += GRAVITY
                draw(m, world, scroll, hero, score)
                if not m.tick():
                    return score, "quit"
            for _ in range(6):
                m.invert()
                if not m.tick():
                    return score, "quit"
            return score, "dead"
        if not m.tick():
            return score, "quit"
        if m.pressed("BRK"):
            return score, "quit"


def stage_clear(m, stage, score):
    """旗を通ったときの間。次の面の番号を出す。"""
    for f in range(96):
        m.cls()
        if f < 48:
            m.text(centered("STAGE CLEAR"), "STAGE CLEAR")
        else:
            m.text(centered(f"STAGE {stage + 1}"), f"STAGE {stage + 1}")
        if f in (0, 8, 16):
            m.beep(1400 + f * 90, 70, 0.45)
        if not m.tick():
            return False
        if m.pressed("BRK"):
            return False
    return True


def run(m):
    """面をつないで1ゲームぶん。得点と、続けてよいかを返す。"""
    score = 0
    stage = 0
    while True:
        score, why = play(m, stage, score)
        if why == "quit":
            return score, False
        if why == "dead":
            return score, True
        score += 500 + stage * 250
        stage += 1
        if not stage_clear(m, stage, score):
            return score, False


def main(m):
    if not title(m):
        return
    best = 0
    while True:
        score, alive = run(m)
        if not alive:
            return
        best = max(best, score)
        if not game_over(m, score, best):
            return
