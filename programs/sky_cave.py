"""洞窟を進む横スクロールシューティング。↑↓ で移動、SPACEで撃つ。

自機は3機。やられても同じところから出直す。出直した直後は少しのあいだ
当たらない(自機が点滅している)。ボスに与えた傷はそのまま残る。

洞窟は縦24ドットの仮想画面に描いてあり、画面(縦7ドット)はその一部。
通路の高さは6ドットから12ドットまで変わる。広いところは画面に収まらないので、
カメラが自機を追って上下し、天井や床が窓の外へ出入りする。
狭いところでは通路が画面より低くなり、天井と床が同時に見える。

しばらく進むと洞窟が開けてボスが出る。ボスは縦15ドットあって一度には見えない。
装甲に撃っても弾が消えるだけで、当たるのは中央の砲口の奥にある核だけ。
自機の高さを核に合わせて撃ち込む。倒すと次の面。
"""

import math
import random

from pc1251 import Buffer, centered

from . import flip

WH = 24          # 仮想画面の高さ
PX = 84          # プレイ領域の右端。その右はスコア
SHIP_X = 3
LIVES = 3        # 残機。やられても洞窟の同じところから出直す
INVUL = 48       # 出直した直後、これだけのあいだは当たらない

SHIP = ["##...", "#####", "##..."]
ENEMY_A = [".#.", "###", ".#."]
ENEMY_B = ["#.#", ".#.", "#.#"]

SPEED_MIN = 1.0
SPEED_MAX = 1.9
SPEED_PER_STAGE = 0.12
SHIP_VY = 1.0
FIRE_WAIT = 4
ENEMY_RATE = 0.045

# ここから下の数字はてきとう。自動操縦で何度か回して、面5まで通したときに
# 上手い人が30秒前後で倒せて、半分くらいは無傷、というあたりで止めた。
STAGE_LEN = 2200.0   # ここまで進むとボス房
OPEN = 220.0         # 手前でこのぶんかけて洞窟が開ける

BOSS_X = 52          # ボスの左端
BOSS_W, BOSS_H = 26, 15
CORE_DX, CORE_DY = 13, 7    # ボスの左上から見た核の位置
BOSS_HP = 20
BOSS_FIRE = 30       # 何フレームおきに撃ってくるか
HOMING = 0.20        # 弾が自機の高さへ寄る速さ。避けられる程度に弱く
SHUT_CYCLE = 96      # 砲口が開いて閉じるまで
SHUT_OPEN = 40       # そのうち開いているフレーム数


def path(wx):
    """通路の中心

    傾きの上限は、自機の少し先が見えるかどうかで決まる。0.055だと30ドット
    先で1.7ドットずれる程度なので、反応できる範囲に収まる。
    """
    return 11.5 + 4.0 * math.sin(wx * 0.0095) + 1.4 * math.sin(wx * 0.0125)


def half(wx):
    """通路の半幅。広いところは画面(縦7ドット)の倍近くまで開く。"""
    return 4.0 + 1.8 * math.sin(wx * 0.0061 + 2.0)


def spikes(wx):
    """通路のなかへ突き出す岩。天井からと床から交互に生える。"""
    s = wx % 240
    if 30 <= s < 54:
        return max(0, 7 - abs(int(s) - 42)) // 2, 0
    if 150 <= s < 174:
        return 0, max(0, 7 - abs(int(s) - 162)) // 2
    return 0, 0


MIN_GAP = 6.0    # 自機が3ドットなので、上下に1ドットずつは余らせる


def ceil_floor(wx):
    """その列で空いているyの範囲(天井の下端, 床の上端)

    ボス房が近づくと、洞窟がだんだん開けて仮想画面いっぱいの広さになる。
    """
    if wx > STAGE_LEN:
        return 1, WH - 2
    c, hg = path(wx), half(wx)
    t, b = c - hg, c + hg
    down, up = spikes(wx)
    room = (b - t) - MIN_GAP        # 岩は余裕のあるところにだけ伸ばす
    if room > 0:
        t += min(down, room * 0.5)
        b -= min(up, room * 0.5)
    if wx > STAGE_LEN - OPEN:
        k = (wx - (STAGE_LEN - OPEN)) / OPEN
        t += (1.0 - t) * k
        b += (WH - 2.0 - b) * k
    t, b = max(1.0, t), min(WH - 2.0, b)
    if b - t < MIN_GAP - 1:
        mid = (t + b) / 2
        t = max(1.0, min(mid - (MIN_GAP - 1) / 2, WH - 1.0 - MIN_GAP))
        b = t + MIN_GAP - 1
    return int(round(t)), int(round(b))


