"""
Conference Room Rubber Band Launcher Demo

Focus the "Controls" OpenCV window for keyboard input:
  W/S     - Pitch up/down
  A/D     - Yaw left/right
  Space   - Fire rubber band
  P       - Toggle aim-camera window
  O       - Run iterative YOLO-to-aim correction
  Esc     - Quit

The MuJoCo viewer is intentionally view-only.
"""

import threading
import time

import cv2
import mujoco
import mujoco.viewer
import numpy as np

from aim_delta_model import AimDeltaModel

MODEL_PATH = "conference_room_with_launcher.xml"
YOLO_MODEL_PATH = "yolo_model/target_yolo11s_640_best.onnx"
YOLO_CLASSES_PATH = "yolo_model/classes.txt"
AIM_MODEL_PATH = "models/aim_delta_ridge_5cm.npz"

LAUNCH_SPEED = 12.0
YAW_STEP = np.deg2rad(1)
PITCH_STEP = np.deg2rad(1)
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
TARGET_FPS = 30
YOLO_INPUT_SIZE = 640
YOLO_CONF_THRESHOLD = 0.25
YOLO_NMS_THRESHOLD = 0.45
YOLO_INFER_EVERY_N_FRAMES = 3
VIEW_MOVE_STEP = 0.20
TARGET_MOVE_STEP = 0.01
AUTO_AIM_ITERATIONS = 6
AUTO_AIM_SETTLE_STEPS = 25
AUTO_AIM_MIN_DELTA_DEG = 0.25
FIRST_BOUNCE_HORIZONTAL_SCALE = 0.65
FIRST_BOUNCE_VERTICAL_SCALE = 0.25
FIRST_BOUNCE_ANGULAR_SCALE = 0.25
HIT_EFFECT_DURATION = 0.75
HIT_EFFECT_RADIUS = 0.18
CAMERA_EXPOSURE = 0.96
CAMERA_BRIGHTNESS = 2.0
BLOOM_THRESHOLD = 210

KEY_W = ord("w")
KEY_S = ord("s")
KEY_A = ord("a")
KEY_D = ord("d")
KEY_F = ord("f")
KEY_G = ord("g")
KEY_H = ord("h")
KEY_I = ord("i")
KEY_J = ord("j")
KEY_K = ord("k")
KEY_L = ord("l")
KEY_O = ord("o")
KEY_P = ord("p")
KEY_T = ord("t")
KEY_SPACE = 32
KEY_ESC = 27

model = mujoco.MjModel.from_xml_path(MODEL_PATH)
data = mujoco.MjData(model)


def jid(name):
    return mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name)


def sid(name):
    return mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, name)


def gid(name):
    return mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, name)


def cid(name):
    return mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_CAMERA, name)


def bid(name):
    return mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, name)


yaw_jid = jid("yaw_joint")
pitch_jid = jid("pitch_joint")
rubber_jid = jid("rubber_joint")
muzzle_sid = sid("muzzle_site")
aim_cam_id = cid("aim_camera")
target_bid = bid("target_object")
target_mocap_id = model.body_mocapid[target_bid]
rubber_geom_ids = {gid("rb_1"), gid("rb_2"), gid("rb_3"), gid("rb_4")}
target_geom_ids = {gid("target_base_rect"), gid("target_stem"), gid("target_round_head")}
bounce_surface_ids = {gid("floor"), gid("long_table_top")}
hit_effect_bid = bid("hit_effect")
hit_effect_mocap_id = model.body_mocapid[hit_effect_bid]
hit_particle_geom_ids = [gid(f"hit_particle_{i}") for i in range(9)]
hit_particle_dirs = np.array([
    [0.00, 0.00, 1.00],
    [0.00, 1.00, 0.05],
    [0.00, -1.00, 0.05],
    [0.00, 0.72, 0.72],
    [0.00, -0.72, 0.72],
    [0.18, 0.55, 0.82],
    [0.18, -0.55, 0.82],
    [-0.18, 0.55, -0.18],
    [-0.18, -0.55, -0.18],
], dtype=float)
hit_particle_dirs /= np.linalg.norm(hit_particle_dirs, axis=1, keepdims=True)
hit_particle_base_rgba = model.geom_rgba[hit_particle_geom_ids].copy()

