import os
import json
import requests
import time

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


# =========================================================
# ПАМЯТЬ БОТА
# =========================================================

# Последние обработанные update_id
processed_updates = set()

# Последний распознанный текст пользователя
user_texts = {}

# Время последней обработки фотографии
photo_processing = {}


# =========================================================
# ЗАЩИТА ОТ ПОВТОРНЫХ UPDATE
# =========================================================

def already_processed(update_id):

    if update_id in processed_updates:

        print(
            "⚠️ UPDATE УЖЕ ОБРАБОТАН:",
            update_id,
            flush=True
        )

        return True

    processed_updates.add(update_id)

    # Чтобы память не росла бесконечно
    if len(processed_updates) > 1000:

        oldest = next(
            iter(processed_updates)
        )

        processed_updates.discard(
            oldest
        )

    return False


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
            "TELEGRAM ERROR:",
            error,
            flush=True
        )

        return {
            "ok": False
        }


# =========================================================
# ОТПРАВКА СООБЩЕНИЯ
# =========================================================

def send_message(
    chat_id,
    text,
    keyboard=None
):

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
# ДЛИННЫЙ ТЕКСТ
# =========================================================

def send_long_message(
    chat_id,
    text
):

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

        send_message(
            chat_id,
            text[
                i:i + max_length
            ]
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
            "Ошибка проверки подписки:",
            result,
            flush=True
        )

        return False

    status = result["result"]["status"]

    print(
        "Статус:",
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

def download_telegram_photo(
    file_id
):

    print(
        "Получаем файл:",
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
            "GET FILE ERROR:",
            result,
            flush=True
        )

        return None

    file_path = result[
        "result"
    ][
        "file_path"
    ]

    url = (
        f"https://api.telegram.org/file/"
        f"bot{BOT_TOKEN}/{file_path}"
    )

    try:

        response = requests.get(
            url,
            timeout=30
        )

        if response.status_code != 200:

            print(
                "DOWNLOAD ERROR:",
                response.status_code,
                flush=True
            )

            return None

        return response.content

    except Exception as error:

        print(
            "DOWNLOAD EXCEPTION:",
            error,
            flush=True
        )

        return None


# =========================================================
# OCR
# =========================================================

def recognize_text(
    image_bytes
):

    try:

        print(
            "🧠 OCR START",
            flush=True
        )

        image = Image.open(
            BytesIO(image_bytes)
        )

        print(
            "Размер:",
            image.size,
            flush=True
        )

        image = image.convert(
            "RGB"
        )

        width, height = image.size

        # Не увеличиваем огромные фотографии
        if width < 1600:

            scale = 1600 / width

            image = image.resize(
                (
                    int(width * scale),
                    int(height * scale)
                )
            )

        image = image.convert(
            "L"
        )

        image = ImageEnhance.Contrast(
            image
        ).enhance(2.0)

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

        text = text.strip()

        print(
            "OCR FINISHED. Символов:",
            len(text),
            flush=True
        )

        return text

    except Exception as error:

        print(
            "OCR ERROR:",
            error,
            flush=True
        )

        return None


# =========================================================
# КЛАВИАТУРА
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


def ocr_keyboard():

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
# START
# =========================================================

def start_command(
    chat_id
):

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

        "📸 Распознавание текста с фото\n"
        "🌐 Перевод\n"
        "✍️ Улучшение текста\n\n"

        "Для начала подпишись на канал:\n"
        "@bonusgrew\n\n"

        "После этого нажми "
        "«✅ Проверить подписку».",

        keyboard
    )


# =========================================================
# МЕНЮ
# =========================================================

def show_menu(
    chat_id
):

    send_message(
        chat_id,

        "🎉 Доступ открыт!\n\n"
        "Выбери функцию:",

        main_menu_keyboard()
    )


# =========================================================
# ОБРАБОТКА ФОТО
# =========================================================

