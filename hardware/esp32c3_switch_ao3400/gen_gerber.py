#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ESP32-C3 ProMini 远程电源开关 —— AO3400 方案 嘉立创打板文件生成器

板子规格: 36 x 28 mm 双面板(FR-4, 1oz), 顶层走线 + 底层地线 + 丝印 + 阻焊 + 钻孔
输出: RS-274X Gerber (GTL/GBL/GTS/GBS/GTO/GBO/GKO) + Excellon 钻孔 (TXT)
用法: python gen_gerber.py
之后用同目录 verify_render.py 回读校验并渲染 PNG 自检。
"""
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gerber")
os.makedirs(OUT, exist_ok=True)

# ============ 板子参数 ============
BOARD_W, BOARD_H = 36.0, 28.0

# ============ 位号/器件/焊盘数据 ============
# (name, pads:[(x,y,kind,size,net)], extra)
# kind: th_c = 圆形通孔焊盘; smd_c = 圆形贴片; smd_r = 矩形贴片 (size=(w,h))
# 通孔焊盘额外: (x,y,'th',直径,'net', 钻径)
PADS = {
    # J1 输入端子 KF301-5.0 2P: P1=VIN+, P2=GND
    "J1": [((7.00, 7.00), 'th', 2.5, 'VIN', 1.6),
           ((12.08, 7.00), 'th', 2.5, 'GND', 1.6)],
    # J3 输出端子: P1=VOUT+ (常通5V), P2=VOUT- (MOS 开关)
    "J3": [((24.00, 7.00), 'th', 2.5, 'VOUT+', 1.6),
           ((29.08, 7.00), 'th', 2.5, 'OUT-', 1.6)],
    # J2 ESP32 接口 1x3 排针: 5V / GND / IO10
    "J2": [((7.00, 21.00), 'th', 1.5, 'VIN', 1.0),
           ((9.54, 21.00), 'th', 1.5, 'GND', 1.0),
           ((12.08, 21.00), 'th', 1.5, 'IO10', 1.0)],
    # Q1 AO3400 SOT-23: pin1=G(栅), pin2=S(源), pin3=D(漏)
    "Q1": [((19.025, 15.00), 'smd_r', (0.7, 1.0), 'GATE'),
           ((19.975, 15.00), 'smd_r', (0.7, 1.0), 'GND'),
           ((19.500, 17.50), 'smd_r', (0.7, 1.0), 'OUT-')],
    # R1 100Ω 栅极串联限流
    "R1": [((16.00, 15.00), 'smd_r', (0.8, 0.9), 'IO10'),
           ((17.00, 15.00), 'smd_r', (0.8, 0.9), 'GATE')],
    # R2 100kΩ 栅极下拉
    "R2": [((17.50, 13.50), 'smd_r', (0.8, 0.9), 'GATE'),
           ((18.50, 13.50), 'smd_r', (0.8, 0.9), 'GND')],
    # C2 0.1uF 高频滤波 (竖向, 焊盘间距 1.6mm 防反压短路)
    "C2": [((13.00, 10.50), 'smd_r', (0.8, 0.9), 'VIN'),
           ((13.00, 12.10), 'smd_r', (0.8, 0.9), 'GND')],
    # C1 220uF 电解 5mm 脚距 (右上角空区, 避开 VIN 干线)
    "C1": [((16.00, 24.50), 'th', 1.5, 'VIN', 0.9),
           ((21.00, 24.50), 'th', 1.5, 'GND', 0.9)],
}

# 过孔: (x, y, 焊盘直径, 钻孔直径, 网络)
VIAS = [
    (13.90, 12.10, 1.0, 0.5, 'GND'),   # C2- 下地
    (19.90, 13.50, 1.0, 0.5, 'GND'),   # R2-/Q1.S 下地
]

# 安装孔 (仅钻孔)
MOUNT = [(3.0, 3.0), (33.0, 3.0), (3.0, 25.0), (33.0, 25.0)]

# 顶层走线: (宽度, [(x,y)...])
TRACES_TOP = [
    (1.2, [(7.00, 7.00), (7.00, 21.00)]),   # VIN 左侧干线(经 J1.P1/J2.5V)
    (1.2, [(7.00, 10.00), (24.00, 10.00)]), # VIN 横干道(接 C2+/J3.P1; 跨过 C2+ 焊盘连接)
    (1.2, [(24.00, 10.00), (24.00, 7.00)]), # VIN 到 J3.P1
    (0.5, [(7.00, 21.00), (10.00, 23.50), (16.00, 24.50)]),  # VIN -> C1+ (电解)
    (0.5, [(12.08, 21.00), (16.00, 21.00), (16.00, 15.00)]),  # IO10 -> R1
    (0.5, [(17.00, 15.00), (19.025, 15.00)]),  # GATE: R1 -> Q1.G
    (0.5, [(17.50, 15.00), (17.50, 13.50)]),   # GATE: 分支到 R2
    (0.5, [(13.00, 12.10), (13.90, 12.10)]),   # C2- -> 过孔
    (0.5, [(18.50, 13.50), (19.90, 13.50)]),   # R2- -> 过孔
    (0.5, [(19.975, 15.00), (19.90, 13.50)]),  # Q1.S -> 过孔
    (1.2, [(19.50, 17.50), (22.00, 15.00), (29.08, 7.00)]),    # OUT-: Q1.D -> J3.P2 (弯折避开 Q1.S)
]

# 底层走线 (GND 干线, 1.0mm; 中段下行避让 J2.IO10 底环)
TRACES_BOT = [
    (1.0, [(12.08, 7.00), (9.54, 21.00), (13.90, 12.10),
           (19.90, 13.50), (21.00, 24.50)]),
]

# ============ 5x7 点阵字体 (用于丝印) ============
FONT = {
 '0': ['01110','10001','10011','10101','11001','10001','01110'],
 '1': ['00100','01100','00100','00100','00100','00100','01110'],
 '2': ['01110','10001','00001','00010','00100','01000','11111'],
 '3': ['11111','00010','00100','00010','00001','10001','01110'],
 '4': ['00010','00110','01010','10010','11111','00010','00010'],
 '5': ['11111','10000','11110','00001','00001','10001','01110'],
 '6': ['00110','01000','10000','11110','10001','10001','01110'],
 '7': ['11111','00001','00010','00100','01000','01000','01000'],
 '8': ['01110','10001','10001','01110','10001','10001','01110'],
 '9': ['01110','10001','10001','01111','00001','00010','01100'],
 'C': ['01110','10001','10000','10000','10000','10001','01110'],
 'D': ['11110','10001','10001','10001','10001','10001','11110'],
 'E': ['11111','10000','10000','11110','10000','10000','11111'],
 'G': ['01110','10001','10000','10111','10001','10001','01111'],
 'H': ['10001','10001','10001','11111','10001','10001','10001'],
 'I': ['01110','00100','00100','00100','00100','00100','01110'],
 'N': ['10001','11001','10101','10011','10001','10001','10001'],
 'O': ['01110','10001','10001','10001','10001','10001','01110'],
 'P': ['11110','10001','10001','11110','10000','10000','10000'],
 'Q': ['01110','10001','10001','10001','10101','10010','01101'],
 'R': ['11110','10001','10001','11110','10100','10010','10001'],
 'S': ['01111','10000','10000','01110','00001','00001','11110'],
 'T': ['11111','00100','00100','00100','00100','00100','00100'],
 'U': ['10001','10001','10001','10001','10001','10001','01110'],
 'V': ['10001','10001','10001','10001','10001','01010','00100'],
 'W': ['10001','10001','10001','10101','10101','10101','01010'],
 '+': ['00000','00100','00100','11111','00100','00100','00000'],
 '-': ['00000','00000','00000','11111','00000','00000','00000'],
 ' ': ['00000','00000','00000','00000','00000','00000','00000'],
}

# ============ Gerber 写入器 ============
class GW:
    def __init__(self, path, comment, polarity='D'):
        self.path = path
        self.lines = []
        self.aps = {}
        self.n = 10
        self.lines += ["%FSLAX46Y46*%", "%MOMM*%", f"G04 {comment}*",
                       f"%LP{polarity}*%"]
    def _ap(self, shape, w, h=None):
        key = (shape, round(w, 4), None if h is None else round(h, 4))
        if key in self.aps:
            return self.aps[key]
        self.n += 1
        if shape == 'C':
            self.lines.append(f"%ADD{self.n}C,{w:.3f}*%")
        else:
            self.lines.append(f"%ADD{self.n}R,{w:.3f}X{h:.3f}*%")
        self.aps[key] = self.n
        return self.n
    def line(self, x1, y1, x2, y2, w):
        a = self._ap('C', w)
        self.lines += [f"D{a}*", f"X{int(round(x1*1e6))}Y{int(round(y1*1e6))}D02*",
                       f"X{int(round(x2*1e6))}Y{int(round(y2*1e6))}D01*"]
    def poly(self, pts, w):
        a = self._ap('C', w)
        self.lines.append(f"D{a}*")
        x0, y0 = pts[0]
        self.lines.append(f"X{int(round(x0*1e6))}Y{int(round(y0*1e6))}D02*")
        for x, y in pts[1:]:
            self.lines.append(f"X{int(round(x*1e6))}Y{int(round(y*1e6))}D01*")
    def rect(self, x1, y1, x2, y2, w):
        self.poly([(x1, y1), (x2, y1), (x2, y2), (x1, y2), (x1, y1)], w)
    def flash(self, x, y, shape, w, h=None):
        a = self._ap(shape, w, h)
        self.lines += [f"D{a}*", f"X{int(round(x*1e6))}Y{int(round(y*1e6))}D03*"]
    def text(self, x, y, s, cell=0.3, size=0.25, adv=1.8):
        cx = x
        for ch in s:
            g = FONT.get(ch, FONT[' '])
            for r, row in enumerate(g):
                for c, bit in enumerate(row):
                    if bit == '1':
                        self.flash(cx + c*cell + cell/2, y + r*cell + cell/2,
                                   'R', size, size)
            cx += adv
    def save(self):
        self.lines.append("M02*")
        with open(self.path, 'w', encoding='ascii', newline='\n') as f:
            f.write("\n".join(self.lines) + "\n")

# ============ 顶层铜 + 底层铜 ============
ALL_PADS = [p for v in PADS.values() for p in v]

def gen_top():
    gw = GW(os.path.join(OUT, "esp32c3_switch.GTL"), "F.Cu")
    for p in ALL_PADS:
        x, y, kind, sz = p[0][0], p[0][1], p[1], p[2]
        if kind == 'th':
            gw.flash(x, y, 'C', sz)
        elif kind == 'smd_r':
            w, h = sz
            gw.flash(x, y, 'R', w, h)
    for (x, y, _, _, _) in VIAS:
        gw.flash(x, y, 'C', 1.0)
    for w, pts in TRACES_TOP:
        gw.poly(pts, w)
    gw.save()

def gen_bot():
    gw = GW(os.path.join(OUT, "esp32c3_switch.GBL"), "B.Cu")
    # 通孔焊盘底环 + 过孔底环
    for p in ALL_PADS:
        x, y, kind, sz = p[0][0], p[0][1], p[1], p[2]
        if kind == 'th':
            gw.flash(x, y, 'C', sz)
    for (x, y, _, _, _) in VIAS:
        gw.flash(x, y, 'C', 1.0)
    for w, pts in TRACES_BOT:
        gw.poly(pts, w)
    gw.save()

# ============ 阻焊 (LPC: 闪光处为开窗) ============
def gen_mask(fname, include_smd):
    gw = GW(os.path.join(OUT, fname), "soldermask", polarity='C')
    for p in ALL_PADS:
        x, y, kind, sz = p[0][0], p[0][1], p[1], p[2]
        if kind == 'th':
            gw.flash(x, y, 'C', sz + 0.4)      # 通孔开窗
        elif include_smd and kind == 'smd_r':
            w, h = sz
            gw.flash(x, y, 'R', w + 0.3, h + 0.3)
    for (x, y, _, _, _) in VIAS:
        gw.flash(x, y, 'C', 1.3)
    for (x, y) in MOUNT:
        gw.flash(x, y, 'C', 3.6)
    gw.save()

# ============ 丝印 ============
def gen_silk():
    gw = GW(os.path.join(OUT, "esp32c3_switch.GTO"), "F.SilkS")
    L = 0.2
    # 端子/排针外框
    gw.rect(4.8, 4.2, 14.3, 9.5, L)   # J1
    gw.rect(22.7, 4.2, 30.3, 9.5, L)  # J3
    gw.rect(4.8, 19.6, 13.6, 22.4, L) # J2
    gw.rect(18.4, 14.5, 20.4, 18.0, L) # Q1 本体
    # C1 电解极性标记 (右上角: 负号横杠)
    gw.line(19.6, 23.9, 22.4, 23.9, L)
    gw.line(21.0, 22.6, 21.0, 25.2, L)
    # 文字
    gw.text(9.5, 2.2, "IN")
    gw.text(7.0, 8.7, "+")
    gw.text(11.8, 8.7, "-")
    gw.text(26.5, 2.2, "OUT")
    gw.text(24.0, 8.7, "+")
    gw.text(28.8, 8.7, "-")
    gw.text(6.6, 23.0, "5V")
    gw.text(9.1, 23.0, "GND")
    gw.text(11.7, 23.0, "IO10")
    gw.text(7.0, 25.4, "ESP32")
    gw.text(16.5, 15.9, "R1")
    gw.text(18.0, 12.0, "R2")
    gw.text(11.4, 11.6, "C2")
    gw.text(13.8, 26.3, "C1")
    gw.text(19.5, 19.0, "Q1")
    gw.text(12.5, 1.2, "ESP32-C3 5V SWITCH")
    gw.save()

def gen_botsilk():
    gw = GW(os.path.join(OUT, "esp32c3_switch.GBO"), "B.SilkS")
    gw.save()

# ============ 板框 ============
def gen_edge():
    gw = GW(os.path.join(OUT, "esp32c3_switch.GKO"), "Edge.Cuts")
    gw.rect(0, 0, BOARD_W, BOARD_H, 0.1)
    gw.save()

# ============ 钻孔 (Excellon, 由 gerbonara 生成保证格式标准) ============
from gerbonara import ExcellonFile
from gerbonara.apertures import ExcellonTool
from gerbonara.graphic_objects import Flash

def gen_drill():
    path = os.path.join(OUT, "esp32c3_switch.TXT")
    tools = {}
    objs = []
    def add(x, y, d, plated=True):
        t = tools.get(d)
        if t is None:
            t = tools[d] = ExcellonTool(diameter=d, plated=plated, unit='mm')
        objs.append(Flash(x, y, t, unit='mm'))
    for p in ALL_PADS:
        x, y, kind = p[0][0], p[0][1], p[1]
        if kind == 'th':
            add(x, y, p[4])
    for (x, y) in MOUNT:
        add(x, y, 3.2, plated=False)      # 安装孔不镀铜
    for (x, y, _, d, _) in VIAS:
        add(x, y, d)
    ef = ExcellonFile(objects=objs, comments=["DRILL file generated by gen_gerber.py"])
    ef.save(path)
    print("drill written:", path)

if __name__ == "__main__":
    gen_top(); gen_bot()
    gen_mask("esp32c3_switch.GTS", True)
    gen_mask("esp32c3_switch.GBS", False)
    gen_silk(); gen_botsilk(); gen_edge(); gen_drill()
    print("generated:", sorted(os.listdir(OUT)))