yaw_target = 0.0
pitch_target = 0.0
viewer_lookat = np.array([0.7, 0.0, 1.0], dtype=float)
target_pos = data.mocap_pos[target_mocap_id].copy()
fire_count = 0
show_cam = False
yolo_status = "idle"
yolo_detection_count = 0
yolo_center_error = None
last_yolo_detection = None
aim_delta_model = None
aim_model_status = "manual"
auto_aim_requested = False
bounce_contact_count = 0
bounce_contact_active = False
projectile_stopped_on_surface = False
target_contact_active = False
hit_effect_start_time = -1.0
hit_count = 0
hit_status = "waiting"
hit_status_until = 0.0

data_lock = threading.RLock()
quit_event = threading.Event()


def muzzle_pose():
    """Return the muzzle world position and barrel +X direction."""
    mujoco.mj_kinematics(model, data)
    pos = data.site_xpos[muzzle_sid].copy()
    mat = data.site_xmat[muzzle_sid].reshape(3, 3)
    return pos, mat[:, 0].copy()


def place_projectile_at_muzzle():
    pos, _ = muzzle_pose()
    qa = model.jnt_qposadr[rubber_jid]
    va = model.jnt_dofadr[rubber_jid]
    data.qpos[qa:qa + 3] = pos
    data.qpos[qa + 3:qa + 7] = [1, 0, 0, 0]
    data.qvel[va:va + 6] = 0
    mujoco.mj_forward(model, data)


def do_fire():
    global bounce_contact_active, bounce_contact_count, fire_count, projectile_stopped_on_surface, target_contact_active

    pos, x_dir = muzzle_pose()
    qa = model.jnt_qposadr[rubber_jid]
    va = model.jnt_dofadr[rubber_jid]
    data.qpos[qa:qa + 3] = pos
    data.qpos[qa + 3:qa + 7] = [1, 0, 0, 0]
    data.qvel[va:va + 3] = x_dir * LAUNCH_SPEED
    data.qvel[va + 3:va + 6] = 0
    mujoco.mj_forward(model, data)
    bounce_contact_count = 0
    bounce_contact_active = False
    projectile_stopped_on_surface = False
    target_contact_active = False
    fire_count += 1


def projectile_target_contact():
    for i in range(data.ncon):
        geom1 = data.contact[i].geom1
        geom2 = data.contact[i].geom2
        if geom1 in rubber_geom_ids and geom2 in target_geom_ids:
            return True, data.contact[i].pos.copy()
        if geom2 in rubber_geom_ids and geom1 in target_geom_ids:
            return True, data.contact[i].pos.copy()
    return False, None


def projectile_touching_bounce_surface():
    for i in range(data.ncon):
        geom1 = data.contact[i].geom1
        geom2 = data.contact[i].geom2
        if geom1 in rubber_geom_ids and geom2 in bounce_surface_ids:
            return True
        if geom2 in rubber_geom_ids and geom1 in bounce_surface_ids:
            return True
    return False


def stop_projectile_motion():
    va = model.jnt_dofadr[rubber_jid]
    data.qvel[va:va + 6] = 0


def damp_first_bounce():
    va = model.jnt_dofadr[rubber_jid]
    data.qvel[va:va + 2] *= FIRST_BOUNCE_HORIZONTAL_SCALE
    if data.qvel[va + 2] > 0:
        data.qvel[va + 2] *= FIRST_BOUNCE_VERTICAL_SCALE
    else:
        data.qvel[va + 2] *= FIRST_BOUNCE_HORIZONTAL_SCALE
    data.qvel[va + 3:va + 6] *= FIRST_BOUNCE_ANGULAR_SCALE


def update_projectile_bounce_limit():
    global bounce_contact_active, bounce_contact_count, projectile_stopped_on_surface

    if projectile_stopped_on_surface:
        stop_projectile_motion()
        return

    touching = projectile_touching_bounce_surface()
    if touching and not bounce_contact_active:
        bounce_contact_count += 1
        if bounce_contact_count == 1:
            damp_first_bounce()
        elif bounce_contact_count >= 2:
            stop_projectile_motion()
            projectile_stopped_on_surface = True
    bounce_contact_active = touching


