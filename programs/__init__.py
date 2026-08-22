"""ポケコンの上で動くプログラム

ここから下ではpc1251のMachineとBufferしか使わない。
pygameとPillow(PIL)はimportしないこと。画面・入力・時間はすべてMachine経由。
書き方は../PROGRAMS.mdを参照。
"""


def flip(m, period=36):
    """periodフレームごとに0と1が入れ替わる

    1行しかないので、2つのことを言いたいときは場所ではなく時間で分ける。
    液晶が尾を引くぶん、切り替えは1秒以上あけないと読めない。
    """
    return (m.frame // period) % 2
