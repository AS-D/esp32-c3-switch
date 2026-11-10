#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
网络连通性检查 (DRC-lite): 把顶层/底层铜光栅化成 0.1mm 网格做并查集,
验证:
  1. 同一网络的焊盘互相连通 (无开路)
  2. 不同网络互不连通 (无短路, VIN/VOUT+ 视为同一电源网络)
用法: python check_netlist.py
"""
import os, sys
import importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
GB = os.path.join(HERE, "gerber")

spec = importlib.util.spec_from_file_location("vr", os.path.join(HERE, "verify_render.py"))
vr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vr)

spec2 = importlib.util.spec_from_file_location("gg", os.path.join(HERE, "gen_gerber.py"))
gg = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(gg)

from gerbonara import GerberFile, ExcellonFile

SCALE = 10  # cells per mm -> 0.1mm grid
W, H = int(36 * SCALE), int(28 * SCALE)

# 归一化网络组: VOUT+ 与 VIN 同一电源
def group(net):
    return 'VIN' if net in ('VIN', 'VOUT+') else net

# --- 光栅化 ---
top = bytearray(W * H)
bot = bytearray(W * H)

def fill(buf, shapes):
    for s in shapes:
        k = s[0]
        if k == 'circ':
            x, y, r = s[1], s[2], s[3]
            x0, x1 = int((x - r) * SCALE), int((x + r) * SCALE)
            y0, y1 = int((y - r) * SCALE), int((y + r) * SCALE)
            cx, cy = x * SCALE, y * SCALE
            rr = r * SCALE
            for yy in range(max(0, y0), min(H, y1 + 1)):
                for xx in range(max(0, x0), min(W, x1 + 1)):
                    if (xx - cx) ** 2 + (yy - cy) ** 2 <= rr * rr:
                        buf[yy * W + xx] = 1
        elif k == 'rect':
            x, y, hw, hh = s[1], s[2], s[3], s[4]
            x0, x1 = int((x - hw) * SCALE), int((x + hw) * SCALE)
            y0, y1 = int((y - hh) * SCALE), int((y + hh) * SCALE)
            for yy in range(max(0, y0), min(H, y1 + 1)):
                s0 = yy * W + max(0, x0)
                e0 = yy * W + min(W, x1 + 1)
                buf[s0:e0] = b'\x01' * (e0 - s0)
        elif k == 'line':
            x1, y1, x2, y2, hw = s[1], s[2], s[3], s[4], s[5]
            p1x, p1y = x1 * SCALE, y1 * SCALE
            p2x, p2y = x2 * SCALE, y2 * SCALE
            dx, dy = p2x - p1x, p2y - p1y
            L2 = dx * dx + dy * dy
            hw2 = (hw * SCALE) ** 2
            bx0 = max(0, int((min(x1, x2) - hw) * SCALE))
            bx1 = min(W - 1, int((max(x1, x2) + hw) * SCALE))
            by0 = max(0, int((min(y1, y2) - hw) * SCALE))
            by1 = min(H - 1, int((max(y1, y2) + hw) * SCALE))
            for yy in range(by0, by1 + 1):
                for xx in range(bx0, bx1 + 1):
                    if L2 == 0:
                        d2 = (xx - p1x) ** 2 + (yy - p1y) ** 2
                    else:
                        t = max(0.0, min(1.0, ((xx - p1x) * dx + (yy - p1y) * dy) / L2))
                        d2 = (xx - (p1x + t * dx)) ** 2 + (yy - (p1y + t * dy)) ** 2
                    if d2 <= hw2:
                        buf[yy * W + xx] = 1

for fn, buf in (("esp32c3_switch.GTL", top), ("esp32c3_switch.GBL", bot)):
    gf = GerberFile.open(os.path.join(GB, fn))
    fill(buf, [s for o in gf.objects if (s := vr.shp(o))])

# --- 并查集 ---
parent = list(range(2 * W * H))
def find(a):
    while parent[a] != a:
        parent[a] = parent[parent[a]]
        a = parent[a]
    return a
def union(a, b):
    ra, rb = find(a), find(b)
    if ra != rb:
        parent[ra] = rb

def cell(buf, xx, yy):
    return buf[yy * W + xx]

for lay, buf in ((0, top), (1, bot)):
    for yy in range(H):
        for xx in range(W):
            if not cell(buf, xx, yy):
                continue
            idx = lay * W * H + yy * W + xx
            # 4 邻接 (边接触才算连通, 避免对角线角点误报)
            for dxx, dyy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = xx + dxx, yy + dyy
                if 0 <= nx < W and 0 <= ny < H and cell(buf, nx, ny):
                    union(idx, lay * W * H + ny * W + nx)

# 过孔: 环 (钻d/2..焊盘1.0/2) 连接上下层
def bridge_ring(x, y, r_out, r_in, label):
    cx, cy = x * SCALE, y * SCALE
    x0, x1 = int(x * SCALE - r_out), int(x * SCALE + r_out)
    y0, y1 = int(y * SCALE - r_out), int(y * SCALE + r_out)
    for yy in range(max(0, y0), min(H, y1 + 1)):
        for xx in range(max(0, x0), min(W, x1 + 1)):
            dd = (xx - cx) ** 2 + (yy - cy) ** 2
            if dd <= r_out * r_out and dd >= r_in * r_in:
                if cell(top, xx, yy) and cell(bot, xx, yy):
                    union(yy * W + xx, W * H + yy * W + xx)

for (x, y, _, d, _) in gg.VIAS:
    bridge_ring(x, y, 0.5 * SCALE, (d / 2) * SCALE, 'via')
# 通孔焊盘 (镀铜) 同样跨层
for p in gg.ALL_PADS:
    x, y, kind, sz = p[0][0], p[0][1], p[1], p[2]
    if kind == 'th':
        bridge_ring(x, y, (sz / 2) * SCALE, (p[4] / 2) * SCALE, 'th')

# --- 每个网络的焊盘锚点 ---
def anchor_cell(buf, x, y, kind, sz):
    """返回焊盘范围内离中心最近的铜格"""
    if kind == 'th':
        x0, x1 = int((x - sz/2) * SCALE), int((x + sz/2) * SCALE)
        y0, y1 = int((y - sz/2) * SCALE), int((y + sz/2) * SCALE)
        cx, cy = x * SCALE, y * SCALE
        best, bestd = None, 1e18
        for yy in range(y0, y1 + 1):
            for xx in range(x0, x1 + 1):
                if 0 <= xx < W and 0 <= yy < H and cell(buf, xx, yy):
                    d = (xx - cx) ** 2 + (yy - cy) ** 2
                    if d < bestd:
                        best, bestd = (yy * W + xx), d
        return best
    else:
        ix, iy = int(x * SCALE), int(y * SCALE)
        if 0 <= ix < W and 0 <= iy < H and cell(buf, ix, iy):
            return iy * W + ix
    return None

# 焊盘 -> 网络 (跳过 C1/J2 等在顶层的锚点; 通孔焊盘顶层锚)
anchors = {}
for ref, pads in gg.PADS.items():
    for p in pads:
        x, y, kind, sz, net = p[0][0], p[0][1], p[1], p[2], p[3]
        a = anchor_cell(top, x, y, kind, sz)
        if a is not None:
            anchors.setdefault(group(net), []).append(a)

# 每网络: 根集合; 网络间: 无共享根
roots = {}
for net, alist in anchors.items():
    rs = {find(a) for a in alist}
    roots[net] = rs
    print(f"net {net}: {len(alist)} pads -> {len(rs)} 根")

ok = True
# 网络内连通
for net, rs in roots.items():
    if len(rs) > 1:
        print(f"  [开路!] {net} 有 {len(rs)} 个独立根")
        ok = False
# 网络间隔离
allr = {}
for net, rs in roots.items():
    for r in rs:
        if r in allr:
            print(f"  [短路!] {net} 与 {allr[r]} 共享铜区")
            ok = False
        allr[r] = net
print("== 结果:", "PASS 无开路无短路" if ok else "FAIL 存在问题 ==")
report = ["== 网络连通性检查 =="]
for net, rs in roots.items():
    report.append(f"net {net}: {len(rs)} 根 {'OK' if len(rs)==1 else '开路!'}")
report.append("短路检测: " + ("无" if len(allr) == len(set(allr)) else "存在!"))
report.append("结果: " + ("PASS" if ok else "FAIL"))
report.append("")
report.append("== 焊盘归属根明细 ==")
for ref, pads in gg.PADS.items():
    for p in pads:
        x, y, kind, sz, net = p[0][0], p[0][1], p[1], p[2], p[3]
        a = anchor_cell(top, x, y, kind, sz)
        r = find(a) if a is not None else None
        report.append(f"{ref} ({x:.2f},{y:.2f}) {net}: root={r}")
with open(os.path.join(GB, "netlist_report.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(report))
sys.exit(0 if ok else 1)