def hide_hit_effect():
    global hit_effect_start_time

    hit_effect_start_time = -1.0
    data.mocap_pos[hit_effect_mocap_id] = [0, 0, -10]
    for i, geom_id in enumerate(hit_particle_geom_ids):
        model.geom_pos[geom_id] = 0
        rgba = hit_particle_base_rgba[i].copy()
        rgba[3] = 0
        model.geom_rgba[geom_id] = rgba
    mujoco.mj_forward(model, data)


def trigger_hit_effect(hit_pos):
    global hit_count, hit_effect_start_time, hit_status, hit_status_until

    data.mocap_pos[hit_effect_mocap_id] = hit_pos
    hit_effect_start_time = time.time()
    hit_count += 1
    hit_status = f"HIT! #{hit_count}"
    hit_status_until = hit_effect_start_time + 1.25
    for i, geom_id in enumerate(hit_particle_geom_ids):
        model.geom_pos[geom_id] = 0
        rgba = hit_particle_base_rgba[i].copy()
        rgba[3] = 1.0
        model.geom_rgba[geom_id] = rgba


def update_target_hit_detection():
    global target_contact_active

    touching, hit_pos = projectile_target_contact()
    if touching and not target_contact_active:
        trigger_hit_effect(hit_pos)
    target_contact_active = touching


def update_hit_effect_visual():
    if hit_effect_start_time < 0:
        return

    age = time.time() - hit_effect_start_time
    if age > HIT_EFFECT_DURATION:
        hide_hit_effect()
        return

    t = np.clip(age / HIT_EFFECT_DURATION, 0.0, 1.0)
    radius = HIT_EFFECT_RADIUS * (1.0 - (1.0 - t) * (1.0 - t))
    alpha = (1.0 - t) * (1.0 - t)
    for i, geom_id in enumerate(hit_particle_geom_ids):
        model.geom_pos[geom_id] = hit_particle_dirs[i] * radius
        rgba = hit_particle_base_rgba[i].copy()
        rgba[3] = alpha
        model.geom_rgba[geom_id] = rgba
    mujoco.mj_forward(model, data)


def load_aim_delta_model_once():
    global aim_delta_model, aim_model_status
    if aim_delta_model is not None:
        return aim_delta_model

    try:
        aim_delta_model = AimDeltaModel.load(AIM_MODEL_PATH)
        aim_model_status = f"loaded alpha {aim_delta_model.alpha:g}"
    except Exception as exc:
        aim_model_status = f"model error {type(exc).__name__}"
        aim_delta_model = None
    return aim_delta_model


def apply_auto_aim_delta_from_detection(detection):
    global aim_model_status, pitch_target, yaw_target

    model_obj = load_aim_delta_model_once()
    if model_obj is None:
        return None
    if detection is None:
        return None

    yaw_now = float(data.qpos[model.jnt_qposadr[yaw_jid]])
    pitch_now = float(data.qpos[model.jnt_qposadr[pitch_jid]])
    delta_yaw, delta_pitch = model_obj.predict_detection(detection, yaw_now, pitch_now)

    delta_yaw = float(np.clip(delta_yaw, np.deg2rad(-5), np.deg2rad(5)))
    delta_pitch = float(np.clip(delta_pitch, np.deg2rad(-4), np.deg2rad(4)))
    yaw_target = yaw_now + delta_yaw
    pitch_target = pitch_now + delta_pitch
    data.ctrl[0] = yaw_target
    data.ctrl[1] = pitch_target
    aim_model_status = f"dyaw {np.rad2deg(delta_yaw):+.2f} dpitch {np.rad2deg(delta_pitch):+.2f}"
    return delta_yaw, delta_pitch


def request_auto_aim():
    global aim_model_status, auto_aim_requested
    auto_aim_requested = True
    aim_model_status = "auto aim queued"


def render_aim_bgr(renderer):
    with data_lock:
        data.mocap_pos[target_mocap_id] = target_pos
        renderer.update_scene(data, camera=aim_cam_id)
        rgb = renderer.render()
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    return apply_webcam_room_look(bgr)


