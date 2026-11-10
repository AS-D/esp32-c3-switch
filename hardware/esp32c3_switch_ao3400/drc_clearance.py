#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""同层最小间距 DRC-lite: 列出顶层/底层铜形状对之间 < 0.25mm 的最小间距(几何精确)"""
import os, math, importlib.util
from gerbonara import GerberFile

HERE = os.path.dirname(os.path.abspath(__file__))
GB = os.path.join(HERE, "gerber")
spec = importlib.util.spec_from_file_location("vr", os.path.join(HERE, "verify_render.py"))
vr = importlib.util.module_from_spec(spec); spec.loader.exec_module(vr)

def load(fn):
    gf = GerberFile.open(os.path.join(GB, fn))
    return [s for o in gf.objects if (s := vr.shp(o))]

def seg_dist(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    L2 = dx*dx + dy*dy
    if L2 == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1)*dx + (py - y1)*dy) / L2))
    return math.hypot(px - (x1 + t*dx), py - (y1 + t*dy))

def shape_dist(a, b):
    """两形状表面间距(近似: 点-点/点-线段 距离减去半径)"""
    def pts(s):
        k = s[0]
        if k == 'circ':
            return [('c', s[1], s[2], s[3])]
        if k == 'rect':
            x, y, hw, hh = s[1], s[2], s[3], s[4]
            return [('c', x - hw, y - hh, 0), ('c', x + hw, y - hh, 0),
                    ('c', x - hw, y + hh, 0), ('c', x + hw, y + hh, 0)]
        if k == 'line':
            return [('l', s[1], s[2], s[3], s[4], s[5])]
        return []
    best = 1e18
    for p in pts(a):
        for q in pts(b):
            if p[0] == 'c' and q[0] == 'c':
                d = math.hypot(p[1] - q[1], p[2] - q[2]) - p[3] - q[3]
            elif p[0] == 'c' and q[0] == 'l':
                d = seg_dist(p[1], p[2], q[1], q[2], q[3], q[4]) - p[3] - q[5]
            elif p[0] == 'l' and q[0] == 'c':
                d = seg_dist(q[1], q[2], p[1], p[2], p[3], p[4]) - q[3] - p[5]
            else:
                # 线-线: 用端点近似
                d = min(seg_dist(p[1], p[2], q[1], q[2], q[3], q[4]) - p[5] - q[5],
                        seg_dist(p[3], p[4], q[1], q[2], q[3], q[4]) - p[5] - q[5],
                        seg_dist(q[1], q[2], p[1], p[2], p[3], p[4]) - q[5] - p[5],
                        seg_dist(q[3], q[4], p[1], p[2], p[3], p[4]) - q[5] - p[5])
            if d < best:
                best = d
    return best

for fn in ("esp32c3_switch.GTL", "esp32c3_switch.GBL"):
    shapes = load(fn)
    print(f"== {fn}: {len(shapes)} 形状, 间距 <0.25mm 的对 ==")
    n = 0
    for i in range(len(shapes)):
        for j in range(i + 1, len(shapes)):
            d = shape_dist(shapes[i], shapes[j])
            if d < 0.25:
                n += 1
                print(f"  {shapes[i]} | {shapes[j]} -> {d:.3f}mm")
    if n == 0:
        print("  (无)")
