"""筐体と液晶パネルの絵。配置と色は実機の写真から実測した。

液晶は5x7ドットの文字セルが24個、セル間は1ドットあいている。
論理的に描けるのは120x7ドット、物理的な横並びは143ドットぶん。
"""

import os

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

CELLS = 24
CW, CH = 5, 7
W, H = CELLS * CW, CH  # 120 x 7 (論理)
PHYS_W = CELLS * (CW + 1) - 1  # 143 (物理)

# 地の筐体はアルミの銀 (R-B がわずかに負)。
# 液晶を囲む板はシャンパンゴールドの塗装で、縁が起きていて強く光を返す。
BODY = (216, 217, 222)
BODY_LIGHT = (232, 233, 237)
BODY_SHADE = (196, 197, 203)
GOLD = (205, 188, 158)
GOLD_DARK = (191, 172, 140)
GOLD_LIGHT = (220, 205, 179)
RING = (206, 206, 204)         # ガラスの下に凹んで入る銀の内枠
RING_LIGHT = (250, 250, 247)   # その反射面。ほぼ白く飛ぶ
RING_DARK = (104, 101, 98)     # 上端。手前の面の影に入る
GLASS = (180, 193, 168)
GLASS_TOP = (188, 201, 176)
GLASS_BOTTOM = (170, 184, 160)
DOT_INK = (28, 36, 64)         # 点灯ドットは黒ではなく濃い青紫
DOT_OFF_A = 33   # 消灯している文字セルも薄い枡目として見える
DOT_ON_A = 240


DOT = 5
PITCH = 7                   # ドット5px + すきま2px
MAT_W = PHYS_W * PITCH - 1  # 1000
MAT_H = H * PITCH - 1       # 48

# 各部の位置。実機の写真を実測した比率をそのまま拡大したもの。
# 文字マトリクスはガラス面の内側に上下左右とも余白を置く。
IMG_W, IMG_H = 1425, 292
BEZEL = (42, 22, 1215, 261)       # シャンパンゴールドの面。ロゴもこの上
SIDE_AL = 9                       # その左右で下地のアルミが見えている幅
BAND_Y = 72                       # ロゴ帯と液晶部を分けるアルミの帯
LOGO_MID = 47                     # 刻印の中心。ロゴ帯のまんなか
LOGO_STEM = 3                     # SHARPの縦線を太らせる量(px)
LOGO_TRACK = 4                    # 字間を詰める量(px)
LOGO_X = 82                       # ロゴの左端。ガラスの左端にそろえる
LOGO_W, LOGO_H = 180, 33          # ロゴ全体を収める枠。横長につぶす
MODEL_X = 286                     # 型番の刷り。ロゴの右に一定の間をあける
GLASS_BOX = (82, 87, 1186, 226)  # ガラス。金色の面と同じ高さではまっている
GLASS_R = 11                      # ガラスをはめている枠の角の丸み
# ガラスの下に凹んで入る銀の内枠。左右が長く、上下は狭い。
# 内枠の縁は液晶より高いところにあるので、液晶の面に影が落ちる。
RING_X, RING_TOP, RING_BOTTOM = 27, 13, 16
SHADOW = 11                       # 枠が液晶の面に落とす影の幅(上)
SHADOW_X = 6                      # 同じく左。光が上からなので上より狭い
LCD_R = 6                         # 液晶の角の丸み
LCD_BOX = (GLASS_BOX[0] + RING_X, GLASS_BOX[1] + RING_TOP,
           GLASS_BOX[2] - RING_X, GLASS_BOX[3] - RING_BOTTOM)
MAT_X, MAT_Y = 134, 143
ANN_Y = 113
ANN_H = 18

def _lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


# インジケータ。並びは実機の順、間隔は等間隔で詰める。
# 位置の根拠は写真で読めた DEG だけで、その左端がマトリクス幅の 33.1%。
# 他のものが写った写真が手に入れば測り直す。
ANN_ORDER = ["BUSY", "DEF", "SHIFT", "HYP", "RUN", "PRO", "RSV",
             "DEG", "RAD", "GRAD", "E"]
