import os
import json
import requests
from flask import Flask, request

app = Flask(__name__)

# =========================
# НАСТРОЙКИ
# =========================

BOT_TOKEN = os.environ.get("BOT_TOKEN")

CHANNEL_USERNAME = "@bonusgrew"

API = f"https://api.telegram.org/bot{BOT_TOKEN}"


# =========================
# TELEGRAM API
# =========================

def telegram(method, data=None):

    try:

        response = requests.post(
            f"{API}/{method}",
            data=data or {},
            timeout=30
        )

        print(
            "Telegram:",
            method,
            response.status_code,
            response.text,
            flush=True
        )

        return response.json()

    except Exception as error:

        print(
            "Telegram ERROR:",
            error,
            flush=True
        )

        return {
            "ok": False
        }


# =========================
# ОТПРАВКА СООБЩЕНИЯ
# =========================

def send_message(chat_id, text, keyboard=None):

    data = {
        "chat_id": chat_id,
        "text": text
    }

    if keyboard is not None:
        data["reply_markup"] = json.dumps(keyboard)

    response = requests.post(
        f"{API}/sendMessage",
        data=data,
        timeout=30
    )

    print(
        "Telegram: sendMessage",
        response.status_code,
        response.text,
        flush=True
    )

    return response.json()

# =========================
# ПРОВЕРКА ПОДПИСКИ
# =========================

def check_subscription(user_id):

    print(
        "Проверяем подписку:",
        user_id,
        flush=True
    )

    result = telegram(
        "getChatMember",
        {
            "chat_id": CHANNEL_USERNAME,
            "user_id": user_id
        }
    )

    if not result.get("ok"):

        print(
            "Не удалось проверить подписку:",
            result,
            flush=True
        )

        return False

    status = result["result"]["status"]

    print(
        "Статус пользователя:",
        status,
        flush=True
    )

    return status in [
        "member",
        "administrator",
        "creator"
    ]


# =========================
# START
# =========================

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

        "👋 Привет! Я QEVRA 🚀\n\n"

        "Здесь будут полезные инструменты "
        "прямо в Telegram.\n\n"

        "Для получения доступа сначала "
        "подпишись на наш канал:\n"
        "@bonusgrew\n\n"

        "После подписки нажми "
        "«✅ Проверить подписку».",

        keyboard
    )


# =========================
# WEBHOOK
# =========================

@app.route(
    "/webhook",
    methods=["POST"]
)
def webhook():

    print(
        "!!! QEVRA WEBHOOK STARTED !!!",
        flush=True
    )

    update = request.get_json(
        silent=True
    )

    print(
        "UPDATE:",
        update,
        flush=True
    )

    if not update:

        return "OK"


    # =========================
    # СООБЩЕНИЯ
    # =========================

    if "message" in update:

        print(
            "MESSAGE FOUND",
            flush=True
        )

        message = update["message"]

        chat_id = message["chat"]["id"]

        user_id = message["from"]["id"]

        text = message.get(
            "text",
            ""
        )

        print(
            "CHAT ID:",
            chat_id,
            flush=True
        )

        print(
            "USER ID:",
            user_id,
            flush=True
        )

        print(
            "TEXT:",
            text,
            flush=True
        )


        # =========================
        # START
        # =========================

        if text == "/start":

            print(
                "START DETECTED",
                flush=True
            )

            start_command(
                chat_id
            )


    # =========================
    # КНОПКИ
    # =========================

    if "callback_query" in update:

        print(
            "CALLBACK FOUND",
            flush=True
        )

        callback = update["callback_query"]

        callback_id = callback["id"]

        user_id = callback["from"]["id"]

        chat_id = callback["message"]["chat"]["id"]

        callback_data = callback["data"]

        print(
            "CALLBACK DATA:",
            callback_data,
            flush=True
        )


        # =========================
        # ПРОВЕРКА ПОДПИСКИ
        # =========================

        if callback_data == "check_subscription":

            subscribed = check_subscription(
                user_id
            )


            # =========================
            # ПОДПИСКА ЕСТЬ
            # =========================

            if subscribed:

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
                    "Подписка подтверждена.\n\n"
                    "Теперь тебе доступен QEVRA."
                )


            # =========================
            # ПОДПИСКИ НЕТ
            # =========================

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

                    "❌ Я пока не вижу твою подписку.\n\n"
                    "Подпишись на @bonusgrew "
                    "и нажми кнопку проверки ещё раз."
                )


    return "OK"


# =========================
# ГЛАВНАЯ
# =========================

@app.route(
    "/",
    methods=["GET"]
)
def home():

    return "QEVRA is alive! 🚀"


# =========================
# ЗАПУСК
# =========================

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            10000
        )
    )

    print(
        "🚀 QEVRA запускается...",
        flush=True
    )

    app.run(
        host="0.0.0.0",
        port=port
    )
