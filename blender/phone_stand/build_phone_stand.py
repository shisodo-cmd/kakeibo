"""折りたたみ式スマホスタンド（アルミ・3枚板 + 2ヒンジ）のモデリングスクリプト.

使い方:
  - Blender の Scripting タブで開いて「Run Script」
  - もしくは: blender -b -P build_phone_stand.py -- --out phone_stand.blend

単位は mm（Unit Scale = 0.001）。各パーツは
  Base → Hinge_Lower(Empty) → Arm → Hinge_Upper(Empty) → Holder
の親子構造になっているので、Hinge_* の X 回転で折りたたみ角度を変えられる。
"""
import math
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

# ---------------------------------------------------------------- 寸法 (mm)
T = 3.0              # 板厚
HINGE_R = 4.5        # ヒンジ筒の半径
HINGE_LEN = 62.0     # ヒンジ全長
KNUCKLE_OUT = 14.0   # 外側ナックルの長さ
KNUCKLE_GAP = 0.6    # ナックル間のすき間
FOOT_H = 0.8         # 底面ゴム足の高さ

BASE_W, BASE_L = 66.0, 72.0
ARM_W, ARM_L = 62.0, 88.0
HOLDER_W, HOLDER_L = 62.0, 76.0
HOOK_W = 16.0        # 先端フックの幅（脚の幅）
HOOK_SEAT = 10.0     # フックの受け面の奥行き
HOOK_LIP = 6.0       # フックの立ち上がり

ARM_ANGLE = 78.0     # 下ヒンジ: ベースに対するアームの角度
HOLDER_ANGLE = -133.0  # 上ヒンジ: アームに対するホルダーの角度

SEG = 24  # 円弧の分割数


# ---------------------------------------------------------------- 2D 形状ヘルパー
def arc(cx, cy, r, a0, a1, n=SEG):
    return [(cx + r * math.cos(a0 + (a1 - a0) * i / n),
             cy + r * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]


def fillet(poly, radii):
    """多角形 poly の各頂点を radii[i] の半径で角丸にする."""
    out = []
    n = len(poly)
    for i, p in enumerate(poly):
        r = radii[i] if isinstance(radii, (list, tuple)) else radii
        if r <= 0:
            out.append(p)
            continue
        p = Vector(p)
        a = (Vector(poly[i - 1]) - p).normalized()
        b = (Vector(poly[(i + 1) % n]) - p).normalized()
        half = a.angle(b) / 2
        d = r / math.tan(half)
        c = p + (a + b).normalized() * (r / math.sin(half))
        t0, t1 = p + a * d, p + b * d
        a0 = math.atan2(t0.y - c.y, t0.x - c.x)
        a1 = math.atan2(t1.y - c.y, t1.x - c.x)
        da = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
        out += arc(c.x, c.y, r, a0, a0 + da, 8)
    return out


def rounded_rect(cx, cy, w, h, r):
    x0, x1, y0, y1 = cx - w / 2, cx + w / 2, cy - h / 2, cy + h / 2
    return fillet([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], r)


def circle(cx, cy, r):
    return arc(cx, cy, r, 0, 2 * math.pi, 48)[:-1]


def arc_slot(cx, cy, r, span, w, mid):
    """中心 (cx,cy)、半径 r、中心角 mid±span の円弧状スロット."""
    a0, a1 = mid - span, mid + span
    pts = arc(cx, cy, r + w / 2, a0, a1)
    e1 = (cx + r * math.cos(a1), cy + r * math.sin(a1))
    pts += arc(*e1, w / 2, a1, a1 + math.pi, 10)[1:-1]
    pts += arc(cx, cy, r - w / 2, a1, a0)
    e0 = (cx + r * math.cos(a0), cy + r * math.sin(a0))
    pts += arc(*e0, w / 2, a0 + math.pi, a0 + 2 * math.pi, 10)[1:-1]
    return pts


# ---------------------------------------------------------------- Blender ヘルパー
def material(name, color, metallic, rough):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = rough
    return m


def plate(name, outline, holes, mat, z_off=0.0, bevel=0.35):
    """輪郭 + 穴のリストから板厚 T のプレートを作る（2D カーブを押し出してメッシュ化）."""
    cu = bpy.data.curves.new(name + "_curve", "CURVE")
    cu.dimensions = "2D"
    cu.fill_mode = "BOTH"
    cu.extrude = T / 2 - bevel
    cu.bevel_depth = bevel
    cu.bevel_resolution = 2
    cu.offset = 1 - bevel / 2  # ベベル分の外側への膨らみを打ち消す
    for loop in [outline] + holes:
        sp = cu.splines.new("POLY")
        sp.points.add(len(loop) - 1)
        for p, (x, y) in zip(sp.points, loop):
            p.co = (x, y, 0, 1)
        sp.use_cyclic_u = True
    tmp = bpy.data.objects.new(name + "_tmp", cu)
    bpy.context.scene.collection.objects.link(tmp)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(tmp.evaluated_get(dg))
    bpy.data.objects.remove(tmp)
    bpy.data.curves.remove(cu)
    me.transform(Matrix.Translation((0, 0, z_off)))
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    obj.data.materials.append(mat)
    for poly in me.polygons:
        poly.use_smooth = False
    return obj


def box(name, size, loc, mat, bevel=0.6):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=size, verts=bm.verts)
    bmesh.ops.translate(bm, vec=loc, verts=bm.verts)
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    obj.data.materials.append(mat)
    mod = obj.modifiers.new("Bevel", "BEVEL")
    mod.width, mod.segments = bevel, 3
    return obj