ANN_DEG_X = 0.316


# 筐体の刻印に使う欧文フォント。OSによって置き場所が違うので候補から探す。
# 見つからなくても、描画済みのbody.pngがあれば結果は変わらない。
_FONT_DIRS = [
    "/usr/share/fonts/truetype/lato",
    "/usr/share/fonts/truetype/dejavu",
    "/usr/share/fonts/truetype",
    "/System/Library/Fonts",
    "/System/Library/Fonts/Supplemental",
    "/Library/Fonts",
    os.path.expanduser("~/Library/Fonts"),
    "C:/Windows/Fonts",
]


def _find(names):
    for d in _FONT_DIRS:
        for n in names:
            p = os.path.join(d, n)
            if os.path.exists(p):
                return p
    return None


LOGO_FONT = _find(["Lato-Bold.ttf", "HelveticaNeue.ttc", "Helvetica.ttc",
                   "Arial Bold.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"])
TEXT_FONT = _find(["Lato-Regular.ttf", "Helvetica.ttc", "Arial.ttf",
                   "arial.ttf", "DejaVuSans.ttf"])
# インジケータは液晶自身が出す表示なので、太らせず本文と同じ細さで描く
ANN_FONT = _find(["DejaVuSansCondensed.ttf", "DejaVuSans.ttf",
                  "Lato-Regular.ttf", "Helvetica.ttc", "Arial.ttf"])


def _font(path, size):
    if path:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


def _vgrad(d, box, top, bottom, gamma=1.0):
    x0, y0, x1, y1 = box
    for y in range(y0, y1 + 1):
        t = (y - y0) / float(max(1, y1 - y0))
        d.line([(x0, y), (x1, y)], fill=_lerp(top, bottom, t ** gamma))


_CACHE_DIR = os.path.dirname(os.path.abspath(__file__))
_BODY_PNG = os.path.join(_CACHE_DIR, "body.png")


def make_body(rebuild=False):
    """筐体の絵。描画済みのbody.pngがあればそれを読む。

    筐体は動かないので毎回描く必要がない。同梱のPNGを使えば、
    刻印用のフォントが入っていない環境でも見た目が変わらない。
    PC1251_REBUILD=1を立てるかrebuild=Trueで描き直す。
    """
    if not rebuild and not os.environ.get("PC1251_REBUILD"):
        if os.path.exists(_BODY_PNG):
            return Image.open(_BODY_PNG).convert("RGB")
    img = render_body()
    try:
        img.save(_BODY_PNG)
    except OSError:
        pass
    return img


# モードスイッチ。写真を実測した位置をそのまま使う。
# ラベルは本体に黒い枠線で刷ってあり、右側に切り欠きがある。
# つまみは彫り込んだ溝のなかを金属のスライダが動く。
SW_LABELS = ("ON", "RSV", "PRO", "RUN")
SW_BOX = (1224, 72, 1268, 171)      # ON..RUN を囲む枠
SW_OFF_BOX = (1224, 176, 1268, 197)
SW_SLOT = (1274, 93, 1330, 198)     # つまみの溝
SW_POS = 3                          # スライダの位置 (0=ON .. 4=OFF)