def settle_aim_control():
    with data_lock:
        data.mocap_pos[target_mocap_id] = target_pos
        for _ in range(AUTO_AIM_SETTLE_STEPS):
            mujoco.mj_step(model, data)
            update_projectile_bounce_limit()
            update_target_hit_detection()
        mujoco.mj_forward(model, data)


def run_auto_aim_sequence(renderer, yolo_net):
    global aim_model_status, auto_aim_requested

    auto_aim_requested = False
    if load_aim_delta_model_once() is None:
        return None, []

    latest_bgr = None
    latest_detections = []
    total_yaw = 0.0
    total_pitch = 0.0
    used_iterations = 0
    min_delta = np.deg2rad(AUTO_AIM_MIN_DELTA_DEG)

    for iteration in range(AUTO_AIM_ITERATIONS):
        latest_bgr = render_aim_bgr(renderer)
        latest_detections = run_yolo_inference(yolo_net, latest_bgr)
        best = best_detection(latest_detections)
        if best is None:
            set_yolo_status("no target", [])
            aim_model_status = f"auto stop {iteration}: no target"
            break

        with data_lock:
            result = apply_auto_aim_delta_from_detection(best)
        if result is None:
            break

        delta_yaw, delta_pitch = result
        total_yaw += delta_yaw
        total_pitch += delta_pitch
        used_iterations += 1
        set_yolo_status(f"{len(latest_detections)} target", latest_detections, None, best)

        if abs(delta_yaw) < min_delta and abs(delta_pitch) < min_delta:
            aim_model_status = (
                f"auto done {used_iterations}: "
                f"{np.rad2deg(total_yaw):+.2f}, {np.rad2deg(total_pitch):+.2f}"
            )
            break

        settle_aim_control()
    else:
        aim_model_status = (
            f"auto max {used_iterations}: "
            f"{np.rad2deg(total_yaw):+.2f}, {np.rad2deg(total_pitch):+.2f}"
        )

    latest_bgr = render_aim_bgr(renderer)
    latest_detections = run_yolo_inference(yolo_net, latest_bgr)
    best = best_detection(latest_detections)
    final_error = None
    if best is not None:
        x1, y1, x2, y2 = best["box"]
        final_error = ((x1 + x2) / 2 - CAMERA_WIDTH / 2, (y1 + y2) / 2 - CAMERA_HEIGHT / 2)
    set_yolo_status(
        f"{len(latest_detections)} target" if latest_detections else "no target",
        latest_detections,
        final_error,
        best,
    )
    return latest_bgr, latest_detections


def reject_auto_aim_without_camera():
    global aim_model_status, auto_aim_requested
    auto_aim_requested = False
    aim_model_status = "turn Aim Camera on"


def handle_key(raw_key):
    global yaw_target, pitch_target, show_cam

    key = raw_key & 0xFF
    if key in (255, 0xFF):
        return
    if ord("A") <= key <= ord("Z"):
        key += ord("a") - ord("A")

    with data_lock:
        if key == KEY_A:
            yaw_target += YAW_STEP
            data.ctrl[0] = yaw_target
        elif key == KEY_D:
            yaw_target -= YAW_STEP
            data.ctrl[0] = yaw_target
        elif key == KEY_W:
            pitch_target += PITCH_STEP
            data.ctrl[1] = pitch_target
        elif key == KEY_S:
            pitch_target -= PITCH_STEP
            data.ctrl[1] = pitch_target
        elif key == KEY_F:
            target_pos[1] += TARGET_MOVE_STEP
        elif key == KEY_H:
            target_pos[1] -= TARGET_MOVE_STEP
        elif key == KEY_T:
            target_pos[0] += TARGET_MOVE_STEP
        elif key == KEY_G:
            target_pos[0] -= TARGET_MOVE_STEP
        elif key == KEY_I:
            viewer_lookat[0] += VIEW_MOVE_STEP
        elif key == KEY_K:
            viewer_lookat[0] -= VIEW_MOVE_STEP
        elif key == KEY_J:
            viewer_lookat[1] += VIEW_MOVE_STEP
        elif key == KEY_L:
            viewer_lookat[1] -= VIEW_MOVE_STEP
        elif key == KEY_O:
            request_auto_aim()
        elif key == KEY_SPACE:
            do_fire()
        elif key == KEY_P:
            show_cam = not show_cam
        elif key == KEY_ESC:
            quit_event.set()