def cylinder_x(name, r, x0, x1, mat, y=0.0, z=0.0):
    """X 軸方向の円柱（ヒンジのナックル用）."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=40, radius1=r, radius2=r,
                          depth=x1 - x0)
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0),
                     matrix=Matrix.Rotation(math.pi / 2, 3, "Y"))
    bmesh.ops.translate(bm, vec=((x0 + x1) / 2, y, z), verts=bm.verts)
    for f in bm.faces:
        f.smooth = abs(f.normal.x) < 0.5
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    obj.data.materials.append(mat)
    mod = obj.modifiers.new("Bevel", "BEVEL")
    mod.width, mod.segments, mod.limit_method = 0.5, 3, "ANGLE"
    return obj


def cylinder_z(name, r, h, loc, mat):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=32, radius1=r, radius2=r, depth=h)
    bmesh.ops.translate(bm, vec=loc, verts=bm.verts)
    for f in bm.faces:
        f.smooth = abs(f.normal.z) < 0.5
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    obj.data.materials.append(mat)
    return obj


def knuckles(prefix, mat, outer):
    """ヒンジのナックル. outer=True なら両端2つ、False なら中央1つ."""
    h = HINGE_LEN / 2
    if outer:
        return [cylinder_x(prefix + "_L", HINGE_R, -h, -h + KNUCKLE_OUT, mat),
                cylinder_x(prefix + "_R", HINGE_R, h - KNUCKLE_OUT, h, mat)]
    return [cylinder_x(prefix + "_C", HINGE_R,
                       -h + KNUCKLE_OUT + KNUCKLE_GAP, h - KNUCKLE_OUT - KNUCKLE_GAP, mat)]


def link(objs, coll, parent=None):
    for o in objs:
        coll.objects.link(o)
        if parent is not None:
            o.parent = parent


# ---------------------------------------------------------------- 組み立て
def build():
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 0.001
    scene.unit_settings.length_unit = "MILLIMETERS"

    coll = bpy.data.collections.new("PhoneStand")
    scene.collection.children.link(coll)

    alu = material("Aluminium_Black", (0.018, 0.018, 0.02), 0.9, 0.42)
    hinge = material("Hinge_Black", (0.012, 0.012, 0.013), 0.6, 0.35)
    rubber = material("Rubber", (0.03, 0.03, 0.03), 0.0, 0.9)

    notch_w = HINGE_LEN - 2 * KNUCKLE_OUT + 1.0   # 相手側の中央ナックルが入る切り欠き幅
    tongue_w = HINGE_LEN - 2 * KNUCKLE_OUT - 2 * KNUCKLE_GAP - 1.0
    clear = HINGE_R + 0.8                          # ヒンジ軸からの逃げ

    # --- ベース（机に置く板）: ヒンジ軸が原点, +Y が手前
    bw, bl = BASE_W / 2, BASE_L
    nw = notch_w / 2
    base_outline = fillet(
        [(-bw, 0), (-nw, 0), (-nw, clear), (nw, clear), (nw, 0), (bw, 0), (bw, bl), (-bw, bl)],
        [1.5, 0, 1.0, 1.0, 0, 1.5, 9, 9])
    base_holes = [rounded_rect(0, 30, 15, 11, 5.4), rounded_rect(0, 52, 15, 11, 5.4)]
    base = plate("Base", base_outline, base_holes, alu, z_off=-HINGE_R + T / 2)
    base.location = (0, 0, HINGE_R + FOOT_H)
    link([base], coll)
    link(knuckles("Base_Knuckle", hinge, outer=True), coll, base)
    feet = [cylinder_z(f"Foot_{i}", 4.0, FOOT_H, (sx * (bw - 9), y, -HINGE_R - FOOT_H / 2), rubber)
            for i, (sx, y) in enumerate([(-1, 12), (1, 12), (-1, bl - 10), (1, bl - 10)])]
    link(feet, coll, base)

    # --- 下ヒンジ
    hl = bpy.data.objects.new("Hinge_Lower", None)
    hl.empty_display_type, hl.empty_display_size = "SINGLE_ARROW", 12
    hl.rotation_euler.x = math.radians(ARM_ANGLE)
    link([hl], coll, base)

    # --- アーム（中間の板）: 下ヒンジ軸が原点, +Y が上ヒンジ方向
    aw, al = ARM_W / 2, ARM_L
    tw = tongue_w / 2
    arm_outline = fillet(
        [(-tw, 0), (tw, 0), (tw, clear), (aw, clear), (aw, al - clear), (nw, al - clear),
         (nw, al), (-nw, al), (-nw, al - clear), (-aw, al - clear), (-aw, clear), (-tw, clear)],
        [0, 0, 1.0, 1.5, 1.5, 1.0, 0, 0, 1.0, 1.5, 1.5, 1.0])
    cy = al * 0.5
    arm_holes = [circle(0, cy, 11.5),
                 arc_slot(0, cy, 23.0, math.radians(36), 3.4, math.pi / 2),
                 arc_slot(0, cy, 23.0, math.radians(36), 3.4, -math.pi / 2)]
    # 折りたたみ時にホルダーと重ならないよう、アームはヒンジ筒の背面側に寄せる
    arm = plate("Arm", arm_outline, arm_holes, alu, z_off=HINGE_R - T / 2)
    link([arm], coll, hl)
    link(knuckles("Arm_Knuckle_Lower", hinge, outer=False), coll, arm)
    upper = knuckles("Arm_Knuckle_Upper", hinge, outer=True)
    for k in upper:
        k.location.y = al
    link(upper, coll, arm)
    stopper = cylinder_z("Arm_Stopper", 2.6, 0.6, (0, al - 17, HINGE_R + 0.3), rubber)
    link([stopper], coll, arm)

    # --- 上ヒンジ
    hu = bpy.data.objects.new("Hinge_Upper", None)
    hu.empty_display_type, hu.empty_display_size = "SINGLE_ARROW", 12
    hu.location = (0, al, 0)
    hu.rotation_euler.x = math.radians(HOLDER_ANGLE)
    link([hu], coll, arm)

    # --- ホルダー（スマホを載せる板）: 上ヒンジ軸が原点, +Y がフック方向, +Z がスマホ側
    hw, hl_ = HOLDER_W / 2, HOLDER_L
    leg_in = hw - HOOK_W
    holder_outline = fillet(
        [(-tw, 0), (tw, 0), (tw, clear), (hw, clear), (hw, hl_), (leg_in, hl_),
         (1.2, hl_ * 0.47), (-1.2, hl_ * 0.47), (-leg_in, hl_), (-hw, hl_), (-hw, clear), (-tw, clear)],
        [0, 0, 1.0, 1.5, 1.2, 1.2, 1.5, 1.5, 1.2, 1.2, 1.5, 1.0])
    holder = plate("Holder", holder_outline, [], alu)
    link([holder], coll, hu)
    link(knuckles("Holder_Knuckle", hinge, outer=False), coll, holder)

    # 先端フック（受け面 + 立ち上がり）とゴムパッド
    hooks = []
    for side, sx in (("L", -1), ("R", 1)):
        xc = sx * (hw - HOOK_W / 2)
        hooks.append(box(f"Hook_Seat_{side}", (HOOK_W, T, HOOK_SEAT + T / 2),
                         (xc, hl_ - T / 2, (HOOK_SEAT + T / 2) / 2), alu))
        hooks.append(box(f"Hook_Lip_{side}", (HOOK_W, HOOK_LIP, T),
                         (xc, hl_ - HOOK_LIP / 2, HOOK_SEAT), alu))
        hooks.append(box(f"Hook_Pad_{side}", (HOOK_W - 2, 0.8, HOOK_SEAT - T),
                         (xc, hl_ - T - 0.4, T / 2 + (HOOK_SEAT - T) / 2), rubber, bevel=0.3))
    link(hooks, coll, holder)

    return coll


def clear_scene():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    for c in list(bpy.data.collections):
        bpy.data.collections.remove(c)


if __name__ == "__main__":
    clear_scene()
    build()
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if "--out" in argv:
        bpy.ops.wm.save_as_mainfile(filepath=argv[argv.index("--out") + 1])
