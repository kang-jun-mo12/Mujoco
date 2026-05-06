"""
Rubber Band Launcher Demo

Focus the "Controls" OpenCV window for keyboard input:
  W/S     - Pitch up/down
  A/D     - Yaw left/right
  Space   - Fire rubber band
  P       - Toggle aim-camera window
  Esc     - Quit

The MuJoCo viewer is intentionally view-only, so its built-in camera,
visualization, reset, and playback shortcuts remain untouched.
"""

import threading
import time

import cv2
import mujoco
import mujoco.viewer
import numpy as np

LAUNCH_SPEED = 12.0
YAW_STEP = np.deg2rad(1)
PITCH_STEP = np.deg2rad(1)
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
TARGET_FPS = 30
VIEW_MOVE_STEP = 0.20
FIRST_BOUNCE_HORIZONTAL_SCALE = 0.65
FIRST_BOUNCE_VERTICAL_SCALE = 0.25
FIRST_BOUNCE_ANGULAR_SCALE = 0.25

KEY_W = ord("w")
KEY_S = ord("s")
KEY_A = ord("a")
KEY_D = ord("d")
KEY_I = ord("i")
KEY_J = ord("j")
KEY_K = ord("k")
KEY_L = ord("l")
KEY_P = ord("p")
KEY_SPACE = 32
KEY_ESC = 27

model = mujoco.MjModel.from_xml_path("rubber_band_launcher.xml")
data = mujoco.MjData(model)


def jid(name):
    return mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name)


def sid(name):
    return mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, name)


def gid(name):
    return mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, name)


def cid(name):
    return mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_CAMERA, name)


yaw_jid = jid("yaw_joint")
pitch_jid = jid("pitch_joint")
rubber_jid = jid("rubber_joint")
muzzle_sid = sid("muzzle_site")
aim_cam_id = cid("aim_camera")
rubber_geom_ids = {gid("rb_1"), gid("rb_2"), gid("rb_3"), gid("rb_4")}
bounce_surface_ids = {gid("floor")}

yaw_target = 0.0
pitch_target = 0.0
viewer_lookat = np.array([0.0, 0.0, 0.35], dtype=float)
fire_count = 0
show_cam = False
bounce_contact_count = 0
bounce_contact_active = False
projectile_stopped_on_surface = False

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
    global bounce_contact_active, bounce_contact_count, fire_count, projectile_stopped_on_surface

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
    fire_count += 1


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
        elif key == KEY_I:
            viewer_lookat[0] += VIEW_MOVE_STEP
        elif key == KEY_K:
            viewer_lookat[0] -= VIEW_MOVE_STEP
        elif key == KEY_J:
            viewer_lookat[1] += VIEW_MOVE_STEP
        elif key == KEY_L:
            viewer_lookat[1] -= VIEW_MOVE_STEP
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
        shots = fire_count
        camera_on = show_cam

    img = np.full((254, 440, 3), (28, 30, 34), dtype=np.uint8)
    lines = [
        "Controls window focused",
        f"Yaw:   {yaw_deg:+7.1f} deg  target {target_yaw_deg:+7.1f}",
        f"Pitch: {pitch_deg:+7.1f} deg  target {target_pitch_deg:+7.1f}",
        f"View:  x {view_x:+5.1f}  y {view_y:+5.1f}  z {view_z:+5.1f}",
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

    lines = [
        f"Yaw:   {yaw_deg:+.1f} deg",
        f"Pitch: {pitch_deg:+.1f} deg",
        f"Shots: {shots}",
    ]
    for i, txt in enumerate(lines):
        cv2.putText(img, txt, (10, 24 + i * 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1, cv2.LINE_AA)
    return img


def ui_thread_fn():
    renderer = None
    interval = 1.0 / TARGET_FPS
    control_win = "Controls"
    aim_win = "Aim Camera"
    cv2.namedWindow(control_win, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(control_win, 440, 254)

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
            cv2.imshow(aim_win, draw_aim_hud(bgr))
        else:
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
    mujoco.mj_forward(model, data)
    place_projectile_at_muzzle()

threading.Thread(target=ui_thread_fn, daemon=True).start()

sim_steps_per_frame = max(1, int(round(1.0 / (TARGET_FPS * model.opt.timestep))))

with mujoco.viewer.launch_passive(model, data) as viewer:
    viewer.cam.lookat[:] = viewer_lookat
    viewer.cam.distance = 1.8
    viewer.cam.elevation = -20
    viewer.cam.azimuth = 135

    while viewer.is_running() and not quit_event.is_set():
        t0 = time.time()
        with data_lock:
            viewer.cam.lookat[:] = viewer_lookat
            for _ in range(sim_steps_per_frame):
                mujoco.mj_step(model, data)
                update_projectile_bounce_limit()
        viewer.sync()
        elapsed = time.time() - t0
        budget = 1.0 / TARGET_FPS
        if elapsed < budget:
            time.sleep(budget - elapsed)

quit_event.set()
cv2.destroyAllWindows()
