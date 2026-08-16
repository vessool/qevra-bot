import os
import requests
from flask import Flask, request

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")

API = f"https://api.telegram.org/bot{BOT_TOKEN}"


def send_message(chat_id, text, keyboard=None):

    data = {
        "chat_id": chat_id,
        "text": text
    }

    if keyboard:
        data["reply_markup"] = keyboard

    response = requests.post(
        f"{API}/sendMessage",
        data=data,
        timeout=30
    )

    print(response.status_code)
    print(response.text)

    return response.json()

    response = requests.post(
        f"{API}/sendMessage",
        data={
            "chat_id": chat_id,
            "text": text
        },
        timeout=30
    )

    print(response.status_code)
    print(response.text)

    return response.json()


@app.route("/", methods=["GET"])
def home():
    return "QEVRA is alive!"


@app.route("/webhook", methods=["POST"])
def webhook():

    print("WEBHOOK RECEIVED")

    update = request.get_json()

    print(update)

    if "message" in update:

        message = update["message"]

        chat_id = message["chat"]["id"]

        text = message.get("text", "")

        if text == "/start":

    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": "📢 Наш канал",
                    "url": "https://t.me/ТУТ_USERNAME_КАНАЛА"
                }
            ]
        ]
    }

    send_message(
        chat_id,

        "👋 Привет! Я QEVRA.\n\n"
        "Бот работает! 🚀\n\n"
        "Здесь скоро появятся полезные инструменты.",

        keyboard
    )

    return "OK"


if __name__ == "__main__":

    port = int(os.environ.get("PORT", 10000))

    app.run(
        host="0.0.0.0",
        port=port
    )
