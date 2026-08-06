import os
import time
import uuid

import cv2
import requests


API_BASE_URL = os.getenv("ROBOT_API_BASE_URL", "https://robot-app-1047763414877.europe-west1.run.app")
SESSION_ID = os.getenv("ROBOT_SESSION_ID", f"pi5-{uuid.uuid4().hex[:10]}")
CAMERA_INDEX = int(os.getenv("ROBOT_CAMERA_INDEX", "0"))

DETECTION_COOLDOWN_SECONDS = float(os.getenv("ROBOT_DETECTION_COOLDOWN", "30"))
PERSON_CONFIRM_FRAMES = int(os.getenv("ROBOT_PERSON_CONFIRM_FRAMES", "2"))
MOTION_CONFIRM_FRAMES = int(os.getenv("ROBOT_MOTION_CONFIRM_FRAMES", "6"))
MOTION_AREA_THRESHOLD = int(os.getenv("ROBOT_MOTION_AREA_THRESHOLD", "9000"))
FRAME_WIDTH = int(os.getenv("ROBOT_FRAME_WIDTH", "640"))
FRAME_HEIGHT = int(os.getenv("ROBOT_FRAME_HEIGHT", "360"))
SHOW_PREVIEW = os.getenv("ROBOT_SHOW_PREVIEW", "0") == "1"


def notify_backend(detection_type: str):
    response = requests.post(
        f"{API_BASE_URL}/robot/presence",
        json={
            "session_id": SESSION_ID,
            "source": "raspberry-pi-5",
            "detection_type": detection_type,
        },
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()
    print(data.get("answer", "Merhaba."))
    if data.get("audio_path"):
        print(f"Audio: {API_BASE_URL}{data['audio_path']}")


def open_camera():
    camera = cv2.VideoCapture(CAMERA_INDEX)
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
    return camera


def main():
    hog = cv2.HOGDescriptor()
    hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
    motion_detector = cv2.createBackgroundSubtractorMOG2(
        history=80,
        varThreshold=45,
        detectShadows=True,
    )

    camera = open_camera()
    if not camera.isOpened():
        raise RuntimeError("Kamera acilamadi. Pi kamera icin libcamera/v4l2 ayarlarini kontrol edin.")

    last_detection_at = 0.0
    person_hits = 0
    motion_hits = 0
    frame_index = 0
    print(f"Session: {SESSION_ID}")
    print(f"API: {API_BASE_URL}")
    print("Algilama modu: once insan, insan bulunamazsa hareket yedegi")

    try:
        while True:
            ok, frame = camera.read()
            if not ok:
                time.sleep(0.2)
                continue

            frame = cv2.resize(frame, (FRAME_WIDTH, FRAME_HEIGHT))
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (7, 7), 0)

            motion_mask = motion_detector.apply(gray)
            motion_mask = cv2.threshold(motion_mask, 244, 255, cv2.THRESH_BINARY)[1]
            motion_mask = cv2.dilate(motion_mask, None, iterations=2)
            contours, _ = cv2.findContours(motion_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            motion_area = sum(cv2.contourArea(c) for c in contours)

            frame_index += 1
            person_detected = False
            boxes = []
            if frame_index % 3 == 0:
                boxes, _ = hog.detectMultiScale(
                    frame,
                    winStride=(8, 8),
                    padding=(8, 8),
                    scale=1.05,
                )
                person_detected = len(boxes) > 0

            person_hits = person_hits + 1 if person_detected else max(0, person_hits - 1)
            motion_hits = motion_hits + 1 if motion_area >= MOTION_AREA_THRESHOLD else max(0, motion_hits - 1)

            now = time.time()
            detection_type = ""
            if person_hits >= PERSON_CONFIRM_FRAMES:
                detection_type = "person"
            elif motion_hits >= MOTION_CONFIRM_FRAMES:
                detection_type = "motion"

            if detection_type and now - last_detection_at > DETECTION_COOLDOWN_SECONDS:
                last_detection_at = now
                person_hits = 0
                motion_hits = 0
                print(f"Algilama: {detection_type} | hareket alani: {int(motion_area)}")
                try:
                    notify_backend(detection_type)
                except Exception as exc:
                    print(f"Backend bildirimi basarisiz: {exc}")

            if SHOW_PREVIEW:
                for x, y, w, h in boxes:
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 180, 0), 2)
                cv2.putText(
                    frame,
                    f"motion={int(motion_area)} person_hits={person_hits} motion_hits={motion_hits}",
                    (12, 24),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    (255, 255, 255),
                    2,
                )
                cv2.imshow("Robot Presence", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            time.sleep(0.08)
    finally:
        camera.release()
        if SHOW_PREVIEW:
            cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