def draw_switch(d):
    x0, y0, x1, y1 = SW_BOX
    sx0, sy0, sx1, sy1 = SW_SLOT
    step = (y1 - y0) / len(SW_LABELS)
    ink = (52, 50, 47)

    size = 18
    while size > 10:                # いちばん長いラベルが枠に収まる大きさにする
        f = _font(TEXT_FONT, size)
        if max(d.textlength(s, font=f) for s in SW_LABELS) <= x1 - x0 - 10:
            break
        size -= 1

    d.rectangle([x0, y0, x1, y1], outline=ink, width=2)
    d.rectangle(SW_OFF_BOX, outline=ink, width=2)
    # 段の区切りの線は、枠の外側に接するところから溝まで伸びる。
    # 枠のなかには入らない。
    for i, lab in enumerate(SW_LABELS):
        d.text((x0 + 5, y0 + 1 + i * step), lab, font=f, fill=ink)
        if i:
            y = int(y0 + i * step)
            d.line([(x1 + 1, y), (sx0 - 1, y)], fill=ink, width=2)
    d.text((SW_OFF_BOX[0] + 5, SW_OFF_BOX[1]), "OFF", font=f, fill=ink)
    ymid = (SW_OFF_BOX[1] + SW_OFF_BOX[3]) // 2
    d.line([(SW_OFF_BOX[2] + 1, ymid), (sx0 - 1, ymid)],
           fill=ink, width=2)

    # 溝。まわりの縁が光を返し、中は彫り込まれて暗い
    d.rounded_rectangle([sx0 - 3, sy0 - 3, sx1 + 3, sy1 + 3], radius=9,
                        fill=(228, 226, 222))
    d.rounded_rectangle([sx0, sy0, sx1, sy1], radius=7, fill=(74, 69, 63))
    d.rounded_rectangle([sx0 + 2, sy0 + 2, sx1 - 2, sy0 + 8], radius=4,
                        fill=(46, 42, 38))

    # 金属のスライダ。上面は暗く、指がかりの段で光が返る
    h = (sy1 - sy0 - 8) / 5.0
    ky0 = int(sy0 + 4 + SW_POS * h) - 10
    ky1 = ky0 + int(h) + 22
    mid = (ky0 + ky1) // 2
    _vgrad(d, (sx0 + 2, ky0, sx1 - 2, mid), (96, 90, 83), (58, 54, 49))
    _vgrad(d, (sx0 + 2, mid, sx1 - 2, mid + 9), (232, 229, 222),
           (150, 144, 135))
    _vgrad(d, (sx0 + 2, mid + 10, sx1 - 2, ky1), (72, 67, 62), (120, 114, 106))
    d.line([(sx0 + 2, ky0), (sx1 - 2, ky0)], fill=(150, 144, 136))
    d.line([(sx0 + 2, ky1), (sx1 - 2, ky1)], fill=(196, 192, 185))


