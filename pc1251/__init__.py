"""PC-1251のシミュレータ。programs/ が使うのはここに出ている名前だけ。"""

from .buffer import CELL_W, CELLS, HEIGHT, WIDTH, Buffer, centered
from .machine import Machine

__all__ = ["Machine", "Buffer", "centered",
           "WIDTH", "HEIGHT", "CELLS", "CELL_W"]