def draw_cave(cv, scroll):
    for x in range(PX + 1):
        t, b = ceil_floor(scroll + x)
        for y in range(0, max(0, t)):
            if y >= t - 2 or (x + y) % 2 == 0:   # 通路際は密、奥は市松
                cv.px(x, y)
        for y in range(min(WH - 1, b) + 1, WH):
            if y <= b + 3 or (x + y) % 2 == 0:
                cv.px(x, y)
    for x in range(PX + 1):                      # 奥の層。手前より遅く流れる
        if int(scroll * 0.45 + x) % 21 == 0:
            t, b = ceil_floor(scroll + x)
            for y in range(t + 1, b):
                if y % 2 == 0:
                    cv.px(x, y)


def crashed(scroll, sy):
    """壁に1ドット食い込むまでは当たりにしない"""
    for i in range(5):
        t, b = ceil_floor(scroll + SHIP_X + i)
        if sy - 1 < t - 1 or sy + 1 > b + 1:
            return True
    return False


class Boss:
    """洞窟の主。全高15ドットあるので縦7ドットの窓には一度に入らない。

    装甲はどこを撃っても弾を吸うだけ。左の中央に砲口が開いていて、
    その高さに自機を合わせて撃つと、奥の核まで弾が届く。
    """

    def __init__(self, stage):
        self.hp = self.max_hp = BOSS_HP + stage * 6
        self.x = float(PX + 10)
        self.y = 4.0                 # 上端
        self.t = 0.0
        self.phase = 0
        self.hit = -99
        self.fire = BOSS_FIRE

    def core(self):
        return self.x + CORE_DX, self.y + CORE_DY

    def arrived(self):
        return self.x <= BOSS_X

    def open_now(self):
        """砲口が開いているか。閉じているあいだは核に届かない。"""
        return self.arrived() and self.phase % SHUT_CYCLE < SHUT_OPEN

    def update(self, frame):
        self.x = max(float(BOSS_X), self.x - 1.4)
        if self.arrived():
            self.phase += 1
        self.t += 0.030 + 0.010 * (1.0 - self.hp / self.max_hp)
        self.y = 4.5 + 3.5 * math.sin(self.t)
        self.fire -= 1

    def zone(self, bx, by):
        """弾がどこに当たったか。core / armor / None(素通り)。"""
        if not (self.x - 1 <= bx <= self.x + BOSS_W
                and self.y <= by <= self.y + BOSS_H - 1):
            return None
        cx, cy = self.core()
        if abs(by - cy) <= 1.2:
            if not self.open_now():
                return "armor" if bx >= cx - 8 else None
            return "core" if bx >= cx - 3 else None
        return "armor"


def diamond(cv, cx, cy, r):
    # 丸は縦7ドットだと丸に見えないので、菱形にしている
    for dy in range(-r, r + 1):
        dx = r - abs(dy)
        cv.hline(cx - dx, cx + dx, cy + dy)


