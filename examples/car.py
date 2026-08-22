"""← → で車が動くだけ。

    uv run play.py car

キーの読み方と、ドット絵の置き方の見本。
画面はy=0が上、y=6が下。xは0から119まで。
"""

# "#" のところが点く。この車は6x3ドット
CAR = [
    "..##..",
    "######",
    ".#..#.",
]

ROAD_Y = 6          # 道路のy
SPEED = 1.5         # 1フレームに何ドット動くか


def main(m):
    x = 20.0        # 車の位置。floatにしておくと速さを細かく決められる

    while m.tick():
        if m.pressed("BRK"):
            return

        # key() は押しているあいだずっと真。pressed() は押した瞬間だけ真
        if m.key("LEFT"):
            x -= SPEED
        if m.key("RIGHT"):
            x += SPEED
        x = max(0.0, min(m.WIDTH - 6.0, x))     # 画面の外へ出さない

        m.cls()
        m.hline(0, m.WIDTH - 1, ROAD_Y)         # 道路
        m.sprite(int(x), ROAD_Y - 3, CAR)       # yはドット絵の上端を指す
