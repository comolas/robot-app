import time
import uuid

import requests
from gpiozero import Button


API_BASE_URL = "https://robot-app-1047763414877.europe-west1.run.app"
SESSION_ID = f"pi5-{uuid.uuid4().hex[:10]}"
TOUCH_GPIO_PIN = 17
TOUCH_COOLDOWN_SECONDS = 4


def notify_head_touch():
    response = requests.post(
        f"{API_BASE_URL}/robot/touch/head",
        json={"session_id": SESSION_ID},
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()
    print(data.get("answer", "Beni mutlu ettiniz. Tesekkur ederim."))
    print(f"Face state: {data.get('face_state', 'complimented')}")
    if data.get("audio_path"):
        print(f"Audio: {API_BASE_URL}{data['audio_path']}")


def main():
    touch = Button(TOUCH_GPIO_PIN, pull_up=False, bounce_time=0.15)
    last_touch_at = 0
    print(f"Session: {SESSION_ID}")
    print(f"Head touch sensor GPIO: {TOUCH_GPIO_PIN}")

    while True:
        touch.wait_for_press()
        now = time.time()
        if now - last_touch_at >= TOUCH_COOLDOWN_SECONDS:
            last_touch_at = now
            try:
                notify_head_touch()
            except Exception as exc:
                print(f"Head touch bildirimi basarisiz: {exc}")


if __name__ == "__main__":
    main()