def draw_boss(cv, boss, frame):
    bx, by = int(round(boss.x)), int(round(boss.y))
    if frame - boss.hit < 3:                 # 当たった瞬間は塗りつぶす
        cv.box(bx, by, bx + BOSS_W - 1, by + BOSS_H - 1)
        return
    right = bx + BOSS_W - 1
    cv.box(bx + 6, by, right, by + 1)        # 上の甲
    cv.box(bx + 6, by + BOSS_H - 2, right, by + BOSS_H - 1)   # 下の甲
    cv.vline(right, by, by + BOSS_H - 1)     # 背
    cv.vline(bx + 6, by + 2, by + 5)         # 前面。砲口の高さだけ開ける
    cv.vline(bx + 6, by + 9, by + 12)
    cv.hline(bx + 6, right, by + 5)
    cv.hline(bx + 6, right, by + 9)
    for k in range(2):                       # 上下の腕。ここから撃ってくる
        y = by + 2 + k * 8
        cv.box(bx, y, bx + 6, y + 2)
        cv.hline(bx, bx + 2, y + 1, False)   # 砲身のくぼみ
    # 装甲のリブ。減るほど抜けていって、残りが体で分かる
    ribs = 1 + boss.hp * 4 // boss.max_hp
    for i in range(4):
        if i >= ribs:
            continue
        x = bx + 10 + i * 4
        cv.vline(x, by + 2, by + 4)
        cv.vline(x, by + 10, by + 12)
    if boss.open_now():                      # 砲口が開いているあいだだけ
        cv.vline(bx + 6, by + 6, by + 8, False)
        cv.hline(bx + 7, bx + CORE_DX - 4, by + 6)
        cv.hline(bx + 7, bx + CORE_DX - 4, by + 8)
        rate = 3 if boss.hp * 3 <= boss.max_hp else 6
        diamond(cv, bx + CORE_DX, by + CORE_DY,
                2 if (frame // rate) % 2 else 1)
    else:
        cv.box(bx + 6, by + 6, bx + CORE_DX - 3, by + 8)


def title(m):
    for _ in range(400):
        m.cls()
        m.text(0, "SKY CAVE")
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
            m.text(0, f"SCORE {score:06d}")
            m.text(70, f"HI {best:06d}")
        if not m.tick():
            return False
        if f > 24 and (m.pressed("SPACE") or m.pressed("ENTER")):
            return True
        if m.pressed("BRK"):
            return False
    return True


def blow_up(m, cv, boss, scroll, cam):
    """ボスが崩れるところ。核から順に穴が開いていく。"""
    bx, by = int(round(boss.x)), int(round(boss.y))
    for f in range(40):
        if f % 7 == 0:
            m.beep(600 - f * 10, 90, 0.55)
        cv.cls()
        draw_cave(cv, scroll)
        if f < 34:
            draw_boss(cv, boss, 0)
            r = f // 2
            for dy in range(-r, r + 1):     # 崩れた部分を消していく
                dx = r - abs(dy)
                cv.hline(bx + CORE_DX - dx, bx + CORE_DX + dx,
                         by + CORE_DY + dy, False)
        m.show(cv, round(cam))
        for y in range(m.HEIGHT):
            for x in range(PX + 1, m.WIDTH):
                m.px(x, y, False)
        if not m.tick():
            return False
    return True


def stage_clear(m, stage, score):
    for f in range(96):
        m.cls()
        if f < 48:
            m.text(centered("STAGE CLEAR"), "STAGE CLEAR")
        else:
            m.text(0, f"SCORE {score:06d}")
            m.text(70, f"NEXT {stage + 1}")
        if f in (0, 8, 16):
            m.beep(1400 + f * 90, 70, 0.45)
        if not m.tick():
            return False
        if m.pressed("BRK"):
            return False
    return True


def play(m, stage, score, lives):
    """1面ぶん。得点・残機・抜けた理由(clear / dead / quit)を返す。"""
    cv = Buffer(WH)
    rnd = random.Random()
    scroll = 0.0
    slow = SPEED_MIN + SPEED_PER_STAGE * stage
    fast = SPEED_MAX + SPEED_PER_STAGE * stage
    speed = slow
    sy = 11.5
    cam = 8.5
    bullets, enemies, booms, shots = [], [], [], []
    boss = None
    wait = 0
    invul = 0

    while True:
        invul = max(0, invul - 1)
        m.symbol("BUSY", (m.frame // 5) % 2 == 0)
        if m.key("UP"):
            sy -= SHIP_VY
        if m.key("DOWN"):
            sy += SHIP_VY
        sy = max(1.0, min(WH - 2.0, sy))
        syi = int(round(sy))
        wait = max(0, wait - 1)
        if m.key("SPACE") and wait == 0:
            bullets.append([SHIP_X + 6, syi])
            wait = FIRE_WAIT
            m.beep(3600, 14, 0.22)

        scroll += speed
        speed = min(fast, slow + scroll / 4000.0)
        score += 1
        if boss is None and scroll >= STAGE_LEN:
            boss = Boss(stage)
            enemies.clear()
        if boss is not None:
            boss.update(m.frame)
            if boss.arrived() and boss.fire <= 0:
                boss.fire = max(20, BOSS_FIRE - stage * 2)
                # 上下の腕から交互に。2門同時だと避け場所が無くなる
                ay = boss.y + (2 if (boss.phase // 60) % 2 else 12)
                # 撃った時点の自機の高さへ寄ってくる。核の前に居座らせない
                vy = max(-HOMING, min(HOMING, (sy - ay) / 60.0))
                shots.append([boss.x, ay, vy])
                m.beep(480, 40, 0.35)
            for sh in shots:
                sh[0] -= 2.4
                sh[1] += sh[2]
            shots = [sh for sh in shots if sh[0] > -2]
        elif m.frame > 40 and rnd.random() < ENEMY_RATE:
            enemies.append({"x": PX + 3.0,
                            "y": path(scroll + PX)
                                 + rnd.uniform(-1, 1) * (half(scroll + PX) - 1.5),
                            "ph": rnd.uniform(0, 6),
                            "sp": rnd.choice([ENEMY_A, ENEMY_B])})
        for b in bullets:
            b[0] += 4
        bullets = [b for b in bullets if b[0] <= PX]
        for e in enemies:
            e["x"] -= 1.1 + speed * 0.2
            e["y"] += 0.22 * math.sin(m.frame * 0.14 + e["ph"])
        enemies = [e for e in enemies if e["x"] > -4]

        dead = crashed(scroll, syi) and invul == 0
        if boss is not None:
            for b in list(bullets):
                z = boss.zone(b[0], b[1])
                if z is None:
                    continue
                bullets.remove(b)
                if z == "armor":
                    m.beep(300, 18, 0.25)    # 装甲は弾を吸うだけ
                    continue
                boss.hp -= 1
                boss.hit = m.frame
                score += 200
                m.beep(900, 40, 0.5)
            for sh in list(shots):
                if (invul == 0 and abs(sh[0] - SHIP_X - 2) <= 2
                        and abs(sh[1] - sy) <= 1.2):
                    dead = True
        for e in list(enemies):
            ex, ey = int(e["x"]), int(round(e["y"]))
            for b in list(bullets):
                if abs(b[0] - (ex + 1)) <= 2 and abs(b[1] - ey) <= 1:
                    booms.append([ex + 1, ey, 0])
                    bullets.remove(b)
                    enemies.remove(e)
                    score += 300
                    m.beep(720, 55, 0.45)
                    break
            else:
                # 撃ち落とした敵は上でbreakしているのでここへ来ない
                if (invul == 0 and abs(ex - SHIP_X - 2) <= 2
                        and abs(ey - syi) <= 1):
                    dead = True

        cv.cls()
        draw_cave(cv, scroll)
        if boss is not None:
            draw_boss(cv, boss, m.frame)
            for sh in shots:
                cv.px(int(sh[0]), int(round(sh[1])))
                cv.px(int(sh[0]) + 1, int(round(sh[1])))
        for e in enemies:
            cv.sprite(int(e["x"]), int(round(e["y"])) - 1, e["sp"])
        if invul == 0 or (m.frame // 3) % 2 == 0:
            cv.sprite(SHIP_X, syi - 1, SHIP)
            if m.frame % 2 == 0:
                cv.px(SHIP_X - 1, syi)
        for b in bullets:
            cv.px(b[0], b[1])
            cv.px(b[0] - 1, b[1])
        for bo in list(booms):
            r = bo[2]
            for dy in range(-r, r + 1):
                dx = r - abs(dy)
                for x in (bo[0] - dx, bo[0] + dx):
                    if 0 <= x <= PX:
                        cv.px(x, bo[1] + dy)
            bo[2] += 1
            if bo[2] > 3:
                booms.remove(bo)

        # カメラは自機を追う。通路が画面より高いところでは天井や床が窓の
        # 外へ出るが、そのぶん上下に飛べる幅が実際に広い。
        cam += (max(0.0, min(WH - m.HEIGHT, sy - 3.0)) - cam) * 0.22
        m.show(cv, round(cam))
        for y in range(m.HEIGHT):
            for x in range(PX + 1, m.WIDTH):
                m.px(x, y, False)
        for i in range(lives):                 # 残機。上から減っていく
            m.hline(86, 87, 5 - i * 2)
        if boss is None:
            m.text(90, f"{score:06d}")
        else:
            # 戦っているあいだは残りが知りたい。得点は倒したあとで見る
            m.text(90, f"HP{max(0, boss.hp):02d}")

        if boss is not None and boss.hp <= 0:
            if not blow_up(m, cv, boss, scroll, cam):
                return score, lives, "quit"
            return score + 1000 + stage * 500, lives, "clear"
        if dead:
            lives -= 1
            m.beep(150, 420, 0.6)
            for _ in range(6):
                m.invert()
                if not m.tick():
                    return score, lives, "quit"
            if lives <= 0:
                return score, lives, "dead"
            # ボスに与えた傷はそのまま。通路の真ん中から出直す
            t0, b0 = ceil_floor(scroll + SHIP_X)
            sy = (t0 + b0) / 2.0
            bullets.clear()
            enemies.clear()
            shots.clear()
            booms.clear()
            invul = INVUL
        if not m.tick():
            return score, lives, "quit"
        if m.pressed("BRK"):
            return score, lives, "quit"


def run(m):
    """面をつないで1ゲームぶん。得点と、続けてよいかを返す。"""
    score = 0
    stage = 0
    lives = LIVES
    while True:
        score, lives, why = play(m, stage, score, lives)
        if why == "quit":
            return score, False
        if why == "dead":
            return score, True
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