def process_photo(
    chat_id,
    user_id,
    message
):

    print(
        "📸 PHOTO PROCESS START",
        flush=True
    )

    # -----------------------------------------------------
    # Защита от слишком частого повторения
    # -----------------------------------------------------

    now = time.time()

    last_time = photo_processing.get(
        user_id,
        0
    )

    if now - last_time < 10:

        print(
            "⚠️ Фото недавно уже обрабатывалось",
            flush=True
        )

        return

    photo_processing[
        user_id
    ] = now


    # -----------------------------------------------------
    # Подписка
    # -----------------------------------------------------

    if not check_subscription(
        user_id
    ):

        send_message(
            chat_id,

            "❌ Сначала подпишись на @bonusgrew."
        )

        return


    # -----------------------------------------------------
    # Сообщение пользователю
    # -----------------------------------------------------

    send_message(
        chat_id,

        "📸 Фото получил.\n\n"
        "🔎 Распознаю текст..."
    )


    try:

        photos = message.get(
            "photo"
        )

        if not photos:

            send_message(
                chat_id,
                "❌ Фото не найдено."
            )

            return

        # Самое большое фото
        photo = photos[-1]

        file_id = photo[
            "file_id"
        ]

        image_bytes = download_telegram_photo(
            file_id
        )

        if image_bytes is None:

            send_message(
                chat_id,

                "❌ Не удалось скачать фотографию."
            )

            return

        # OCR
        text = recognize_text(
            image_bytes
        )

        if not text:

            send_message(
                chat_id,

                "😔 Я не смог найти текст "
                "на фотографии.\n\n"

                "Попробуй сделать более "
                "чёткое фото."
            )

            return

        # Сохраняем
        user_texts[
            user_id
        ] = text

        print(
            "✅ Текст сохранён",
            flush=True
        )

        # Отправляем результат
        send_long_message(
            chat_id,

            "📝 Распознанный текст:\n\n"
            + text
        )

        # Кнопки отдельно
        send_message(
            chat_id,

            "Что сделать дальше?",

            ocr_keyboard()
        )

    except Exception as error:

        print(
            "PHOTO ERROR:",
            error,
            flush=True
        )

        send_message(
            chat_id,

            "❌ Ошибка при обработке фотографии."
        )

    finally:

        print(
            "📸 PHOTO PROCESS END",
            flush=True
        )


# =========================================================
# УЛУЧШЕНИЕ ТЕКСТА
# =========================================================

def improve_text(
    text
):

    try:

        lines = []

        for line in text.splitlines():

            line = " ".join(
                line.split()
            )

            if line:

                lines.append(
                    line.strip()
                )

        result = "\n".join(
            lines
        )

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

            result = result.replace(
                old,
                new
            )

        return result.strip()

    except Exception as error:

        print(
            "IMPROVE ERROR:",
            error,
            flush=True
        )

        return text


# =========================================================
# ПРОСТОЙ ПЕРЕВОД
# =========================================================

