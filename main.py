import os
import json
import requests

from flask import Flask, request

from PIL import Image, ImageEnhance, ImageFilter
import pytesseract

from io import BytesIO


app = Flask(__name__)


# =========================================================
# НАСТРОЙКИ
# =========================================================

BOT_TOKEN = os.environ.get("BOT_TOKEN")

CHANNEL_USERNAME = "@bonusgrew"

API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Последний распознанный текст каждого пользователя
user_texts = {}


# =========================================================
# TELEGRAM API
# =========================================================

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


# =========================================================
# ОТПРАВКА СООБЩЕНИЯ
# =========================================================

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

    return telegram(
        "sendMessage",
        data
    )


# =========================================================
# РАЗБИВКА ДЛИННОГО ТЕКСТА
# =========================================================

def send_long_message(chat_id, text):

    max_length = 4000

    if len(text) <= max_length:

        send_message(
            chat_id,
            text
        )

        return

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


# =========================================================
# ПРОВЕРКА ПОДПИСКИ
# =========================================================

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


# =========================================================
# СКАЧИВАНИЕ ФОТО
# =========================================================

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

    try:

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

    except Exception as error:

        print(
            "DOWNLOAD ERROR:",
            error,
            flush=True
        )

        return None


# =========================================================
# OCR
# =========================================================

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

        image = image.convert("RGB")

        width, height = image.size

        # Увеличиваем маленькие изображения
        if width < 1600:

            scale = 1600 / width

            image = image.resize(
                (
                    int(width * scale),
                    int(height * scale)
                )
            )

        # Чёрно-белое изображение
        image = image.convert("L")

        # Контраст
        image = ImageEnhance.Contrast(
            image
        ).enhance(2.0)

        # Резкость
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


# =========================================================
# ПЕРЕВОД
# =========================================================

def translate_text(text):

    print(
        "Запускаем перевод...",
        flush=True
    )

    try:

        # Определяем язык очень приблизительно
        russian_letters = sum(
            1 for char in text
            if "а" <= char.lower() <= "я"
        )

        english_letters = sum(
            1 for char in text
            if "a" <= char.lower() <= "z"
        )

        if russian_letters > english_letters:

            source_lang = "ru"
            target_lang = "en"

        else:

            source_lang = "en"
            target_lang = "ru"

        url = "https://translate.googleapis.com/translate_a/single"

        params = {
            "client": "gtx",
            "sl": source_lang,
            "tl": target_lang,
            "dt": "t",
            "q": text
        }

        response = requests.get(
            url,
            params=params,
            timeout=30
        )

        if response.status_code != 200:

            print(
                "TRANSLATE STATUS:",
                response.status_code,
                flush=True
            )

            return None

        data = response.json()

        translated_parts = []

        for item in data[0]:

            if item and item[0]:

                translated_parts.append(
                    item[0]
                )

        translated = "".join(
            translated_parts
        ).strip()

        if not translated:

            return None

        print(
            "Перевод получен:",
            translated[:200],
            flush=True
        )

        return translated

    except Exception as error:

        print(
            "TRANSLATE ERROR:",
            error,
            flush=True
        )

        return None


# =========================================================
# УЛУЧШЕНИЕ ТЕКСТА
# =========================================================

def improve_text(text):

    try:

        # Убираем лишние пробелы
        lines = []

        for line in text.splitlines():

            line = " ".join(
                line.split()
            ).strip()

            if line:

                lines.append(line)

        cleaned = "\n".join(lines)

        # Убираем повторяющиеся пробелы
        cleaned = cleaned.replace(
            "  ",
            " "
        )

        # Исправляем некоторые типичные OCR-ошибки
        replacements = {

            " ,": ",",
            " .": ".",
            " !": "!",
            " ?": "?",
            " :": ":",
            " ;": ";",
            "( ": "(",
            " )": ")"

        }

        for old, new in replacements.items():

            cleaned = cleaned.replace(
                old,
                new
            )

        return cleaned.strip()

    except Exception as error:

        print(
            "IMPROVE ERROR:",
            error,
            flush=True
        )

        return text


# =========================================================
# ГЛАВНОЕ МЕНЮ
# =========================================================

def main_menu_keyboard():

    return {
        "inline_keyboard": [

            [
                {
                    "text": "📸 Распознать текст",
                    "callback_data": "ocr"
                }
            ]

        ]
    }


def show_menu(chat_id):

    send_message(
        chat_id,

        "🎉 QEVRA готов к работе!\n\n"
        "Выбери функцию:",

        main_menu_keyboard()
    )


# =========================================================
# START
# =========================================================

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

        "Твой Telegram-помощник.\n\n"

        "Сейчас я умею:\n"
        "📸 распознавать текст с фотографий\n"
        "🌐 переводить распознанный текст\n"
        "✍️ очищать и улучшать текст\n\n"

        "Для доступа подпишись на канал:\n"
        "@bonusgrew\n\n"

        "После подписки нажми "
        "«✅ Проверить подписку».",

        keyboard
    )


# =========================================================
# МЕНЮ РЕЗУЛЬТАТА OCR
# =========================================================

