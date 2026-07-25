import time
import uuid

import cv2
import requests


API_BASE_URL = "https://robot-app-1047763414877.europe-west1.run.app"
SESSION_ID = f"pi5-{uuid.uuid4().hex[:10]}"
DETECTION_COOLDOWN_SECONDS = 30


def notify_backend():
    response = requests.post(
        f"{API_BASE_URL}/session/start",
        json={"session_id": SESSION_ID},
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()
    print(data.get("answer", "Merhaba."))
    if data.get("audio_path"):
        print(f"Audio: {API_BASE_URL}{data['audio_path']}")


def main():
    hog = cv2.HOGDescriptor()
    hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

    camera = cv2.VideoCapture(0)
    if not camera.isOpened():
        raise RuntimeError("Kamera acilamadi.")

    last_detection_at = 0
    print(f"Session: {SESSION_ID}")

    try:
        while True:
            ok, frame = camera.read()
            if not ok:
                time.sleep(0.2)
                continue

            frame = cv2.resize(frame, (640, 360))
            boxes, _ = hog.detectMultiScale(
                frame,
                winStride=(8, 8),
                padding=(8, 8),
                scale=1.05,
            )

            now = time.time()
            if len(boxes) > 0 and now - last_detection_at > DETECTION_COOLDOWN_SECONDS:
                last_detection_at = now
                print("Kullanici algilandi.")
                try:
                    notify_backend()
                except Exception as exc:
                    print(f"Backend bildirimi basarisiz: {exc}")

            time.sleep(0.1)
    finally:
        camera.release()


if __name__ == "__main__":
    main()
