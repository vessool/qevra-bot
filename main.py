import os
import requests
from flask import Flask, request

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")

API = f"https://api.telegram.org/bot{BOT_TOKEN}"


def send_message(chat_id, text):

    print("STEP 3: отправляем сообщение")

    response = requests.post(
        f"{API}/sendMessage",
        data={
            "chat_id": chat_id,
            "text": text
        },
        timeout=30
    )

    print("STEP 4: Telegram ответил:")
    print(response.status_code)
    print(response.text)

    return response.json()


@app.route("/", methods=["GET"])
def home():

    return "QEVRA is alive!"


@app.route("/webhook", methods=["POST"])
def webhook():

    print("STEP 1: WEBHOOK ПОЛУЧЕН")

    update = request.get_json()

    print("UPDATE:")
    print(update)

    if not update:
        print("Нет данных")
        return "OK"

    if "message" in update:

        message = update["message"]

        chat_id = message["chat"]["id"]

        text = message.get("text", "")

        print("STEP 2: текст пользователя:", text)

        if text == "/start":

            print("STEP 2.1: НАЙДЕН /start")

            send_message(
                chat_id,
                "👋 Привет!\n\n"
                "Я — QEVRA.\n\n"
                "Бот работает! 🚀"
            )

    return "OK"


if __name__ == "__main__":

    port = int(os.environ.get("PORT", 10000))

    app.run(
        host="0.0.0.0",
        port=port
    )
