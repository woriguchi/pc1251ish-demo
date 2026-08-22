"""「PC-インタープリタ」の文法を解釈するコード

出典は工学社「PiO」1986年8月号 169〜171ページ、作者は Fan_PC-1251 氏
(https://x.com/pio1986_10)。PC-1245/51/55用。

オリジナルの処理系はマシン語976バイトで、&C200〜&C5CFに
置いてBASICから CALL &C300 で呼び出すものでした。ここでは、かわりに同じ
PC-インタープリタの文法をPythonで読んで実行するプログラムを書きました。

仕様は以下の通りです。

    DEG 位置,データ…   位置00〜77が横120ドット、データは縦7ドットの列
    COS                画面を消す
    SQR                白黒反転
    PRINT "文字列"      CALL で決めた桁から出す
    BEEP 高さ,長さ      鳴り終わるまで止まる
    INKEY$             押しているキーのコード。何も押していなければFF

定数は16進2ケタ、変数はA〜Zの1バイト、配列は(&00)〜(&9F)。A〜Zは配列の
&86〜&9Fと同じ場所なので、Zは&C69F番地になります。&、=、: はオリジナルのとお
り省けます。構文が曖昧になるので、以下のように処理しています。
(本物とはその点で違うかも知れません。)

  ・命令の頭では、まず命令語、次に1文字の変数として読む
  ・値のところでは、16進2ケタが並んでいればそれを定数として読む
  ・式は前から順に計算する。カッコは無い

同じ字面でも置かれた場所で読み方が変わるので、場所ごとに別の正規表現を
用意して、その位置から順に当てていく。

BEEPの音程と長さの換算だけは適当ですのでオリジナルとの互換性はありません。
"""

import operator
import os
import random
import re

FPS = 24
STMT_PER_FRAME = 60      # 1フレームに進める命令数。BASICの5〜7倍のつもり
MEM_SIZE = 0xA0          # 配列(&00)〜(&9F)
MEM_BASE = 0xC600        # その先頭の番地。A〜Zは&C686から
VAR_BASE = 0x86
NO_KEY = 0xFF            # 何も押していないときのINKEY$

PROG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "progs")

# 表2のキーコード。上から順に見て、最初に押されているものを返す。
# SPCは表2に無いので、英字の次の&6Bを当てた
KEY_CODES = [("ENTER", 0x00), ("BRK", 0x07), ("UP", 0x0C), ("DOWN", 0x0D),
             ("RIGHT", 0x0E), ("LEFT", 0x0F), ("SPACE", 0x6B)]
KEY_CODES += [(str(i), 0x40 + i) for i in range(10)]
KEY_CODES += [(chr(65 + i), 0x51 + i) for i in range(26)]

WORDS = (r"INKEY\$|COM\$|CLEAR|PRINT|PEEK|BEEP|GOTO|NEXT|STOP|WAIT|CALL"
         r"|COS|SQR|DEG|RND|END|FOR|LET|NOT|IF")

# 命令の頭。命令語が先で、そうでなければ1文字が代入の左辺
HEAD = re.compile(rf"[\s:;]*(?:(?P<word>{WORDS})|(?P<rem>\.)"
                  r"|(?P<var>[A-Z])(?P<idx>\))?\s*=?)")
# 値のところ。16進2ケタが先なので FF は定数、F+ の F は変数になる
VALUE = re.compile(r"\s*(?:&?(?P<hex>[0-9A-F]{2})|(?P<fn>INKEY\$|PEEK|RND)"
                   r"|\"(?P<ch>.)\"?|(?P<var>[A-Z])(?P<idx>\))?)")
BINOP = re.compile(r"\s*(?P<op>AND|OR|[-+*/])")
RELOP = re.compile(r"\s*(?P<rel><>|[=<>])")
COMMA = re.compile(r"\s*,")
STRING = re.compile(r'\s*"(?P<s>[^"]*)"')
EOL = re.compile(r"[\s:;]*$")
LINE = re.compile(r"(?P<num>\d+)\s*:?\s*(?P<body>.*)")
HEADER = re.compile(r"#\s*(?P<key>\w+)\s*(?P<rest>.*)")


class PcError(Exception):
    """オリジナルのエラーコード。1=文法、2=演算、4=ライン"""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


class Halt(Exception):
    """実行を終える。whyは END / BREAK / QUIT"""

    def __init__(self, why):
        super().__init__(why)
        self.why = why


def _div(a, b):
    if not b:
        raise PcError(2)
    return a // b


BINOPS = {"+": operator.add, "-": operator.sub, "*": operator.mul,
          "/": _div, "AND": operator.and_, "OR": operator.or_}
RELOPS = {"=": operator.eq, ">": operator.gt, "<": operator.lt,
          "<>": operator.ne}


def beep_hz(v):
    """BEEPの式1から周波数へ。オリジナルには大小しか書いていないので決め打ち"""
    return min(6000, 120 + v * 28)


