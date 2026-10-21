"""phone_stand.blend に CM 風アニメーションを追加するスクリプト.

折りたたみ状態 → 展開 しながら、カメラが製品の周りを回り込む 8 秒の映像を作る。
背景は白（床はシャドウキャッチャーで影だけ落ちる）。

使い方: phone_stand.blend を開いた状態で Scripting タブに貼り付けて「Run Script」。
何度実行しても作り直されるだけなので、数値を変えて再実行して OK。
レンダリングは「レンダー → アニメーションをレンダリング」（Ctrl+F12）。
"""
import math

import bpy
from mathutils import Vector

# ---------------------------------------------------------------- 設定
FPS = 30
DURATION = 8.0                 # 秒
RES = (1920, 1080)
SAMPLES = 64                   # 重い場合は 32 くらいまで下げる
OUTPUT = "//phone_stand_cm_"   # .blend と同じフォルダに mp4 を書き出す

FOLD = {"Hinge_Lower": 0.0, "Hinge_Upper": -180.0}     # 折りたたみ
OPEN = {"Hinge_Lower": 78.0, "Hinge_Upper": -133.0}    # 展開（スタンド状態）

# 展開のタイミング（秒）: アームが起き上がる → 少し遅れてホルダーが開く
ARM_MOVE = (1.0, 3.2)
HOLDER_MOVE = (2.2, 4.2)

# カメラ: 製品中心を周回する角度（度, 0 = 正面）と距離・高さ
ORBIT = [(0.0, -150.0), (DURATION, 25.0)]
DIST = [(0.0, 330.0), (DURATION, 270.0)]
HEIGHT = [(0.0, 170.0), (4.0, 95.0), (DURATION, 115.0)]
TARGET_Z = [(0.0, 8.0), (3.5, 34.0), (DURATION, 34.0)]
LENS = 50
F_STOP = 4.0

PREFIX = "CM_"


def frame(t):
    return 1 + round(t * FPS)


def key_angle(obj, deg, t):
    obj.rotation_euler.x = math.radians(deg)
    obj.keyframe_insert("rotation_euler", index=0, frame=frame(t))


def smooth_keys(obj):
    """全キーフレームを ease in/out のベジェにする."""
    ad = obj.animation_data
    if not ad or not ad.action:
        return
    for fc in _fcurves(ad):
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"
            kp.handle_left_type = kp.handle_right_type = "AUTO_CLAMPED"


def _fcurves(ad):
    # Blender 4.4 以降のレイヤー付きアクションと従来のアクションの両方に対応
    action = ad.action
    if hasattr(action, "fcurves") and len(action.fcurves):
        return list(action.fcurves)
    out = []
    for layer in getattr(action, "layers", []):
        for strip in layer.strips:
            bag = strip.channelbag(ad.action_slot) if hasattr(strip, "channelbag") else None
            if bag:
                out += list(bag.fcurves)
    return out


def cleanup():
    for o in [o for o in bpy.data.objects if o.name.startswith(PREFIX)]:
        bpy.data.objects.remove(o)
    for name in ("Hinge_Lower", "Hinge_Upper"):
        o = bpy.data.objects.get(name)
        if o and o.animation_data:
            o.animation_data_clear()


def new_obj(name, data=None, parent=None):
    o = bpy.data.objects.new(PREFIX + name, data)
    bpy.context.scene.collection.objects.link(o)
    o.parent = parent
    return o


