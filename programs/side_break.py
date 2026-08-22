"""横向きのブロック崩し。↑↓でパドル、SPACEで打ち出す。

画面が縦7ドットしかないので、縦に積むのではなく横に寝かせてある。
左端のパドルで玉を打ち返し、右のブロック壁を削る。壁と右端のあいだは
空いていて、そこへ回り込ませると壁を裏から削れる。
点滅しているブロックを壊すと玉が増える。

壁はゆっくり左へ寄ってくる。手前の列を崩すと壁の先端が奥へ下がるので、
そのぶん時間が稼げる。押し切られると玉を1個失う。
"""

import random

from pc1251 import centered

from . import flip

PX = 89          # プレイ領域の右端。その右は得点
PAD_X = 1        # パドルの列
PAD_H = 2        # パドルの高さ。縦7ドットのうち2ドットしか守れない
PAD_V = 0.5      # パドルの速さ(ドット/フレーム)

# ブロックは5ドット間隔で並べ、絵は4ドットだけ描く。残る1ドットが目地。
# 文字セルの境目のすきまを目地に使う手もあるが、壁は左へ寄っていくので
# 境目とブロックの切れ目がずれて、そのうち全部つながって見える。
PITCH = 5
BRICK_W = 4      # 当たり判定は5ドットぶん。目地に玉は入らない
COLS, ROWS = 6, 7
BX = 50          # 壁の初期位置。右端は BX+PITCH*COLS-1 = 79
ADVANCE = 0.025  # 壁が左へ寄る速さ。0.6ドット/秒
DANGER = 12      # 壁の先端がここまで来ると押し切られる

SPEED0 = 2.1     # 玉の横方向の速さ
SPEED_UP = 0.09  # 1面ごとに上がるぶん
SPEED_MAX = 2.6  # これ以上速いとパドルの判定をすり抜ける
VY_MAX = 0.42    # 縦7ドットしかないので控えめに
MIN_VY = 0.26    # 真横に近いと同じ段だけ削って他の段に届かなくなる
SPIN = 0.55      # パドルを動かしながら当てたときにつく角度
# 縦7ドットだと跳ね返りがすぐ周期に入り、同じ段だけを往復して
# 最後の数個が残る。MIN_VY と SPIN で角度を、ADVANCE で壁の位置を動かす。
MAX_BALLS = 4
SPECIALS = 3     # 玉が増えるブロックの数

BALLS_AT_START = 3


class Ball:
    def __init__(self, x, y, vx, vy):
        self.x, self.y = x, y
        self.vx, self.vy = vx, vy


