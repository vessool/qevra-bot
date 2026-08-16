import os
import json
import requests

from flask import Flask, request

from PIL import Image, ImageEnhance, ImageFilter
import pytesseract

from io import BytesIO


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

        data["reply_markup"] = json.dumps(
            keyboard,
            ensure_ascii=False
        )

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
# СКАЧИВАНИЕ ФОТО ИЗ TELEGRAM
# =========================

def download_telegram_photo(file_id):

    print(
        "Получаем информацию о файле:",
        file_id,
        flush=True
    )

    result = telegram(
        "getFile",
        {
            "file_id": file_id
        }
    )

    if not result.get("ok"):

        print(
            "Не удалось получить файл:",
            result,
            flush=True
        )

        return None

    file_path = result["result"]["file_path"]

    file_url = (
        f"https://api.telegram.org/file/"
        f"bot{BOT_TOKEN}/{file_path}"
    )

    print(
        "Скачиваем:",
        file_path,
        flush=True
    )

    response = requests.get(
        file_url,
        timeout=60
    )

    if response.status_code != 200:

        print(
            "Ошибка скачивания:",
            response.status_code,
            flush=True
        )

        return None

    return response.content


# =========================
# OCR
# =========================

def recognize_text(image_bytes):

    try:

        image = Image.open(
            BytesIO(image_bytes)
        )

        print(
            "Размер изображения:",
            image.size,
            flush=True
        )

        # Переводим в RGB
        image = image.convert("RGB")

        # Увеличиваем изображение
        width, height = image.size

        if width < 1600:

            scale = 1600 / width

            image = image.resize(
                (
                    int(width * scale),
                    int(height * scale)
                )
            )

        # Оттенки серого
        image = image.convert("L")

        # Повышаем контраст
        image = ImageEnhance.Contrast(
            image
        ).enhance(2.0)

        # Немного резкости
        image = image.filter(
            ImageFilter.SHARPEN
        )

        print(
            "Запускаем Tesseract...",
            flush=True
        )

        text = pytesseract.image_to_string(
            image,
            lang="rus+eng",
            config="--psm 6"
        )

        return text.strip()

    except Exception as error:

        print(
            "OCR ERROR:",
            error,
            flush=True
        )

        return None


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
# МЕНЮ ПОСЛЕ ПОДПИСКИ
# =========================

def show_menu(chat_id):

    keyboard = {
        "inline_keyboard": [

            [
                {
                    "text": "📸 Распознать текст с фото",
                    "callback_data": "ocr"
                }
            ]

        ]
    }

    send_message(
        chat_id,

        "🎉 Отлично!\n\n"
        "Подписка подтверждена.\n\n"
        "Выбери функцию:",

        keyboard
    )


# =========================
# ОБРАБОТКА ФОТО
# =========================

def process_photo(
    chat_id,
    user_id,
    message
):

    print(
        "📸 Получено изображение",
        flush=True
    )

    # Проверяем подписку
    if not check_subscription(user_id):

        send_message(
            chat_id,

            "❌ Сначала подпишись на @bonusgrew."
        )

        return

    send_message(
        chat_id,

        "📸 Фото получил.\n\n"
        "🔎 Распознаю текст..."
    )

    try:

        photos = message["photo"]

        # Берём самое большое изображение
        largest_photo = photos[-1]

        file_id = largest_photo["file_id"]

        image_bytes = download_telegram_photo(
            file_id
        )

        if image_bytes is None:

            send_message(
                chat_id,

                "❌ Не удалось скачать фотографию."
            )

            return

        text = recognize_text(
            image_bytes
        )

        if not text:

            send_message(
                chat_id,

                "😔 Я не смог найти текст на этой фотографии.\n\n"
                "Попробуй отправить более чёткое фото "
                "с хорошим освещением."
            )

            return

        # Telegram ограничивает размер текста сообщения
        max_length = 4000

        if len(text) <= max_length:

            send_message(
                chat_id,

                "📝 Распознанный текст:\n\n"
                + text
            )

        else:

            # Разбиваем длинный текст
            for i in range(
                0,
                len(text),
                max_length
            ):

                part = text[
                    i:i + max_length
                ]

                send_message(
                    chat_id,
                    part
                )

    except Exception as error:

        print(
            "PHOTO ERROR:",
            error,
            flush=True
        )

        send_message(
            chat_id,

            "❌ Произошла ошибка при обработке фотографии."
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
        # ФОТО
        # =========================

        elif "photo" in message:

            print(
                "PHOTO DETECTED",
                flush=True
            )

            process_photo(
                chat_id,
                user_id,
                message
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

                show_menu(
                    chat_id
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


        # =========================
        # КНОПКА OCR
        # =========================

        elif callback_data == "ocr":

            telegram(
                "answerCallbackQuery",
                {
                    "callback_query_id": callback_id
                }
            )

            send_message(
                chat_id,

                "📸 Отправь мне фотографию с текстом.\n\n"
                "Я попробую распознать текст."
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
