import os
import requests
from flask import Flask, request

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")

CHANNEL_USERNAME = "@bonusgrew"

API = f"https://api.telegram.org/bot{BOT_TOKEN}"


def telegram(method, data=None):

    try:

        response = requests.post(
            f"{API}/{method}",
            data=data or {},
            timeout=30
        )

        print("Telegram status:", response.status_code)
        print("Telegram response:", response.text)

        return response.json()

    except Exception as error:

        print("Telegram error:", error)

        return {
            "ok": False,
            "error": str(error)
        }


def send_message(chat_id, text, keyboard=None):

    data = {
        "chat_id": chat_id,
        "text": text
    }

    if keyboard is not None:
        data["reply_markup"] = keyboard

    return telegram(
        "sendMessage",
        data
    )


def check_subscription(user_id):

    result = telegram(
        "getChatMember",
        {
            "chat_id": CHANNEL_USERNAME,
            "user_id": user_id
        }
    )

    if not result.get("ok"):

        print("Ошибка проверки подписки")

        return False

    status = result["result"]["status"]

    print("Статус пользователя:", status)

    return status in [
        "member",
        "administrator",
        "creator"
    ]


def start_command(chat_id):

    keyboard = {
        "inline_keyboard": [

            [
                {
                    "text": "📢 Подписаться на канал",
                    "url": "https://t.me/bonusgrew"
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
        "🤖 Полезные инструменты прямо "
        "в Telegram.\n\n"
        "Для получения бесплатного доступа "
        "подпишись на наш канал "
        "@bonusgrew.\n\n"
        "После подписки нажми "
        "«✅ Проверить подписку».",

        keyboard
    )


@app.route("/webhook", methods=["POST"])
def webhook():

    print("!!! QEVRA WEBHOOK STARTED !!!", flush=True)

    update = request.get_json()

    print("UPDATE:", update, flush=True)
    print("")
    print("========================")
    print("🔥 WEBHOOK RECEIVED")
    print("========================")

    update = request.get_json(silent=True)

    print("UPDATE:")
    print(update)

    if not update:
        return "OK"

    if "message" in update:

        print("MESSAGE FOUND", flush=True)

        message = update["message"]

        chat_id = message["chat"]["id"]

        text = message.get("text", "")

        print("CHAT ID:", chat_id, flush=True)
        print("TEXT:", text, flush=True)

        if text == "/start":

            print("START DETECTED", flush=True)

            send_message(
                chat_id,
                "👋 Привет! Я QEVRA 🚀\n\n"
                "Бот снова работает!"
            )

            print("MESSAGE SENT", flush=True)

        message = update["message"]

        chat_id = message["chat"]["id"]

        user_id = message["from"]["id"]

        text = message.get("text", "")

        print("CHAT ID:", chat_id)
        print("USER ID:", user_id)
        print("TEXT:", text)

        if text == "/start":

            print("🔥 START COMMAND")

            start_command(chat_id)

        elif "photo" in message:

            print("📸 Получено фото")

            if check_subscription(user_id):

                send_message(
                    chat_id,

                    "✅ Доступ подтверждён!\n\n"
                    "📸 Я получил твоё фото.\n\n"
                    "Функцию распознавания текста "
                    "подключим следующим этапом."
                )

            else:

                send_message(
                    chat_id,

                    "❌ Доступ закрыт.\n\n"
                    "Сначала подпишись на канал "
                    "@bonusgrew и нажми "
                    "«Проверить подписку»."
                )

    if "callback_query" in update:

        callback = update["callback_query"]

        callback_id = callback["id"]

        user_id = callback["from"]["id"]

        chat_id = callback["message"]["chat"]["id"]

        callback_data = callback["data"]

        print("BUTTON:", callback_data)

        if callback_data == "check_subscription":

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

                    "🎉 Отлично!\n\n"
                    "Подписка подтверждена.\n\n"
                    "Теперь выбери инструмент:",

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
                    "Подпишись на @bonusgrew "
                    "и нажми кнопку ещё раз."
                )

    return "OK"


@app.route("/", methods=["GET"])
def home():

    return "QEVRA is alive! 🚀"


if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            10000
        )
    )

    print("🚀 QEVRA запускается...")

    app.run(
        host="0.0.0.0",
        port=port
    )
