import os
import requests
from flask import Flask, request

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_USERNAME = os.environ.get("CHANNEL_USERNAME")

API = f"https://api.telegram.org/bot{BOT_TOKEN}"


def telegram(method, data=None):

    response = requests.post(
        f"{API}/{method}",
        data=data or {},
        timeout=30
    )

    print("Telegram:", response.status_code, response.text)

    return response.json()


def send_message(chat_id, text, keyboard=None):

    data = {
        "chat_id": chat_id,
        "text": text
    }

    if keyboard:
        data["reply_markup"] = keyboard

    return telegram("sendMessage", data)


def check_subscription(user_id):

    result = telegram(
        "getChatMember",
        {
            "chat_id": CHANNEL_USERNAME,
            "user_id": user_id
        }
    )

    if not result.get("ok"):
        return False

    status = result["result"]["status"]

    return status in [
        "member",
        "administrator",
        "creator"
    ]


def start_message(chat_id):

    keyboard = {
        "inline_keyboard": [

            [
                {
                    "text": "📢 Подписаться",
                    "url": f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}"
                }
            ],

            [
                {
                    "text": "✅ Проверить подписку",
                    "callback_data": "check_subscription"
                }
            ]

        ]
    }

    send_message(
        chat_id,

        "👋 Привет!\n\n"

        "Я — QEVRA.\n\n"

        "🤖 Полезные AI-инструменты "
        "прямо в Telegram.\n\n"

        "Для бесплатного доступа "
        "подпишись на наш канал.\n\n"

        "После подписки нажми "
        "«Проверить подписку».",

        keyboard
    )


@app.route("/", methods=["GET"])
def home():

    return "QEVRA is alive!"


@app.route("/webhook", methods=["POST"])
def webhook():

    print("🔥 WEBHOOK")

    update = request.get_json()

    print(update)

    # =========================
    # СООБЩЕНИЕ
    # =========================

    if "message" in update:

        message = update["message"]

        chat_id = message["chat"]["id"]

        text = message.get("text", "")

        print("TEXT:", text)

        if text == "/start":

            start_message(chat_id)

        elif "photo" in message:

            user_id = message["from"]["id"]

            if check_subscription(user_id):

                send_message(
                    chat_id,

                    "✅ Доступ подтверждён!\n\n"

                    "📸 Фото получено!\n\n"

                    "Скоро я смогу распознать "
                    "текст с этого изображения."
                )

            else:

                send_message(
                    chat_id,

                    "❌ Доступ закрыт.\n\n"

                    "Сначала подпишись на канал "
                    "и нажми «Проверить подписку»."
                )

    # =========================
    # НАЖАТИЕ КНОПКИ
    # =========================

    if "callback_query" in update:

        callback = update["callback_query"]

        callback_id = callback["id"]

        user_id = callback["from"]["id"]

        chat_id = callback["message"]["chat"]["id"]

        data = callback["data"]

        if data == "check_subscription":

            subscribed = check_subscription(user_id)

            if subscribed:

                telegram(
                    "answerCallbackQuery",
                    {
                        "callback_query_id": callback_id,
                        "text": "✅ Подписка подтверждена!"
                    }
                )

                keyboard = {
                    "inline_keyboard": [

                        [
                            {
                                "text": "📸 Распознать фото",
                                "callback_data": "ocr"
                            }
                        ]

                    ]
                }

                send_message(
                    chat_id,

                    "🎉 Доступ открыт!\n\n"

                    "Выбери инструмент:",

                    keyboard
                )

            else:

                telegram(
                    "answerCallbackQuery",
                    {
                        "callback_query_id": callback_id,
                        "text": "❌ Подписка не найдена"
                    }
                )

                send_message(
                    chat_id,

                    "❌ Я не вижу подписку.\n\n"

                    "Подпишись на канал и "
                    "нажми кнопку ещё раз."
                )

    return "OK"


if __name__ == "__main__":

    port = int(os.environ.get("PORT", 10000))

    app.run(
        host="0.0.0.0",
        port=port
    )
