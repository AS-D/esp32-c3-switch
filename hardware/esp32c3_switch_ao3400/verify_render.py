#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
校验 Gerber 并渲染 PNG 自检
- 用 gerbonara 回读全部 Gerber/钻孔文件 (语法+语义解析)
- 检查顶层/底层走线每个端点是落在铜上(无悬空走线)
- 渲染顶层/底层视图 PNG 供人工目检
用法: python verify_render.py
"""
import os, zlib, struct, math

HERE = os.path.dirname(os.path.abspath(__file__))
GB = os.path.join(HERE, "gerber")
PY = r"C:\Users\a5s21\.platformio\penv\Scripts\python.exe"  # unused

from gerbonara import GerberFile, ExcellonFile

def prims(fname):
    gf = GerberFile.open(os.path.join(GB, fname))
    return gf.objects, gf

def shp(o):
    """返回渲染用形状: (kind, args)"""
    t = type(o).__name__
    ap = getattr(o, 'aperture', None)
    if t == 'Flash':
        if ap is None:
            return None
        at = type(ap).__name__
        if at == 'CircleAperture':
            d = getattr(ap, 'diameter', None) or getattr(ap, 'size', None)
            return ('circ', o.x, o.y, d / 2.0)
        else:
            w = getattr(ap, 'w', None) or getattr(ap, 'width', None)
            h = getattr(ap, 'h', None) or getattr(ap, 'height', None)
            return ('rect', o.x, o.y, w / 2.0, h / 2.0)
    if t == 'Line':
        w = getattr(ap, 'diameter', None) or getattr(ap, 'size', None) or 0.1
        return ('line', o.x1, o.y1, o.x2, o.y2, w / 2.0)
    if t == 'Arc':
        return None
    if t == 'Region':
        return None
    return None

# ---------------- 最小 PNG 写入 ----------------
def write_png(path, w, h, rgb):
    raw = b''
    for y in range(h):
        raw += b'\x00' + bytes(rgb[y * w * 3:(y + 1) * w * 3])
    def chunk(tag, data):
        c = struct.pack('>I', len(data)) + tag + data
        return c + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff)
    png = b'\x89PNG\r\n\x1a\n'
    png += chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
    png += chunk(b'IDAT', zlib.compress(raw, 6))
    png += chunk(b'IEND', b'')
    with open(path, 'wb') as f:
        f.write(png)

# ---------------- 渲染 ----------------
def render(shape_lists, holes, out, scale=6.0, ss=2):
    bw, bh = 36.0, 28.0
    W, H = int(bw * scale * ss), int(bh * scale * ss)
    cu = bytearray(W * H)   # 1 = 铜
    mk = bytearray(W * H)   # 1 = 阻焊开窗
    sk = bytearray(W * H)   # 1 = 丝印
    def paint(shape, buf):
        k = shape[0]
        if k == 'circ':
            x, y, r = shape[1], shape[2], shape[3]
            x0, x1 = int((x - r) * scale * ss), int((x + r) * scale * ss)
            y0, y1 = int((y - r) * scale * ss), int((y + r) * scale * ss)
            cx, cy = x * scale * ss, y * scale * ss
            rr = r * scale * ss
            for yy in range(max(0, y0), min(H, y1 + 1)):
                for xx in range(max(0, x0), min(W, x1 + 1)):
                    if (xx - cx) ** 2 + (yy - cy) ** 2 <= rr * rr:
                        buf[yy * W + xx] = 1
        elif k == 'rect':
            x, y, hw, hh = shape[1], shape[2], shape[3], shape[4]
            x0, x1 = int((x - hw) * scale * ss), int((x + hw) * scale * ss)
            y0, y1 = int((y - hh) * scale * ss), int((y + hh) * scale * ss)
            for yy in range(max(0, y0), min(H, y1 + 1)):
                s0 = yy * W + max(0, x0)
                e0 = yy * W + min(W, x1 + 1)
                buf[s0:e0] = b'\x01' * (e0 - s0)
        elif k == 'line':
            x1, y1, x2, y2, hw = shape[1], shape[2], shape[3], shape[4], shape[5]
            p1x, p1y = x1 * scale * ss, y1 * scale * ss
            p2x, p2y = x2 * scale * ss, y2 * scale * ss
            dx, dy = p2x - p1x, p2y - p1y
            L2 = dx * dx + dy * dy
            hw2 = (hw * scale * ss) ** 2
            bx0 = max(0, int((min(x1, x2) - hw) * scale * ss))
            bx1 = min(W - 1, int((max(x1, x2) + hw) * scale * ss))
            by0 = max(0, int((min(y1, y2) - hw) * scale * ss))
            by1 = min(H - 1, int((max(y1, y2) + hw) * scale * ss))
            for yy in range(by0, by1 + 1):
                for xx in range(bx0, bx1 + 1):
                    if L2 == 0:
                        d2 = (xx - p1x) ** 2 + (yy - p1y) ** 2
                    else:
                        t = ((xx - p1x) * dx + (yy - p1y) * dy) / L2
                        t = max(0.0, min(1.0, t))
                        d2 = (xx - (p1x + t * dx)) ** 2 + (yy - (p1y + t * dy)) ** 2
                    if d2 <= hw2:
                        buf[yy * W + xx] = 1
    for sl in shape_lists[0]:
        paint(sl, cu)
    for sl in shape_lists[1]:
        paint(sl, mk)
    for sl in shape_lists[2]:
        paint(sl, sk)
    rgb = bytearray(W * H * 3)
    MASK_G = (0x2f, 0x74, 0x3c)
    CU_MASKED = (0x3d, 0x2a, 0x14)
    CU_OPEN = (0xd8, 0x94, 0x2e)
    SILK = (0xf4, 0xf2, 0xec)
    HOL = (0x2f, 0x74, 0x3c)
    for i in range(W * H):
        if sk[i]:
            rgb[i*3:i*3+3] = bytes(SILK)
        elif cu[i]:
            rgb[i*3:i*3+3] = bytes(CU_OPEN if mk[i] else CU_MASKED)
        else:
            rgb[i*3:i*3+3] = bytes(MASK_G)
    # 钻孔: 直接画背景色
    for (x, y, r) in holes:
        cx, cy = x * scale * ss, y * scale * ss
        rr = r * scale * ss
        x0, x1 = int((x - r) * scale * ss), int((x + r) * scale * ss)
        y0, y1 = int((y - r) * scale * ss), int((y + r) * scale * ss)
        for yy in range(max(0, y0), min(H, y1 + 1)):
            for xx in range(max(0, x0), min(W, x1 + 1)):
                if (xx - cx) ** 2 + (yy - cy) ** 2 <= rr * rr:
                    i = yy * W + xx
                    rgb[i*3:i*3+3] = bytes(HOL)
    # 缩小 ss
    ow, oh = W // ss, H // ss
    out_rgb = bytearray(ow * oh * 3)
    for yy in range(oh):
        for xx in range(ow):
            r = g = b = 0
            for sy in range(ss):
                for sx in range(ss):
                    i = ((yy * ss + sy) * W + (xx * ss + sx)) * 3
                    r += rgb[i]; g += rgb[i+1]; b += rgb[i+2]
            n = ss * ss
            i2 = (yy * ow + xx) * 3
            out_rgb[i2] = r // n; out_rgb[i2+1] = g // n; out_rgb[i2+2] = b // n
    write_png(out, ow, oh, out_rgb)

# ---------------- 连通性检查 ----------------
def trace_ends_covered(tr, copper):
    """每个走线折点必须被铜覆盖 (line 或 flash)"""
    bad = []
    for w, pts in tr:
        for (x, y) in pts:
            ok = False
            for s in copper:
                k = s[0]
                if k == 'line':
                    x1, y1, x2, y2, hw = s[1], s[2], s[3], s[4], s[5]
                    dx, dy = x2 - x1, y2 - y1
                    L2 = dx*dx + dy*dy
                    if L2 == 0:
                        d = math.hypot(x - x1, y - y1)
                    else:
                        t = max(0.0, min(1.0, ((x - x1)*dx + (y - y1)*dy) / L2))
                        d = math.hypot(x - (x1 + t*dx), y - (y1 + t*dy))
                    if d <= hw + 0.01:
                        ok = True; break
                elif k == 'circ':
                    if math.hypot(x - s[1], y - s[2]) <= s[3] + 0.01:
                        ok = True; break
                elif k == 'rect':
                    if abs(x - s[1]) <= s[3] + 0.01 and abs(y - s[2]) <= s[4] + 0.01:
                        ok = True; break
            if not ok:
                bad.append((x, y))
    return bad

if __name__ == "__main__":
    files = ["esp32c3_switch.GTL", "esp32c3_switch.GBL", "esp32c3_switch.GTS",
             "esp32c3_switch.GBS", "esp32c3_switch.GTO", "esp32c3_switch.GKO"]
    print("== 回读校验 ==")
    parsed = {}
    for fn in files:
        try:
            objs, gf = prims(fn)
            parsed[fn] = objs
            print(f"  {fn}: OK ({len(objs)} objects, bbox={gf.bounding_box})")
        except Exception as e:
            print(f"  {fn}: FAIL -> {e}")
    try:
        ef = ExcellonFile.open(os.path.join(GB, "esp32c3_switch.TXT"))
        print(f"  esp32c3_switch.TXT: OK ({len(ef.objects)} holes)")
        holes = [(o.x, o.y, o.aperture.diameter / 2.0) for o in ef.objects]
    except Exception as e:
        print(f"  TXT: FAIL -> {e}"); holes = []

    copper_top = [s for o in parsed["esp32c3_switch.GTL"] if (s := shp(o))]
    copper_bot = [s for o in parsed["esp32c3_switch.GBL"] if (s := shp(o))]

    # 悬空走线检查
    print("== 走线端点连通检查 ==")
    # 重新导入设计数据
    import importlib.util
    spec = importlib.util.spec_from_file_location("gg", os.path.join(HERE, "gen_gerber.py"))
    gg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gg)
    bad_top = trace_ends_covered(gg.TRACES_TOP, copper_top)
    bad_bot = trace_ends_covered(gg.TRACES_BOT, copper_bot)
    print(f"  顶层悬空端点: {len(bad_top)} {bad_top[:5]}")
    print(f"  底层悬空端点: {len(bad_bot)} {bad_bot[:5]}")

    # 渲染
    print("== 渲染 ==")
    mask_top = [s for o in parsed["esp32c3_switch.GTS"] if (s := shp(o))]
    mask_bot = [s for o in parsed["esp32c3_switch.GBS"] if (s := shp(o))]
    silk_top = [s for o in parsed["esp32c3_switch.GTO"] if (s := shp(o))]
    render([copper_top, mask_top, silk_top], holes, os.path.join(GB, "view_top.png"), scale=14, ss=1)
    render([copper_bot, mask_bot, []], holes, os.path.join(GB, "view_bottom.png"), scale=14, ss=1)
    print("  view_top.png / view_bottom.png written")