def beep_ms(v):
    """BEEPの式2から長さへ。これも決め打ち"""
    return max(8, v * 8)


class Program:
    """1本ぶんのソース。見出し行(#)で題名や得点の場所を書ける"""

    def __init__(self, path):
        self.path = path
        self.name = os.path.splitext(os.path.basename(path))[0]
        self.title = self.name.upper()
        self.score = None          # 得点の番地。上の桁から並べる
        self.speed = None          # 1フレームに進める命令数
        self.data = []             # (番地, バイト列)。BASICのPOKEにあたる
        self.lines = []            # [(行番号, 本文)]
        self._load()

    def _load(self):
        for raw in open(self.path, encoding="utf-8"):
            s = raw.strip()
            if s.startswith("#"):
                self._header(HEADER.match(s))
                continue
            m = LINE.match(s)
            if not m:
                continue                    # 行番号のない行は読まない
            if int(m.group("num")) < 900:   # 900番以上はBASIC側の行
                self.lines.append((int(m.group("num")), m.group("body")))
        self.lines.sort(key=lambda t: t[0])

    def _header(self, m):
        if not m:
            return
        key, rest = m.group("key").upper(), m.group("rest").strip()
        if key == "TITLE":
            self.title = rest
        elif key == "SCORE":
            self.score = [int(a.strip().lstrip("&"), 16)
                          for a in rest.split(",")]
        elif key == "SPEED":
            self.speed = max(1, int(rest))
        elif key == "POKE":
            # オリジナルではBASIC側がCALLの前にPOKEでデータを置いていた。
            # #POKE 番地 バイト,バイト,… と書けば同じことができる
            addr, _, body = rest.partition(" ")
            self.data.append((int(addr.lstrip("&"), 16),
                              [int(v, 16) for v in
                               body.replace(",", " ").split()]))


def programs():
    """progs/ にある .pci を並べて返す"""
    if not os.path.isdir(PROG_DIR):
        return []
    return [Program(os.path.join(PROG_DIR, fn))
            for fn in sorted(os.listdir(PROG_DIR)) if fn.endswith(".pci")]