def setup():
    scene = bpy.context.scene
    if "Hinge_Lower" not in bpy.data.objects:
        raise RuntimeError("phone_stand.blend を開いてから実行してください（Hinge_Lower が見つかりません）")
    cleanup()

    scene.render.fps = FPS
    scene.frame_start, scene.frame_end = 1, frame(DURATION)
    scene.frame_set(1)

    # --- ヒンジのアニメーション
    lower, upper = bpy.data.objects["Hinge_Lower"], bpy.data.objects["Hinge_Upper"]
    key_angle(lower, FOLD["Hinge_Lower"], ARM_MOVE[0])
    key_angle(lower, OPEN["Hinge_Lower"], ARM_MOVE[1])
    key_angle(upper, FOLD["Hinge_Upper"], HOLDER_MOVE[0])
    key_angle(upper, OPEN["Hinge_Upper"], HOLDER_MOVE[1])
    smooth_keys(lower)
    smooth_keys(upper)

    # --- カメラリグ: 中心の Empty を回転させ、カメラは注視点を追う
    target = new_obj("Target")
    target.location = (0, 40, TARGET_Z[0][1])
    for t, z in TARGET_Z:
        target.location.z = z
        target.keyframe_insert("location", index=2, frame=frame(t))
    smooth_keys(target)

    pivot = new_obj("Orbit")
    pivot.location = (0, 40, 0)
    for t, deg in ORBIT:
        pivot.rotation_euler.z = math.radians(deg)
        pivot.keyframe_insert("rotation_euler", index=2, frame=frame(t))
    smooth_keys(pivot)

    cam_data = bpy.data.cameras.new(PREFIX + "Camera")
    cam_data.lens = LENS
    cam_data.clip_start, cam_data.clip_end = 1, 10000
    cam_data.dof.use_dof = True
    cam_data.dof.focus_object = target
    cam_data.dof.aperture_fstop = F_STOP
    cam = new_obj("Camera", cam_data, pivot)
    # 正面（+Y 側）から見る位置が 0 度
    for t, d in DIST:
        cam.location.y = d
        cam.keyframe_insert("location", index=1, frame=frame(t))
    for t, h in HEIGHT:
        cam.location.z = h
        cam.keyframe_insert("location", index=2, frame=frame(t))
    smooth_keys(cam)
    track = cam.constraints.new("TRACK_TO")
    track.target = target
    track.track_axis, track.up_axis = "TRACK_NEGATIVE_Z", "UP_Y"
    scene.camera = cam

    # --- 白背景: カメラから見える背景は真っ白、反射用にはやや柔らかい白
    world = bpy.data.worlds.new(PREFIX + "World")
    scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    mix = nt.nodes.new("ShaderNodeMixShader")
    lp = nt.nodes.new("ShaderNodeLightPath")
    bg_cam = nt.nodes.new("ShaderNodeBackground")
    bg_cam.inputs["Strength"].default_value = 1.4  # 1 を超えた分は白に張り付く
    bg_env = nt.nodes.new("ShaderNodeBackground")
    bg_env.inputs["Strength"].default_value = 0.35
    nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs["Fac"])
    nt.links.new(bg_env.outputs["Background"], mix.inputs[1])
    nt.links.new(bg_cam.outputs["Background"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])

    # 床: 影だけを写すシャドウキャッチャー
    me = bpy.data.meshes.new(PREFIX + "Floor")
    s = 3000
    me.from_pydata([(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0)], [], [(0, 1, 2, 3)])
    floor = new_obj("Floor", me)
    floor.is_shadow_catcher = True

    # --- ライト: 大きなソフトボックス（キー）+ 背面のリム 2 灯
    def area(name, loc, energy, size, color=(1, 1, 1)):
        ld = bpy.data.lights.new(PREFIX + name, "AREA")
        ld.energy, ld.size, ld.color = energy, size, color
        lo = new_obj(name, ld)
        lo.location = loc
        lo.rotation_euler = (Vector((0, 40, 30)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()

    area("Key", (-180, 260, 260), 9e5, 220)
    area("Rim_L", (-220, -160, 140), 5e5, 120)
    area("Rim_R", (220, -120, 160), 5e5, 120)
    area("Top", (0, 40, 400), 3e5, 300)

    # --- レンダー設定
    r = scene.render
    scene.render.engine = "CYCLES"
    scene.cycles.samples = SAMPLES
    scene.cycles.use_denoising = True
    r.resolution_x, r.resolution_y = RES
    r.resolution_percentage = 100
    r.film_transparent = False
    # 白背景を白のまま出すため Standard 表示に
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    r.filepath = OUTPUT
    img = r.image_settings
    if hasattr(img, "media_type"):
        img.media_type = "VIDEO"
    img.file_format = "FFMPEG"
    r.ffmpeg.format = "MPEG4"
    r.ffmpeg.codec = "H264"
    r.ffmpeg.constant_rate_factor = "HIGH"

    scene.frame_set(1)


setup()