class Wall:
    """ブロックの生死と、壁ぜんたいの位置"""

    def __init__(self, rnd):
        self.alive = [[True] * COLS for _ in range(ROWS)]
        self.special = set()
        while len(self.special) < SPECIALS:
            self.special.add((rnd.randrange(ROWS), rnd.randrange(COLS)))
        self.left = COLS * ROWS
        self.x = float(BX)

    def at(self, x, y):
        """そのドットにあるブロックの (row, col)。無ければ None。"""
        r = int(round(y))
        if not 0 <= r < ROWS:
            return None
        c = int((x - self.x) // PITCH)
        if 0 <= c < COLS and self.alive[r][c]:
            return r, c
        return None

    def break_at(self, r, c):
        self.alive[r][c] = False
        self.left -= 1
        return (r, c) in self.special

    def front(self):
        """いちばん手前に残っているブロックの左端"""
        for c in range(COLS):
            if any(self.alive[r][c] for r in range(ROWS)):
                return self.x + c * PITCH
        return self.x + COLS * PITCH


def move(ball, wall, m):
    """玉を1フレームぶん進める。壊した数と、枝分かれ元の玉を返す。

    5ドット幅のブロックを速さ2.1で通り抜けないよう、縦横を別々に
    小刻みに進める。どちらの向きで当たったかで跳ね返す軸が決まる。
    """
    broke, split = 0, None
    steps = 3
    dx, dy = ball.vx / steps, ball.vy / steps
    for _ in range(steps):
        ball.x += dx
        hit = wall.at(ball.x, ball.y)
        if hit:
            ball.x -= dx
            ball.vx = -ball.vx
            dx = -dx
            broke += 1
            if wall.break_at(*hit):
                split = ball
            m.beep(1800 + hit[1] * 220, 16, 0.35)

        ball.y += dy
        hit = wall.at(ball.x, ball.y)
        if hit:
            ball.y -= dy
            ball.vy = -ball.vy
            dy = -dy
            broke += 1
            if wall.break_at(*hit):
                split = ball
            m.beep(1800 + hit[1] * 220, 16, 0.35)

    if ball.y < 0.0:
        ball.y, ball.vy = -ball.y, -ball.vy
        m.beep(900, 12, 0.22)
    elif ball.y > ROWS - 1:
        ball.y, ball.vy = 2 * (ROWS - 1) - ball.y, -ball.vy
        m.beep(900, 12, 0.22)
    if ball.x > PX:
        ball.x, ball.vx = 2 * PX - ball.x, -ball.vx
        m.beep(900, 12, 0.22)
    return broke, split


def bounce_paddle(ball, pad, pad_dy, m):
    """パドルに当たったら跳ね返す

    当てた場所で角度が変わり、動かしながら当てるとさらに角度がつく。
    真横に近い角度で返すと同じ段だけを削って他の段に届かなくなるので、
    最低限の角度は必ずつける。
    """
    if ball.vx >= 0 or ball.x > PAD_X + 1:
        return False
    mid = pad + (PAD_H - 1) / 2.0
    if abs(ball.y - mid) > PAD_H / 2.0 + 0.2:
        return False
    ball.x = PAD_X + 1
    ball.vx = -ball.vx
    vy = (ball.y - mid) * 0.34 + pad_dy * SPIN
    vy = max(-VY_MAX, min(VY_MAX, vy))
    if abs(vy) < MIN_VY:
        vy = MIN_VY if ball.y < (ROWS - 1) / 2 else -MIN_VY
    ball.vy = vy
    m.beep(1200, 18, 0.3)
    return True


def split_balls(balls, src, m):
    """特殊ブロックを壊した玉から枝分かれさせる"""
    if len(balls) >= MAX_BALLS:
        return
    for sign in (-1, 1):
        if len(balls) >= MAX_BALLS:
            break
        balls.append(Ball(src.x, src.y, src.vx, sign * VY_MAX * 0.7))
    m.beep(3000, 45, 0.4)


def move_paddle(m, pad):
    """新しい位置と、そのフレームで動いた量を返す"""
    new = max(0.0, min(float(ROWS - PAD_H),
                       pad + (m.key("DOWN") - m.key("UP")) * PAD_V))
    return new, new - pad


def draw(m, wall, balls, pad, score, left, frame):
    m.cls()
    wx = int(round(wall.x))
    for r in range(ROWS):
        row = wall.alive[r]
        for c in range(COLS):
            if not row[c]:
                continue
            if (r, c) in wall.special and (frame // 4) % 2:
                continue                     # 点滅。玉が増えるブロック
            x = wx + c * PITCH
            m.hline(max(0, x), min(PX, x + BRICK_W - 1), r)
    py = int(round(pad))
    m.vline(PAD_X, py, py + PAD_H - 1)
    m.vline(PAD_X - 1, py, py + PAD_H - 1)
    for b in balls:
        m.px(int(round(b.x)), int(round(b.y)))
    for y in range(m.HEIGHT):                # 得点の場所を空ける
        for x in range(PX + 1, m.WIDTH):
            m.px(x, y, False)
    m.text(90, f"{left}{min(score, 99999):05d}")


def serve(m, wall, pad, score, left, speed):
    """パドルの上に玉を乗せて、押されるまで待つ"""
    while True:
        pad, _ = move_paddle(m, pad)
        ball = Ball(PAD_X + 2, pad + (PAD_H - 1) / 2.0, speed, MIN_VY)
        draw(m, wall, [ball], pad, score, left, m.frame)
        if not m.tick():
            return None, pad
        if m.pressed("SPACE") or m.pressed("ENTER"):
            m.beep(1400, 40, 0.35)
            return [ball], pad
        if m.pressed("BRK"):
            return None, pad


def title(m):
    for _ in range(400):
        m.cls()
        m.text(0, "SIDE BREAK")
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


def pause(m, wall, pad, score, left, frames):
    for _ in range(frames):
        draw(m, wall, [], pad, score, left, m.frame)
        if not m.tick():
            return False
    return True


def play(m):
    """1回ぶん遊ぶ。得点と、続けてよいかを返す。"""
    rnd = random.Random()
    pad = 2.5
    score = 0
    left = BALLS_AT_START
    level = 0
    wall = Wall(rnd)

    while True:
        speed = min(SPEED_MAX, SPEED0 + SPEED_UP * level)
        balls, pad = serve(m, wall, pad, score, left, speed)
        if balls is None:
            return score, False

        outcome = "lost"          # 抜けた理由。clear / crush / lost
        while balls:
            m.symbol("BUSY", (m.frame // 5) % 2 == 0)
            pad, pad_dy = move_paddle(m, pad)
            wall.x -= ADVANCE
            split = None
            for b in list(balls):
                broke, s = move(b, wall, m)
                score += broke * (10 + level * 5)
                split = split or s
                bounce_paddle(b, pad, pad_dy, m)
                if b.x < 0:
                    balls.remove(b)
            if split is not None and split in balls:
                split_balls(balls, split, m)

            draw(m, wall, balls, pad, score, left, m.frame)
            if not m.tick():
                return score, False
            if m.pressed("BRK"):
                return score, False

            # 1フレームに2個壊れることがあるので == 0 では取りこぼす
            if wall.left <= 0:
                outcome = "clear"
                break
            if wall.front() < DANGER:
                outcome = "crush"
                break

        if outcome == "clear":
            score += 500
            level += 1
            for f in range(36):
                if f % 6 == 0:
                    m.beep(1200 + f * 60, 50, 0.4)
                if not pause(m, wall, pad, score, left, 1):
                    return score, False
            wall = Wall(rnd)
            continue

        if outcome == "crush":
            wall.x = float(BX)
            m.beep(150, 420, 0.55)
        else:
            m.beep(200, 320, 0.5)
        if not pause(m, wall, pad, score, left, 14):
            return score, False
        left -= 1
        if left <= 0:
            for _ in range(6):
                m.invert()
                if not m.tick():
                    return score, False
            return score, True


def main(m):
    if not title(m):
        return
    best = 0
    while True:
        score, alive = play(m)
        if not alive:
            return
        best = max(best, score)
        if not game_over(m, score, best):
            return