class Interp:
    def __init__(self, m, prog, seed=None):
        self.m = m
        self.prog = prog
        self.lines = prog.lines
        self.mem = bytearray(MEM_SIZE)
        self.rnd = random.Random(seed)
        self.cursor = 0
        self.li = 0
        self.pos = 0
        self.state = True          # IFが偽のあいだ False
        self.loop = None           # FOR〜NEXT。1段しか持たない
        self.per_frame = prog.speed or STMT_PER_FRAME
        self.budget = self.per_frame
        self.err_line = 0
        for addr, vals in prog.data:
            if addr >= MEM_BASE:
                addr -= MEM_BASE
            self.mem[addr:addr + len(vals)] = bytes(vals)

    # ------------------------------------------------ メモリとキー

    def peek(self, addr):
        if MEM_BASE <= addr < MEM_BASE + MEM_SIZE:
            return self.mem[addr - MEM_BASE]
        return self.mem[addr] if 0 <= addr < MEM_SIZE else 0

    def inkey(self):
        for name, code in KEY_CODES:
            if self.m.key(name):
                return code
        return NO_KEY

    # ------------------------------------------------ 時間

    def frame(self):
        self.budget = self.per_frame
        if not self.m.tick():
            raise Halt("QUIT")
        if self.m.key("BRK"):
            raise Halt("BREAK")

    def sleep(self, frames):
        for _ in range(max(1, frames)):
            self.frame()

    def charge(self):
        self.budget -= 1
        if self.budget <= 0:
            self.frame()

    # ------------------------------------------------ 字句

    def text(self):
        return self.lines[self.li][1]

    def match(self, rx):
        m = rx.match(self.text(), self.pos)
        if m:
            self.pos = m.end()
        return m

    def addr(self, letter, idx):
        """A なら置き場所、A) なら A の値を添字にした配列の場所"""
        a = VAR_BASE + ord(letter) - 65
        return self.mem[a] % MEM_SIZE if idx else a

    # ------------------------------------------------ 式

    def operand(self):
        m = self.match(VALUE)
        if not m:
            raise PcError(1)
        if m.group("hex"):
            return int(m.group("hex"), 16)
        if m.group("ch"):
            return ord(m.group("ch").upper()) & 0xFF
        fn = m.group("fn")
        if fn == "INKEY$":
            return self.inkey()
        if fn == "PEEK":
            return self.peek(self.operand())
        if fn == "RND":
            n = self.operand()
            return self.rnd.randrange(n) if n else 0
        return self.mem[self.addr(m.group("var"), m.group("idx"))]

    def expr(self):
        v = self.operand()
        m = self.match(BINOP)
        while m:
            v = BINOPS[m.group("op")](v, self.operand()) & 0xFF
            m = self.match(BINOP)
        return v

    def condition(self):
        left = self.expr()
        m = self.match(RELOP)
        if not m:
            raise PcError(1)
        return RELOPS[m.group("rel")](left, self.expr())

    # ------------------------------------------------ 画面

    def show(self, s):
        """CALLで決めた桁から文字を置く。桁のドットは先に消す"""
        x = (self.cursor % self.m.CELLS) * self.m.CELL_W
        for i in range(len(s) * self.m.CELL_W):
            for y in range(self.m.HEIGHT):
                self.m.px(x + i, y, False)
        self.m.text(x, s)

    def deg(self, pos, data):
        """列データを並べる。POKE &F800,… と同じ書き心地のもの"""
        for i, v in enumerate(data):
            for y in range(self.m.HEIGHT):
                self.m.px(pos + i, y, bool(v >> y & 1))

    # ------------------------------------------------ 命令

    def do_clear(self):
        self.mem[:] = bytes(MEM_SIZE)

    def do_cos(self):
        self.m.cls()
        self.cursor = 0

    def do_sqr(self):
        self.m.invert()

    def do_call(self):
        self.cursor = self.expr()

    def do_print(self):
        m = self.match(STRING)
        self.show(m.group("s") if m else chr(self.expr()))

    def do_deg(self):
        pos = self.expr()
        data = []
        while self.match(COMMA):
            data.append(self.expr())
        self.deg(pos, data)

    def do_beep(self):
        hz = beep_hz(self.expr())
        if not self.match(COMMA):
            raise PcError(1)
        ms = beep_ms(self.expr())
        self.m.beep(hz, ms)
        self.sleep(round(ms / 1000 * FPS))

    def do_wait(self):
        self.sleep(round(self.expr() / 256 * FPS))

    def do_stop(self):
        while self.inkey() == NO_KEY:
            self.frame()
        while self.inkey() != NO_KEY:
            self.frame()

    def do_goto(self):
        """飛び先は式の16進2ケタ。それを行番号の下2ケタとして探す"""
        tag = f"{self.expr():02X}"
        if not tag.isdigit():
            raise PcError(4)
        for i, (num, _) in enumerate(self.lines):
            if num % 100 == int(tag):
                self.li, self.pos, self.state = i, 0, True
                return
        raise PcError(4)

    def do_for(self):
        self.loop = [self.expr() or 256, self.li, self.pos]

    def do_next(self):
        if self.loop is None:
            return
        self.loop[0] -= 1
        if self.loop[0] > 0:
            self.li, self.pos = self.loop[1], self.loop[2]
        else:
            self.loop = None

    def do_if(self):
        if not self.condition():
            self.state = False

    def do_not(self):
        self.state = not self.state

    def do_let(self):
        # オリジナルでは「このコマンドがあると次の命令を無視して進む」
        # 区切りが省ける書き方では次がどこまでか決められないので、
        # : があればそこまで、無ければ行の終わりまでを捨てる
        t = self.text()
        i = t.find(":", self.pos)
        self.pos = len(t) if i < 0 else i + 1

    def do_end(self):
        raise Halt("END")

    def do_com(self):
        pass                                  # マシン語は呼べない

    ACTIONS = {"CLEAR": do_clear, "COS": do_cos, "SQR": do_sqr,
               "CALL": do_call, "PRINT": do_print, "DEG": do_deg,
               "BEEP": do_beep, "WAIT": do_wait, "STOP": do_stop,
               "GOTO": do_goto, "FOR": do_for, "NEXT": do_next,
               "IF": do_if, "NOT": do_not, "LET": do_let,
               "END": do_end, "COM$": do_com}

    # ------------------------------------------------ 実行

    def statement(self):
        self.charge()
        m = self.match(HEAD)
        if not m:
            raise PcError(1)
        if m.group("rem"):                    # . 以降は読まない
            self.pos = len(self.text())
        elif m.group("word"):
            act = self.ACTIONS.get(m.group("word"))
            if act is None:
                raise PcError(1)
            act(self)
        else:
            self.mem[self.addr(m.group("var"), m.group("idx"))] = self.expr()

    def skip_to_not(self):
        """IFが偽のとき。NOTがあればそこから、無ければ次の行へ"""
        i = self.text().find("NOT", self.pos)
        if i < 0:
            self.li, self.pos, self.state = self.li + 1, 0, True
        else:
            self.pos, self.state = i + 3, True

    def run(self):
        """走らせて (終わりかた, エラー番号, 行番号) を返す"""
        try:
            while True:
                if self.li >= len(self.lines):
                    return "END", 0, 0
                if not self.state:
                    self.skip_to_not()
                elif self.match(EOL):
                    self.li, self.pos = self.li + 1, 0
                else:
                    self.err_line = self.lines[self.li][0]
                    self.statement()
        except Halt as e:
            return e.why, 0, 0
        except PcError as e:
            return "ERROR", e.code, self.err_line
        except (IndexError, ValueError, KeyError):
            return "ERROR", 1, self.err_line
