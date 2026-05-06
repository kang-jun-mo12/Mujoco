"""
Collect YOLO-to-aim training data from the MuJoCo conference room.

For each target position on the table, this script:
  1. Searches for a yaw/pitch pair that hits the target in simulation.
  2. Renders the barrel-mounted aim camera from nearby current poses.
  3. Runs the trained YOLO ONNX detector on the rendered frame.
  4. Writes bbox features and delta_yaw/delta_pitch labels to CSV.
"""

import argparse
import csv
import math
from pathlib import Path

import cv2
import mujoco
import numpy as np

MODEL_PATH = "conference_room_with_launcher.xml"
YOLO_MODEL_PATH = "yolo_model/target_yolo11s_640_best.onnx"
OUTPUT_PATH = "datasets/aim_training_data.csv"

CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
YOLO_INPUT_SIZE = 640
YOLO_CONF_THRESHOLD = 0.25
YOLO_NMS_THRESHOLD = 0.45
LAUNCH_SPEED = 12.0
GRAVITY = 9.81
TABLE_TARGET_Z = 0.805
TARGET_CENTER_Z_OFFSET = 0.070
SETTLE_STEPS = 30
FIRE_MAX_STEPS = 900

CAMERA_EXPOSURE = 0.96
CAMERA_BRIGHTNESS = 2.0
BLOOM_THRESHOLD = 210


def jid(model, name):
    return mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name)


def gid(model, name):
    return mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, name)


def sid(model, name):
    return mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, name)


def cid(model, name):
    return mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_CAMERA, name)


def bid(model, name):
    return mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, name)


def apply_webcam_room_look(bgr):
    img = bgr.astype(np.float32)
    img *= np.array([1.12, 1.05, 0.96], dtype=np.float32)
    img = img * CAMERA_EXPOSURE + CAMERA_BRIGHTNESS
    img = np.clip(img, 0, 255).astype(np.uint8)

    bright = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    bloom_mask = cv2.threshold(bright, BLOOM_THRESHOLD, 255, cv2.THRESH_BINARY)[1]
    bloom = cv2.GaussianBlur(cv2.bitwise_and(img, img, mask=bloom_mask), (0, 0), 8)
    img = cv2.addWeighted(img, 1.0, bloom, 0.22, 0)
    return cv2.GaussianBlur(img, (3, 3), 0.25)


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


class YoloTargetDetector:
    def __init__(self, model_path):
        self.net = cv2.dnn.readNetFromONNX(model_path)

    def detect(self, bgr):
        input_img, scale, pad_x, pad_y = letterbox_image(bgr)
        blob = cv2.dnn.blobFromImage(
            input_img,
            scalefactor=1.0 / 255.0,
            size=(YOLO_INPUT_SIZE, YOLO_INPUT_SIZE),
            swapRB=True,
            crop=False,
        )
        self.net.setInput(blob)
        output = self.net.forward()

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
            conf = float(pred[4])
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
            })
        detections.sort(key=lambda det: det["conf"], reverse=True)
        return detections