def render_body():
    """筐体を描く。面の境目は線ではなく明暗のグラデーションで表す。"""
    img = Image.new("RGB", (IMG_W, IMG_H), BODY)
    d = ImageDraw.Draw(img)
    _vgrad(d, (0, 0, IMG_W, IMG_H), BODY_LIGHT, BODY_SHADE, 0.7)

    # 金色パネル
    x0, y0, x1, y1 = BEZEL
    _vgrad(d, BEZEL, GOLD_LIGHT, GOLD_DARK, 0.85)
    # 浮き出た面の左右は金色が回りこんでおらず、下地のアルミが見えている
    for i in range(SIDE_AL):
        d.line([(x0 + i, y0), (x0 + i, y1)],
               fill=_lerp(BODY_LIGHT, BODY, i / float(SIDE_AL)))
        d.line([(x1 - i, y0), (x1 - i, y1)],
               fill=_lerp(BODY_SHADE, BODY, i / float(SIDE_AL)))
    for i in range(4):        # アルミと金色の継ぎ目。左は光り、右は影になる
        d.line([(x0 + SIDE_AL + i, y0), (x0 + SIDE_AL + i, y1)],
               fill=_lerp((243, 238, 226), GOLD, i / 4.0))
        d.line([(x1 - SIDE_AL - i, y0), (x1 - SIDE_AL - i, y1)],
               fill=_lerp((150, 133, 106), GOLD_DARK, i / 4.0))
    gx0, gx1 = x0 + SIDE_AL, x1 - SIDE_AL   # 金色が乗っている範囲
    for i in range(6):        # 上端の稜線。持ち上がったぶん強く光る
        d.line([(gx0, y0 + i), (gx1, y0 + i)],
               fill=_lerp((246, 240, 224), GOLD_LIGHT, i / 6.0))
    for i in range(6):        # 下端は落ちる
        d.line([(gx0, y1 - i), (gx1, y1 - i)],
               fill=_lerp((162, 141, 110), GOLD_DARK, i / 6.0))
    for i in range(6):        # 左右のアルミも同じように上が光り下が落ちる
        for xa, xb in ((x0, gx0 - 1), (gx1 + 1, x1)):
            d.line([(xa, y0 + i), (xb, y0 + i)],
                   fill=_lerp((250, 250, 252), BODY_LIGHT, i / 6.0))
            d.line([(xa, y1 - i), (xb, y1 - i)],
                   fill=_lerp((164, 164, 170), BODY_SHADE, i / 6.0))
    for i in range(8):        # パネルが本体に落とす影
        d.line([(x0, y1 + 1 + i), (x1, y1 + 1 + i)],
               fill=_lerp((166, 163, 156), BODY, i / 8.0))

    # SHARPロゴ。パネルから盛り上がった金属なので、光は左上の角に乗り、
    # 影は右下へ落ちる。文字の形をずらして引き算し、縁だけを取り出す。
    # 実機のロゴは字間がほとんど無く、横へ広がった字形。いったん普通に
    # 組んでから、その塊を横長の枠へ引き伸ばして近づける。
    f_logo = _font(LOGO_FONT, 64)
    tmp = Image.new("L", (900, 200), 0)
    td = ImageDraw.Draw(tmp)
    lx = 20
    for ch in "SHARP":
        for k in range(LOGO_STEM):   # 横へずらして重ね、縦の線を太らせる
            td.text((lx + k, 100), ch, font=f_logo, fill=255, anchor="lm")
        lx += td.textlength(ch, font=f_logo) + LOGO_STEM - LOGO_TRACK
    glyphs = tmp.crop(tmp.getbbox()).resize((LOGO_W, LOGO_H), Image.LANCZOS)
    mark = Image.new("L", (IMG_W, IMG_H), 0)
    mark.paste(glyphs, (LOGO_X, LOGO_MID - LOGO_H // 2))

    def _rim(dx, dy):
        return ImageChops.subtract(ImageChops.offset(mark, dx, dy), mark)

    drop = _rim(2, 2).filter(ImageFilter.GaussianBlur(0.6))
    img.paste(Image.new("RGB", (IMG_W, IMG_H), (139, 118, 78)), (0, 0), drop)

    face = Image.new("RGB", (IMG_W, IMG_H))
    _vgrad(ImageDraw.Draw(face), (0, y0, IMG_W, BAND_Y),
           (252, 251, 247), (219, 213, 198))
    img.paste(face, (0, 0), mark)

    lit = ImageChops.subtract(mark, ImageChops.offset(mark, 2, 2))
    img.paste(Image.new("RGB", (IMG_W, IMG_H), (255, 255, 253)), (0, 0),
              lit.filter(ImageFilter.GaussianBlur(0.5)))
    dim = ImageChops.subtract(mark, ImageChops.offset(mark, -2, -2))
    img.paste(Image.new("RGB", (IMG_W, IMG_H), (146, 126, 88)), (0, 0),
              dim.filter(ImageFilter.GaussianBlur(0.6)))

    # 型番は細い字で、字間を空けて濃い茶で刷られている
    f_model = _font(TEXT_FONT, 23)
    x = MODEL_X
    for word in ("POCKET COMPUTER", "PC-1251"):
        for ch in word:
            d.text((x, LOGO_MID), ch, font=f_model, fill=(98, 82, 48),
                   anchor="lm")
            x += d.textlength(ch, font=f_model) + 1.5
        x += 22

    # ロゴ帯と液晶部の境。ここも金色が乗っておらず、下地のアルミが帯で出る
    band = [(182, 168, 142), (228, 229, 233), (240, 241, 244), (238, 239, 242),
            (228, 229, 234), (212, 212, 217), (186, 176, 154)]
    for i, c in enumerate(band):
        d.line([(x0 + SIDE_AL, BAND_Y + i), (x1 - SIDE_AL, BAND_Y + i)], fill=c)

    # ガラスはシャンパンゴールドの面と同じ高さではまっている。
    # その下に銀の内枠が凹んで入り、さらに下に液晶がある。
    gx0, gy0, gx1, gy1 = GLASS_BOX
    for i in range(3):        # ガラスの縁。金色の面がわずかに落ちる
        d.rounded_rectangle([gx0 - 3 + i, gy0 - 3 + i, gx1 + 3 - i, gy1 + 3 - i],
                            radius=GLASS_R + 3 - i,
                            outline=_lerp((246, 238, 220), (150, 134, 106),
                                          i / 3.0))
    # 銀の内枠。凹んでいるので、上端は手前の面の影に入って暗く、
    # そのすぐ下の面が強い反射で白く飛ぶ
    d.rounded_rectangle([gx0, gy0, gx1, gy1], radius=GLASS_R, fill=RING)
    for i in range(3):
        d.line([(gx0 + GLASS_R, gy0 + i), (gx1 - GLASS_R, gy0 + i)],
               fill=RING_DARK)
    for i in range(3, RING_TOP):
        d.line([(gx0 + GLASS_R - i, gy0 + i), (gx1 - GLASS_R + i, gy0 + i)],
               fill=_lerp(RING_LIGHT, RING, (i - 3) / (RING_TOP - 3.0)))
    d.line([(gx0 + GLASS_R, gy1), (gx1 - GLASS_R, gy1)], fill=RING_LIGHT)
    d.line([(gx1, gy0 + GLASS_R), (gx1, gy1 - GLASS_R)], fill=RING_LIGHT)

    # 液晶そのもの。内枠より一段低いので、枠の縁が液晶の面に影を落とす。
    # 影は液晶の上に乗るものなので、角の丸みも液晶に従う。
    lx0, ly0, lx1, ly1 = LCD_BOX
    lw, lh = lx1 - lx0 + 1, ly1 - ly0 + 1
    lcd = Image.new("RGB", (lw, lh))
    ld = ImageDraw.Draw(lcd)
    for y in range(lh):
        ld.line([(0, y), (lw - 1, y)],
                fill=_lerp(GLASS_TOP, GLASS_BOTTOM, y / (lh - 1.0)))
    mask = Image.new("L", (lw, lh), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, lw - 1, lh - 1],
                                           radius=LCD_R, fill=255)
    # 影は枠の穴を斜め下へずらしたぶんの差。こう作ると角では自然に
    # 帯が細くなり、丸みにも乗る。光は上からなので縦のずれのほうが大きい。
    lit = Image.new("L", (lw, lh), 0)
    lit.paste(mask, (SHADOW_X, SHADOW))
    shade = ImageChops.subtract(mask, lit)
    shade = shade.filter(ImageFilter.GaussianBlur(2.2))
    shade = ImageChops.multiply(shade, mask)
    shade = shade.point(lambda v: v * 215 // 255)
    lcd.paste(Image.new("RGB", (lw, lh), (52, 56, 58)), (0, 0), shade)
    img.paste(lcd, (lx0, ly0), mask)

    # 斜めの映り込み。いちばん上のガラス面なので内枠にも液晶にもかかる
    refl = Image.new("L", (gx1 - gx0 + 1, gy1 - gy0 + 1), 0)
    rd = ImageDraw.Draw(refl)
    for k in range(-40, 360):
        a = max(0, 22 - abs(k - 160) // 4)
        rd.line([(k, 0), (k - 140, gy1 - gy0)], fill=a, width=4)
    img.paste(Image.new("RGB", refl.size, (255, 255, 255)), (gx0, gy0), refl)

    # パネル右下の印刷
    f_tiny = _font(TEXT_FONT, 16)
    d.text((1190, 242), "MEMORY SAFE GUARD / AUTO POWER OFF",
           font=f_tiny, fill=(106, 90, 54), anchor="ra")

    draw_switch(d)

    # 写真らしさのために、わずかにぼかしてから粒状ノイズを乗せる。
    # ガラス面だけはノイズを避ける(毎フレーム書き換わるので圧縮できない)。
    img = img.filter(ImageFilter.GaussianBlur(0.7))
    clean = img.crop((gx0, gy0, gx1 + 1, gy1 + 1))
    noise = Image.effect_noise((IMG_W, IMG_H), 5).convert("RGB")
    img = ImageChops.add(img, noise, scale=1, offset=-128)
    img.paste(clean, (gx0, gy0))
    return img


def ann_layout(d, f):
    """インジケータの左端の位置。DEG が実測の場所に来るよう間隔を決める。"""
    widths = [d.textlength(n, font=f) for n in ANN_ORDER]
    i = ANN_ORDER.index("DEG")
    gap = (ANN_DEG_X * MAT_W - sum(widths[:i])) / i
    out, x = [], 0.0
    for name, w in zip(ANN_ORDER, widths, strict=True):
        out.append((name, int(round(x))))
        x += w + gap
    return out


def osd_img(text):
    """シミュレータ側の表示。インジケータと同じ書体で右端に置く。"""
    f = _font(ANN_FONT, 13)
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    im = Image.new("RGBA", (int(probe.textlength(text, font=f)) + 2, ANN_H),
                   (0, 0, 0, 0))
    ImageDraw.Draw(im).text((0, 1), text, font=f,
                            fill=DOT_INK + (DOT_ON_A,))
    return im


_ANN_CACHE = {}


def _ann_img(active):
    """点灯中のインジケータだけを描いたRGBAオーバレイ"""
    key = tuple(sorted(active))
    if key in _ANN_CACHE:
        return _ANN_CACHE[key]
    im = Image.new("RGBA", (MAT_W, ANN_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    f = _font(ANN_FONT, 13)
    for name, x in ann_layout(d, f):
        if name in active:
            d.text((x, 1), name, font=f, fill=DOT_INK + (DOT_ON_A,))
    _ANN_CACHE[key] = im
    return im



# --- 液晶の応答 ---
# 1980年代の液晶は応答が遅く、点灯にも消灯にも数フレームかかる。
# 消える側のほうが遅いので、速く動くドットは尾を引いて見える。
# 時定数で持っておき、フレーム時間から係数を作る。
LEVELS = 6
TAU_RISE_MS = 33.0
TAU_FALL_MS = 86.0

DOT_ALPHA = [int(round(DOT_OFF_A + (DOT_ON_A - DOT_OFF_A) * i / (LEVELS - 1)))
             for i in range(LEVELS)]


def phys_x(x):
    """論理列(0..119)を液晶上の物理ドット位置に変換する"""
    return (x // CW) * (CW + 1) + (x % CW)


def dot_rects():
    """マトリクス内の各ドットの矩形(x, y, w, h)を論理座標順に返す"""
    out = []
    for y in range(H):
        row = []
        for x in range(W):
            row.append((phys_x(x) * PITCH, y * PITCH, DOT, DOT))
        out.append(row)
    return out


def glass_patch(body, grid=True):
    """ドットを消したときの下地(ガラス面)。毎フレーム貼り直して使う。

    grid=Trueなら、消灯している文字セルの枡目も薄く焼き込んでおく。
    実機でも消えているセルはうっすら見えるし、毎フレーム描くより速い。
    """
    im = body.crop((MAT_X, MAT_Y, MAT_X + MAT_W, MAT_Y + MAT_H))
    if not grid:
        return im
    ov = Image.new("RGBA", (MAT_W, MAT_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    off = DOT_INK + (DOT_ALPHA[0],)
    for y in range(H):
        for x in range(W):
            px = phys_x(x) * PITCH
            d.rectangle(
                [px, y * PITCH, px + DOT - 1, y * PITCH + DOT - 1],
                fill=off)
    return Image.alpha_composite(im.convert("RGBA"), ov).convert("RGB")


def ann_patch(body):
    return body.crop((MAT_X, ANN_Y, MAT_X + MAT_W, ANN_Y + ANN_H))


def ann_overlay(active):
    return _ann_img(tuple(active))