def ocr_result_keyboard():

    return {
        "inline_keyboard": [

            [
                {
                    "text": "🌐 Перевести",
                    "callback_data": "translate"
                }
            ],

            [
                {
                    "text": "✍️ Улучшить текст",
                    "callback_data": "improve"
                }
            ],

            [
                {
                    "text": "📸 Распознать ещё",
                    "callback_data": "ocr"
                }
            ],

            [
                {
                    "text": "🏠 Главное меню",
                    "callback_data": "menu"
                }
            ]

        ]
    }


# =========================================================
# ОБРАБОТКА ФОТО
# =========================================================

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

        # Берём самое большое фото
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

                "😔 Я не смог найти текст "
                "на этой фотографии.\n\n"

                "Попробуй:\n"
                "• сделать фото чётче\n"
                "• добавить освещение\n"
                "• сфотографировать текст прямо"
            )

            return

        # Сохраняем текст
        user_texts[user_id] = text

        print(
            "Текст сохранён для пользователя:",
            user_id,
            flush=True
        )

        send_message(
            chat_id,

            "📝 Распознанный текст:\n\n"
            + text,

            ocr_result_keyboard()
        )

    except Exception as error:

        print(
            "PHOTO ERROR:",
            error,
            flush=True
        )

        send_message(
            chat_id,

            "❌ Произошла ошибка "
            "при обработке фотографии."
        )


# =========================================================
# WEBHOOK
# =========================================================

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


    # =====================================================
    # СООБЩЕНИЯ
    # =====================================================

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


        # -------------------------------------------------
        # START
        # -------------------------------------------------

        if text == "/start":

            print(
                "START DETECTED",
                flush=True
            )

            start_command(
                chat_id
            )


        # -------------------------------------------------
        # ФОТО
        # -------------------------------------------------

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


    # =====================================================
    # CALLBACK
    # =====================================================

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


        # =================================================
        # ПРОВЕРКА ПОДПИСКИ
        # =================================================

        if callback_data == "check_subscription":

            subscribed = check_subscription(
                user_id
            )

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


        # =================================================
        # OCR
        # =================================================

        elif callback_data == "ocr":

            telegram(
                "answerCallbackQuery",
                {
                    "callback_query_id": callback_id
                }
            )

            send_message(
                chat_id,

                "📸 Отправь фотографию с текстом.\n\n"
                "Я попробую распознать его."
            )


        # =================================================
        # ПЕРЕВОД
        # =================================================

        elif callback_data == "translate":

            telegram(
                "answerCallbackQuery",
                {
                    "callback_query_id": callback_id,
                    "text": "🌐 Перевожу..."
                }
            )

            # Проверяем подписку
            if not check_subscription(user_id):

                send_message(
                    chat_id,
                    "❌ Сначала подпишись на @bonusgrew."
                )

            elif user_id not in user_texts:

                send_message(
                    chat_id,

                    "❌ У меня нет текста для перевода.\n\n"
                    "Сначала отправь фотографию."
                )

            else:

                original_text = user_texts[user_id]

                send_message(
                    chat_id,
                    "🌐 Перевожу текст..."
                )

                translated = translate_text(
                    original_text
                )

                if translated:

                    send_long_message(
                        chat_id,

                        "🌐 Перевод:\n\n"
                        + translated
                    )

                    send_message(
                        chat_id,

                        "Что сделать дальше?",

                        ocr_result_keyboard()
                    )

                else:

                    send_message(
                        chat_id,

                        "❌ Не удалось выполнить перевод.\n\n"
                        "Попробуй ещё раз."
                    )


        # =================================================
        # УЛУЧШЕНИЕ
        # =================================================

        elif callback_data == "improve":

            telegram(
                "answerCallbackQuery",
                {
                    "callback_query_id": callback_id,
                    "text": "✍️ Обрабатываю..."
                }
            )

            if not check_subscription(user_id):

                send_message(
                    chat_id,
                    "❌ Сначала подпишись на @bonusgrew."
                )

            elif user_id not in user_texts:

                send_message(
                    chat_id,

                    "❌ У меня нет текста.\n\n"
                    "Сначала отправь фотографию."
                )

            else:

                original_text = user_texts[user_id]

                improved = improve_text(
                    original_text
                )

                user_texts[user_id] = improved

                send_long_message(
                    chat_id,

                    "✍️ Улучшенный текст:\n\n"
                    + improved
                )

                send_message(
                    chat_id,

                    "Что сделать дальше?",

                    ocr_result_keyboard()
                )


        # =================================================
        # ГЛАВНОЕ МЕНЮ
        # =================================================

        elif callback_data == "menu":

            telegram(
                "answerCallbackQuery",
                {
                    "callback_query_id": callback_id
                }
            )

            if not check_subscription(user_id):

                send_message(
                    chat_id,
                    "❌ Сначала подпишись на @bonusgrew."
                )

            else:

                show_menu(
                    chat_id
                )


    return "OK"


# =========================================================
# ГЛАВНАЯ СТРАНИЦА
# =========================================================

@app.route(
    "/",
    methods=["GET"]
)
def home():

    return "QEVRA is alive! 🚀"


# =========================================================
# ЗАПУСК
# =========================================================

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