class AimDatasetCollector:
    def __init__(self):
        self.model = mujoco.MjModel.from_xml_path(MODEL_PATH)
        self.detector = YoloTargetDetector(YOLO_MODEL_PATH)
        self.renderer = mujoco.Renderer(self.model, height=CAMERA_HEIGHT, width=CAMERA_WIDTH)

        self.yaw_jid = jid(self.model, "yaw_joint")
        self.pitch_jid = jid(self.model, "pitch_joint")
        self.rubber_jid = jid(self.model, "rubber_joint")
        self.muzzle_sid = sid(self.model, "muzzle_site")
        self.aim_cam_id = cid(self.model, "aim_camera")
        self.target_bid = bid(self.model, "target_object")
        self.target_mocap_id = self.model.body_mocapid[self.target_bid]
        self.yaw_qadr = self.model.jnt_qposadr[self.yaw_jid]
        self.pitch_qadr = self.model.jnt_qposadr[self.pitch_jid]
        self.rubber_qadr = self.model.jnt_qposadr[self.rubber_jid]
        self.rubber_vadr = self.model.jnt_dofadr[self.rubber_jid]

        self.rubber_geom_ids = {gid(self.model, name) for name in ("rb_1", "rb_2", "rb_3", "rb_4")}
        self.target_geom_ids = {
            gid(self.model, "target_base_rect"),
            gid(self.model, "target_stem"),
            gid(self.model, "target_round_head"),
        }

    def set_pose(self, data, yaw, pitch, target_pos):
        data.mocap_pos[self.target_mocap_id] = target_pos
        data.qpos[self.yaw_qadr] = yaw
        data.qpos[self.pitch_qadr] = pitch
        data.ctrl[0] = yaw
        data.ctrl[1] = pitch
        mujoco.mj_forward(self.model, data)

    def muzzle_pose(self, data):
        mujoco.mj_kinematics(self.model, data)
        pos = data.site_xpos[self.muzzle_sid].copy()
        mat = data.site_xmat[self.muzzle_sid].reshape(3, 3)
        return pos, mat[:, 0].copy()

    def place_projectile_at_muzzle(self, data):
        pos, x_dir = self.muzzle_pose(data)
        data.qpos[self.rubber_qadr:self.rubber_qadr + 3] = pos
        data.qpos[self.rubber_qadr + 3:self.rubber_qadr + 7] = [1, 0, 0, 0]
        data.qvel[self.rubber_vadr:self.rubber_vadr + 3] = x_dir * LAUNCH_SPEED
        data.qvel[self.rubber_vadr + 3:self.rubber_vadr + 6] = 0
        mujoco.mj_forward(self.model, data)

    def contact_hit(self, data):
        for i in range(data.ncon):
            geom1 = data.contact[i].geom1
            geom2 = data.contact[i].geom2
            if geom1 in self.rubber_geom_ids and geom2 in self.target_geom_ids:
                return True
            if geom2 in self.rubber_geom_ids and geom1 in self.target_geom_ids:
                return True
        return False

    def simulate_fire_hit(self, target_pos, yaw, pitch):
        data = mujoco.MjData(self.model)
        self.set_pose(data, yaw, pitch, target_pos)
        for _ in range(SETTLE_STEPS):
            mujoco.mj_step(self.model, data)
        self.set_pose(data, yaw, pitch, target_pos)
        self.place_projectile_at_muzzle(data)

        for step in range(FIRE_MAX_STEPS):
            mujoco.mj_step(self.model, data)
            if self.contact_hit(data):
                return True, step * self.model.opt.timestep
        return False, None

    def render_detection(self, target_pos, yaw, pitch):
        data = mujoco.MjData(self.model)
        self.set_pose(data, yaw, pitch, target_pos)
        for _ in range(SETTLE_STEPS):
            mujoco.mj_step(self.model, data)
        self.set_pose(data, yaw, pitch, target_pos)

        self.renderer.update_scene(data, camera=self.aim_cam_id)
        rgb = self.renderer.render()
        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        bgr = apply_webcam_room_look(bgr)
        detections = self.detector.detect(bgr)
        return detections[0] if detections else None

    def estimate_hit_angles(self, target_pos):
        data = mujoco.MjData(self.model)
        self.set_pose(data, 0.0, 0.0, target_pos)
        muzzle_pos, _ = self.muzzle_pose(data)
        aim_pos = np.array(target_pos, dtype=float)
        aim_pos[2] += TARGET_CENTER_Z_OFFSET

        dx = aim_pos[0] - muzzle_pos[0]
        dy = aim_pos[1] - muzzle_pos[1]
        horizontal = math.hypot(dx, dy)
        yaw = math.atan2(dy, dx)

        dz = aim_pos[2] - muzzle_pos[2]
        v2 = LAUNCH_SPEED * LAUNCH_SPEED
        disc = v2 * v2 - GRAVITY * (GRAVITY * horizontal * horizontal + 2 * dz * v2)
        if disc < 0 or horizontal <= 1e-6:
            pitch = 0.0
        else:
            alpha = math.atan((v2 - math.sqrt(disc)) / (GRAVITY * horizontal))
            pitch = -alpha
        return yaw, pitch

    def find_hit_angles(self, target_pos, yaw_radius_deg, pitch_radius_deg, search_step_deg):
        yaw_est, pitch_est = self.estimate_hit_angles(target_pos)
        step = math.radians(search_step_deg)
        yaw_offsets = np.arange(-math.radians(yaw_radius_deg), math.radians(yaw_radius_deg) + step / 2, step)
        pitch_offsets = np.arange(-math.radians(pitch_radius_deg), math.radians(pitch_radius_deg) + step / 2, step)
        candidates = []
        for yaw_off in yaw_offsets:
            for pitch_off in pitch_offsets:
                candidates.append((abs(yaw_off) + abs(pitch_off), yaw_est + yaw_off, pitch_est + pitch_off))
        candidates.sort(key=lambda item: item[0])

        for _, yaw, pitch in candidates:
            hit, hit_time = self.simulate_fire_hit(target_pos, yaw, pitch)
            if hit:
                return yaw, pitch, hit_time
        return None, None, None


def frange(min_value, max_value, step):
    values = []
    value = min_value
    while value <= max_value + step * 0.5:
        values.append(round(value, 6))
        value += step
    return values


def parse_offsets(text):
    return [math.radians(float(item.strip())) for item in text.split(",") if item.strip()]