def translate_text(
    text
):

    try:

        print(
            "🌐 TRANSLATE START",
            flush=True
        )

        russian = sum(
            1
            for char in text
            if "а" <= char.lower() <= "я"
        )

        english = sum(
            1
            for char in text
            if "a" <= char.lower() <= "z"
        )

        if russian >= english:

            source = "ru"
            target = "en"

        else:

            source = "en"
            target = "ru"

        url = (
            "https://translate.googleapis.com/"
            "translate_a/single"
        )

        params = {

            "client": "gtx",
            "sl": source,
            "tl": target,
            "dt": "t",
            "q": text

        }

        response = requests.get(
            url,
            params=params,
            timeout=20
        )

        if response.status_code != 200:

            print(
                "TRANSLATE STATUS:",
                response.status_code,
                flush=True
            )

            return None

        data = response.json()

        result = ""

        for item in data[0]:

            if item and item[0]:

                result += item[0]

        return result.strip()

    except Exception as error:

        print(
            "TRANSLATE ERROR:",
            error,
            flush=True
        )

        return None


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

    if not update:

        return "OK"


    # =====================================================
    # ЗАЩИТА ОТ ДУБЛЕЙ
    # =====================================================

    update_id = update.get(
        "update_id"
    )

    if update_id is not None:

        if already_processed(
            update_id
        ):

            return "OK"


    print(
        "UPDATE:",
        update,
        flush=True
    )


    # =====================================================
    # MESSAGE
    # =====================================================

    if "message" in update:

        message = update[
            "message"
        ]

        chat_id = message[
            "chat"
        ][
            "id"
        ]

        user_id = message[
            "from"
        ][
            "id"
        ]

        text = message.get(
            "text",
            ""
        )

        print(
            "MESSAGE:",
            text,
            flush=True
        )


        # -------------------------------------------------
        # START
        # -------------------------------------------------

        if text == "/start":

            start_command(
                chat_id
            )

            return "OK"


        # -------------------------------------------------
        # PHOTO
        # -------------------------------------------------

        if "photo" in message:

            process_photo(
                chat_id,
                user_id,
                message
            )

            return "OK"


    # =====================================================
    # CALLBACK
    # =====================================================

    if "callback_query" in update:

        callback = update[
            "callback_query"
        ]

        callback_id = callback[
            "id"
        ]

        user_id = callback[
            "from"
        ][
            "id"
        ]

        chat_id = callback[
            "message"
        ][
            "chat"
        ][
            "id"
        ]

        callback_data = callback[
            "data"
        ]

        print(
            "CALLBACK:",
            callback_data,
            flush=True
        )


        # -------------------------------------------------
        # CHECK SUBSCRIPTION
        # -------------------------------------------------

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

                    "❌ Подписка не найдена.\n\n"
                    "Подпишись на @bonusgrew "
                    "и попробуй снова."
                )


        # -------------------------------------------------
        # OCR
        # -------------------------------------------------

        elif callback_data == "ocr":

            telegram(
                "answerCallbackQuery",
                {
                    "callback_query_id": callback_id
                }
            )

            send_message(
                chat_id,

                "📸 Отправь фотографию "
                "с текстом."
            )


        # -------------------------------------------------
        # TRANSLATE
        # -------------------------------------------------

        elif callback_data == "translate":

            telegram(
                "answerCallbackQuery",
                {
                    "callback_query_id": callback_id,
                    "text": "🌐 Перевожу..."
                }
            )

            if not check_subscription(
                user_id
            ):

                send_message(
                    chat_id,
                    "❌ Сначала подпишись на @bonusgrew."
                )

            elif user_id not in user_texts:

                send_message(
                    chat_id,

                    "❌ Нет текста для перевода.\n\n"
                    "Сначала отправь фотографию."
                )

            else:

                text = user_texts[
                    user_id
                ]

                send_message(
                    chat_id,
                    "🌐 Перевожу..."
                )

                translated = translate_text(
                    text
                )

                if translated:

                    send_long_message(
                        chat_id,

                        "🌐 Перевод:\n\n"
                        + translated
                    )

                    send_message(
                        chat_id,

                        "Готово. Что дальше?",

                        ocr_keyboard()
                    )

                else:

                    send_message(
                        chat_id,

                        "❌ Не удалось выполнить перевод."
                    )


        # -------------------------------------------------
        # IMPROVE
        # -------------------------------------------------

        elif callback_data == "improve":

            telegram(
                "answerCallbackQuery",
                {
                    "callback_query_id": callback_id,
                    "text": "✍️ Улучшаю..."
                }
            )

            if user_id not in user_texts:

                send_message(
                    chat_id,

                    "❌ Сначала отправь фотографию."
                )

            else:

                text = user_texts[
                    user_id
                ]

                improved = improve_text(
                    text
                )

                user_texts[
                    user_id
                ] = improved

                send_long_message(
                    chat_id,

                    "✍️ Улучшенный текст:\n\n"
                    + improved
                )

                send_message(
                    chat_id,

                    "Готово. Что дальше?",

                    ocr_keyboard()
                )


        # -------------------------------------------------
        # MENU
        # -------------------------------------------------

        elif callback_data == "menu":

            telegram(
                "answerCallbackQuery",
                {
                    "callback_query_id": callback_id
                }
            )

            show_menu(
                chat_id
            )


    return "OK"


# =========================================================
# HOME
# =========================================================

@app.route(
    "/",
    methods=["GET"]
)
def home():

    return "QEVRA is alive! 🚀"


# =========================================================
# START SERVER
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