def draw_control_panel():
    with data_lock:
        yaw_deg = np.rad2deg(data.qpos[model.jnt_qposadr[yaw_jid]])
        pitch_deg = np.rad2deg(data.qpos[model.jnt_qposadr[pitch_jid]])
        target_yaw_deg = np.rad2deg(yaw_target)
        target_pitch_deg = np.rad2deg(pitch_target)
        view_x, view_y, view_z = viewer_lookat
        target_x, target_y, target_z = target_pos
        yolo_text = yolo_status
        aim_text = aim_model_status
        hit_text = hit_status if time.time() < hit_status_until else f"{hit_count} hits"
        if yolo_center_error is not None:
            err_x, err_y = yolo_center_error
            yolo_text = f"{yolo_status} dx {err_x:+.0f} dy {err_y:+.0f}"
        shots = fire_count
        camera_on = show_cam

    img = np.full((390, 480, 3), (28, 30, 34), dtype=np.uint8)
    lines = [
        "Controls window focused",
        f"Yaw:   {yaw_deg:+7.1f} deg  target {target_yaw_deg:+7.1f}",
        f"Pitch: {pitch_deg:+7.1f} deg  target {target_pitch_deg:+7.1f}",
        f"View:  x {view_x:+5.1f}  y {view_y:+5.1f}  z {view_z:+5.1f}",
        f"Target:x {target_x:+5.2f} y {target_y:+5.2f} z {target_z:+5.2f}",
        f"YOLO:  {yolo_text}",
        f"Aim:   {aim_text}",
        f"Hit:   {hit_text}",
        f"Shots: {shots}",
        f"Aim camera: {'ON' if camera_on else 'OFF'}",
    ]

    for i, txt in enumerate(lines):
        color = (210, 230, 255) if i == 0 else (180, 220, 180)
        cv2.putText(img, txt, (14, 34 + i * 34), cv2.FONT_HERSHEY_SIMPLEX, 0.62, color, 1, cv2.LINE_AA)
    return img