def make_row(target_pos, current_yaw, current_pitch, hit_yaw, hit_pitch, hit_time, detection):
    x1, y1, x2, y2 = detection["box"]
    bbox_w = x2 - x1
    bbox_h = y2 - y1
    bbox_cx = (x1 + x2) / 2
    bbox_cy = (y1 + y2) / 2
    err_x = bbox_cx - CAMERA_WIDTH / 2
    err_y = bbox_cy - CAMERA_HEIGHT / 2
    delta_yaw = hit_yaw - current_yaw
    delta_pitch = hit_pitch - current_pitch

    return {
        "target_x": target_pos[0],
        "target_y": target_pos[1],
        "target_z": target_pos[2],
        "bbox_x1": x1,
        "bbox_y1": y1,
        "bbox_x2": x2,
        "bbox_y2": y2,
        "bbox_cx": bbox_cx,
        "bbox_cy": bbox_cy,
        "bbox_w": bbox_w,
        "bbox_h": bbox_h,
        "bbox_area": bbox_w * bbox_h,
        "bbox_conf": detection["conf"],
        "norm_err_x": err_x / (CAMERA_WIDTH / 2),
        "norm_err_y": err_y / (CAMERA_HEIGHT / 2),
        "bbox_w_norm": bbox_w / CAMERA_WIDTH,
        "bbox_h_norm": bbox_h / CAMERA_HEIGHT,
        "bbox_area_norm": (bbox_w * bbox_h) / (CAMERA_WIDTH * CAMERA_HEIGHT),
        "current_yaw_rad": current_yaw,
        "current_pitch_rad": current_pitch,
        "current_yaw_deg": math.degrees(current_yaw),
        "current_pitch_deg": math.degrees(current_pitch),
        "hit_yaw_rad": hit_yaw,
        "hit_pitch_rad": hit_pitch,
        "hit_yaw_deg": math.degrees(hit_yaw),
        "hit_pitch_deg": math.degrees(hit_pitch),
        "delta_yaw_rad": delta_yaw,
        "delta_pitch_rad": delta_pitch,
        "delta_yaw_deg": math.degrees(delta_yaw),
        "delta_pitch_deg": math.degrees(delta_pitch),
        "hit_time_sec": hit_time,
        "hit_success": 1,
    }


def build_arg_parser():
    parser = argparse.ArgumentParser(description="Collect YOLO bbox to aim-delta CSV data from MuJoCo.")
    parser.add_argument("--output", default=OUTPUT_PATH)
    parser.add_argument("--x-min", type=float, default=-1.8)
    parser.add_argument("--x-max", type=float, default=3.0)
    parser.add_argument("--y-min", type=float, default=-0.6)
    parser.add_argument("--y-max", type=float, default=0.6)
    parser.add_argument("--target-z", type=float, default=TABLE_TARGET_Z)
    parser.add_argument("--position-step", type=float, default=0.3)
    parser.add_argument("--current-yaw-offsets-deg", default="-4,-2,0,2,4")
    parser.add_argument("--current-pitch-offsets-deg", default="-3,0,3")
    parser.add_argument("--search-yaw-radius-deg", type=float, default=6.0)
    parser.add_argument("--search-pitch-radius-deg", type=float, default=8.0)
    parser.add_argument("--search-step-deg", type=float, default=1.0)
    parser.add_argument("--max-positions", type=int, default=0)
    return parser


def main():
    args = build_arg_parser().parse_args()
    collector = AimDatasetCollector()
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    x_values = frange(args.x_min, args.x_max, args.position_step)
    y_values = frange(args.y_min, args.y_max, args.position_step)
    yaw_offsets = parse_offsets(args.current_yaw_offsets_deg)
    pitch_offsets = parse_offsets(args.current_pitch_offsets_deg)
    fieldnames = list(make_row(
        np.array([0.0, 0.0, args.target_z]),
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        {"box": (0, 0, 1, 1), "conf": 1.0},
    ).keys())

    rows_written = 0
    positions_done = 0
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        f.flush()

        for x in x_values:
            for y in y_values:
                if args.max_positions and positions_done >= args.max_positions:
                    print(f"done: wrote {rows_written} rows to {output_path}")
                    return

                target_pos = np.array([x, y, args.target_z], dtype=float)
                hit_yaw, hit_pitch, hit_time = collector.find_hit_angles(
                    target_pos,
                    args.search_yaw_radius_deg,
                    args.search_pitch_radius_deg,
                    args.search_step_deg,
                )
                positions_done += 1
                if hit_yaw is None:
                    print(f"miss label: target=({x:.2f}, {y:.2f}, {args.target_z:.2f})", flush=True)
                    continue

                for yaw_offset in yaw_offsets:
                    for pitch_offset in pitch_offsets:
                        current_yaw = hit_yaw + yaw_offset
                        current_pitch = hit_pitch + pitch_offset
                        detection = collector.render_detection(target_pos, current_yaw, current_pitch)
                        if detection is None:
                            continue
                        writer.writerow(make_row(target_pos, current_yaw, current_pitch, hit_yaw, hit_pitch, hit_time, detection))
                        rows_written += 1

                f.flush()
                print(
                    f"target=({x:.2f}, {y:.2f}) hit yaw={math.degrees(hit_yaw):+.2f} "
                    f"pitch={math.degrees(hit_pitch):+.2f} rows={rows_written}",
                    flush=True,
                )

    print(f"done: wrote {rows_written} rows to {output_path}", flush=True)


if __name__ == "__main__":
    main()
