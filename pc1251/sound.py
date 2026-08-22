"""圧電ブザーの音

実機の音は、機械語でポート1本を反転させて作る矩形波。半周期の長さは
待ちループの回数nで決まり、CPUは576kHzなので

    f = CLOCK / (2 * LOOP_CYC * n)

nは整数なので出せる音程は飛び飛びになるが、刻みは1/nなので低い音ほど
細かい。300Hzあたりなら半音(約6%)よりずっと細かく刻めるので、実機でも
機械語で音楽を鳴らせた。粗くなるのは高いほうで、3kHzを超えると隣の音との
差が1音を超える。ここではその量子化と、小さな圧電素子の痩せた音色を出す。
"""

from array import array

RATE = 22050
CLOCK = 576000.0  # SC61860のクロック
LOOP_CYC = 8      # 待ちループ1周ぶんの命令サイクル数(概算)
BASE = CLOCK / (2 * LOOP_CYC)     # n=1 に相当する周波数
MIN_N = 4         # これより短いループは書けない (9000Hz)
MAX_N = 450       # これより長くすると音として聞こえない (80Hz)
HPF = 0.86        # 圧電素子は低音を返さない。一次のハイパス
EDGE_MS = 0.8     # 端をなまらせる幅。無いと切れ目で耳障りな音が出る

_cache = {}


def quantize(hz: float) -> tuple[float, int]:
    """実機が出せるいちばん近い音程と、そのループ回数"""
    n = max(MIN_N, min(MAX_N, int(round(BASE / max(1.0, hz)))))
    return BASE / n, n


def render(hz: float, ms: int, vol: float = 0.5) -> bytes:
    f, k = quantize(hz)
    key = (k, ms, round(vol, 2))
    if key in _cache:
        return _cache[key]
    n = max(1, int(RATE * ms / 1000))
    half = RATE / f / 2.0
    amp = 32000 * vol
    edge = max(1.0, RATE * EDGE_MS / 1000)
    out = array("h")
    x_prev = y = 0.0
    for i in range(n):
        x = amp if (i // half) % 2 < 1 else -amp
        y = HPF * (y + x - x_prev)
        x_prev = x
        e = min(1.0, i / edge, (n - i) / edge)
        v = int(y * e)
        out.append(max(-32000, min(32000, v)))
    data = out.tobytes()
    _cache[key] = data
    return data