def draw_aim_hud(img):
    with data_lock:
        yaw_deg = np.rad2deg(data.qpos[model.jnt_qposadr[yaw_jid]])
        pitch_deg = np.rad2deg(data.qpos[model.jnt_qposadr[pitch_jid]])
        shots = fire_count
        show_hit = time.time() < hit_status_until
        hit_text = hit_status

    lines = [
        f"Yaw:   {yaw_deg:+.1f} deg",
        f"Pitch: {pitch_deg:+.1f} deg",
        f"Shots: {shots}",
    ]
    for i, txt in enumerate(lines):
        cv2.putText(img, txt, (10, 24 + i * 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1, cv2.LINE_AA)
    if show_hit:
        cv2.putText(img, hit_text, (CAMERA_WIDTH // 2 - 58, 72), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 240, 255), 3, cv2.LINE_AA)
    return img


def load_yolo_classes():
    try:
        with open(YOLO_CLASSES_PATH, "r", encoding="utf-8") as f:
            names = [line.strip() for line in f if line.strip()]
    except OSError:
        names = []
    return names or ["target"]


def letterbox_image(bgr, new_size=YOLO_INPUT_SIZE):
    h, w = bgr.shape[:2]
    scale = min(new_size / w, new_size / h)
    resized_w = int(round(w * scale))
    resized_h = int(round(h * scale))
    resized = cv2.resize(bgr, (resized_w, resized_h), interpolation=cv2.INTER_LINEAR)
    canvas = np.full((new_size, new_size, 3), 114, dtype=np.uint8)
    pad_x = (new_size - resized_w) // 2
    pad_y = (new_size - resized_h) // 2
    canvas[pad_y:pad_y + resized_h, pad_x:pad_x + resized_w] = resized
    return canvas, scale, pad_x, pad_y


def load_yolo_net():
    return cv2.dnn.readNetFromONNX(YOLO_MODEL_PATH)


def run_yolo_inference(net, bgr):
    input_img, scale, pad_x, pad_y = letterbox_image(bgr)
    blob = cv2.dnn.blobFromImage(input_img, scalefactor=1.0 / 255.0, size=(YOLO_INPUT_SIZE, YOLO_INPUT_SIZE), swapRB=True, crop=False)
    net.setInput(blob)
    output = net.forward()

    preds = np.squeeze(output)
    if preds.ndim == 2 and preds.shape[0] < preds.shape[1]:
        preds = preds.T

    boxes = []
    confidences = []
    frame_h, frame_w = bgr.shape[:2]

    for pred in preds:
        if pred.shape[0] < 5:
            continue
        cx, cy, bw, bh = pred[:4]
        class_scores = pred[4:]
        class_id = int(np.argmax(class_scores))
        conf = float(class_scores[class_id])
        if conf < YOLO_CONF_THRESHOLD:
            continue

        x1 = (cx - bw / 2 - pad_x) / scale
        y1 = (cy - bh / 2 - pad_y) / scale
        x2 = (cx + bw / 2 - pad_x) / scale
        y2 = (cy + bh / 2 - pad_y) / scale

        x1 = int(np.clip(x1, 0, frame_w - 1))
        y1 = int(np.clip(y1, 0, frame_h - 1))
        x2 = int(np.clip(x2, 0, frame_w - 1))
        y2 = int(np.clip(y2, 0, frame_h - 1))
        if x2 <= x1 or y2 <= y1:
            continue

        boxes.append([x1, y1, x2 - x1, y2 - y1])
        confidences.append(conf)

    keep = cv2.dnn.NMSBoxes(boxes, confidences, YOLO_CONF_THRESHOLD, YOLO_NMS_THRESHOLD)
    keep = np.array(keep).reshape(-1) if len(keep) else []
    detections = []
    for idx in keep:
        x, y, w, h = boxes[int(idx)]
        detections.append({
            "box": (x, y, x + w, y + h),
            "conf": confidences[int(idx)],
            "class_id": 0,
        })
    return detections


def best_detection(detections):
    best = None
    for det in detections:
        if best is None or det["conf"] > best["conf"]:
            best = det
    return best


def draw_yolo_detections(img, detections, class_names):
    h, w = img.shape[:2]
    cv2.drawMarker(img, (w // 2, h // 2), (255, 255, 255), cv2.MARKER_CROSS, 16, 1, cv2.LINE_AA)

    best = best_detection(detections)
    for det in detections:
        x1, y1, x2, y2 = det["box"]
        conf = det["conf"]
        label = class_names[det["class_id"]] if det["class_id"] < len(class_names) else "target"
        color = (70, 240, 90)
        cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
        cv2.putText(img, f"{label} {conf:.2f}", (x1, max(18, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2, cv2.LINE_AA)

    if best is None:
        return None, None

    x1, y1, x2, y2 = best["box"]
    cx = (x1 + x2) / 2
    cy = (y1 + y2) / 2
    err_x = cx - w / 2
    err_y = cy - h / 2
    cv2.circle(img, (int(cx), int(cy)), 4, (0, 255, 255), -1, cv2.LINE_AA)
    cv2.line(img, (w // 2, h // 2), (int(cx), int(cy)), (0, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(img, f"err {err_x:+.0f}, {err_y:+.0f}", (10, h - 16), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 1, cv2.LINE_AA)
    return (err_x, err_y), best


def set_yolo_status(status, detections=None, center_error=None, best=None):
    global last_yolo_detection, yolo_center_error, yolo_detection_count, yolo_status
    with data_lock:
        yolo_status = status
        yolo_detection_count = len(detections) if detections is not None else 0
        yolo_center_error = center_error
        if best is not None:
            last_yolo_detection = {
                "box": tuple(best["box"]),
                "conf": float(best["conf"]),
            }
        elif detections is not None and not detections:
            last_yolo_detection = None


def apply_webcam_room_look(bgr):
    """Approximate the cool, bright, slightly bloomed look of the reference camera."""
    img = bgr.astype(np.float32)
    img *= np.array([1.12, 1.05, 0.96], dtype=np.float32)
    img = img * CAMERA_EXPOSURE + CAMERA_BRIGHTNESS
    img = np.clip(img, 0, 255).astype(np.uint8)

    bright = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    bloom_mask = cv2.threshold(bright, BLOOM_THRESHOLD, 255, cv2.THRESH_BINARY)[1]
    bloom = cv2.GaussianBlur(cv2.bitwise_and(img, img, mask=bloom_mask), (0, 0), 8)
    img = cv2.addWeighted(img, 1.0, bloom, 0.22, 0)

    return cv2.GaussianBlur(img, (3, 3), 0.25)


def ui_thread_fn():
    renderer = None
    yolo_net = None
    yolo_classes = load_yolo_classes()
    yolo_detections = []
    frame_index = 0
    interval = 1.0 / TARGET_FPS
    control_win = "Controls"
    aim_win = "Aim Camera"
    cv2.namedWindow(control_win, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(control_win, 480, 390)

    while not quit_event.is_set():
        t0 = time.time()
        cv2.imshow(control_win, draw_control_panel())

        with data_lock:
            camera_on = show_cam
            if camera_on:
                if renderer is None:
                    renderer = mujoco.Renderer(model, height=CAMERA_HEIGHT, width=CAMERA_WIDTH)
                renderer.update_scene(data, camera=aim_cam_id)
                rgb = renderer.render()
            else:
                rgb = None

        if rgb is not None:
            bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
            bgr = apply_webcam_room_look(bgr)
            frame_index += 1
            if auto_aim_requested:
                try:
                    if yolo_net is None:
                        yolo_net = load_yolo_net()
                    auto_bgr, auto_detections = run_auto_aim_sequence(renderer, yolo_net)
                    if auto_bgr is not None:
                        bgr = auto_bgr
                        yolo_detections = auto_detections
                        frame_index = 0
                except Exception as exc:
                    yolo_detections = []
                    set_yolo_status(f"error: {type(exc).__name__}", [])
            if frame_index % YOLO_INFER_EVERY_N_FRAMES == 0:
                try:
                    if yolo_net is None:
                        yolo_net = load_yolo_net()
                    yolo_detections = run_yolo_inference(yolo_net, bgr)
                    status = f"{len(yolo_detections)} target" if yolo_detections else "no target"
                    set_yolo_status(status, yolo_detections)
                except Exception as exc:
                    yolo_detections = []
                    set_yolo_status(f"error: {type(exc).__name__}", [])
            center_error, best = draw_yolo_detections(bgr, yolo_detections, yolo_classes)
            if yolo_detections:
                set_yolo_status(f"{len(yolo_detections)} target", yolo_detections, center_error, best)
            cv2.imshow(aim_win, draw_aim_hud(bgr))
        else:
            if auto_aim_requested:
                reject_auto_aim_without_camera()
            set_yolo_status("idle", [])
            try:
                if cv2.getWindowProperty(aim_win, cv2.WND_PROP_VISIBLE) >= 1:
                    cv2.destroyWindow(aim_win)
            except Exception:
                pass

        handle_key(cv2.waitKey(1))

        elapsed = time.time() - t0
        if elapsed < interval:
            time.sleep(interval - elapsed)

    cv2.destroyAllWindows()


with data_lock:
    data.mocap_pos[target_mocap_id] = target_pos
    mujoco.mj_forward(model, data)
    place_projectile_at_muzzle()
    hide_hit_effect()

threading.Thread(target=ui_thread_fn, daemon=True).start()

sim_steps_per_frame = max(1, int(round(1.0 / (TARGET_FPS * model.opt.timestep))))

with mujoco.viewer.launch_passive(model, data) as viewer:
    viewer.cam.lookat[:] = viewer_lookat
    viewer.cam.distance = 7.0
    viewer.cam.elevation = -18
    viewer.cam.azimuth = 135

    while viewer.is_running() and not quit_event.is_set():
        t0 = time.time()
        with data_lock:
            viewer.cam.lookat[:] = viewer_lookat
            data.mocap_pos[target_mocap_id] = target_pos
            for _ in range(sim_steps_per_frame):
                mujoco.mj_step(model, data)
                update_projectile_bounce_limit()
                update_target_hit_detection()
            update_hit_effect_visual()
        viewer.sync()
        elapsed = time.time() - t0
        budget = 1.0 / TARGET_FPS
        if elapsed < budget:
            time.sleep(budget - elapsed)

quit_event.set()
cv2.destroyAllWindows()
