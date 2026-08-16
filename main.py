import os
import requests
from flask import Flask, request

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL = os.environ.get("CHANNEL_USERNAME")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"


def telegram(method, data=None):
    url = f"{TELEGRAM_API}/{method}"

    response = requests.post(
        url,
        data=data or {},
        timeout=30
    )

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
            "chat_id": CHANNEL,
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


def start_bot(chat_id):

    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": "📢 Подписаться",
                    "url": f"https://t.me/{CHANNEL.lstrip('@')}"
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
        "Полезные AI-инструменты прямо в Telegram.\n\n"
        "Для бесплатного доступа подпишись "
        "на наш канал.\n\n"
        "После подписки нажми "
        "«Проверить подписку».",
        keyboard
    )


@app.route("/", methods=["GET"])
def home():

    return "QEVRA is alive!"


@app.route("/webhook", methods=["POST"])
def webhook():

    update = request.json

    # Пользователь написал сообщение
    if "message" in update:

        message = update["message"]

        chat_id = message["chat"]["id"]
        text = message.get("text", "")

        if text == "/start":

            start_bot(chat_id)

        elif "photo" in message:

            user_id = message["from"]["id"]

            if check_subscription(user_id):

                send_message(
                    chat_id,
                    "✅ Доступ подтверждён!\n\n"
                    "📸 Фото получено!\n\n"
                    "В следующей версии я смогу "
                    "распознавать текст с изображения."
                )

            else:

                send_message(
                    chat_id,
                    "❌ Сначала подпишись на наш канал.\n\n"
                    "После подписки нажми "
                    "«Проверить подписку»."
                )

    # Пользователь нажал кнопку
    if "callback_query" in update:

        callback = update["callback_query"]

        callback_id = callback["id"]
        user_id = callback["from"]["id"]
        chat_id = callback["message"]["chat"]["id"]

        if callback["data"] == "check_subscription":

            if check_subscription(user_id):

                telegram(
                    "answerCallbackQuery",
                    {
                        "callback_query_id": callback_id,
                        "text": "✅ Подписка подтверждена!"
                    }
                )

                send_message(
                    chat_id,
                    "🎉 Отлично!\n\n"
                    "Доступ открыт.\n\n"
                    "📸 Теперь отправь мне фотографию."
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
                    "❌ Я пока не вижу подписку.\n\n"
                    "Подпишись на канал и попробуй снова."
                )

    return "OK"


if __name__ == "__main__":

    port = int(os.environ.get("PORT", 10000))

    app.run(
        host="0.0.0.0",
        port=port
    )
