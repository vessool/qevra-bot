import os
import json
import requests
import time
import tempfile

from flask import Flask, request

from PIL import Image, ImageEnhance, ImageFilter
import pytesseract

from io import BytesIO
from docx import Document


app = Flask(__name__)


# =========================================================
# НАСТРОЙКИ
# =========================================================

BOT_TOKEN = os.environ.get("BOT_TOKEN")

API = f"https://api.telegram.org/bot{BOT_TOKEN}"


# =========================================================
# ПАМЯТЬ БОТА
# =========================================================

processed_updates = set()

user_texts = {}

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
# СОЗДАНИЕ WORD
# =========================================================

def create_word_document(text):

    try:

        print(
            "📄 СОЗДАЁМ WORD",
            flush=True
        )

        document = Document()

        # Разбиваем распознанный текст на строки
        lines = text.splitlines()

        for line in lines:

            line = line.strip()

            if line:

                document.add_paragraph(
                    line
                )

            else:

                document.add_paragraph("")

        # Временный файл
        temp_file = tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".docx"
        )

        file_path = temp_file.name

        temp_file.close()

        document.save(
            file_path
        )

        print(
            "✅ WORD СОЗДАН:",
            file_path,
            flush=True
        )

        return file_path

    except Exception as error:

        print(
            "WORD ERROR:",
            error,
            flush=True
        )

        return None


# =========================================================
# ОТПРАВКА WORD
# =========================================================

def send_document(
    chat_id,
    file_path,
    filename="document.docx"
):

    try:

        url = f"{API}/sendDocument"

        with open(
            file_path,
            "rb"
        ) as document_file:

            response = requests.post(
                url,
                data={
                    "chat_id": chat_id
                },
                files={
                    "document": (
                        filename,
                        document_file,
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )
                },
                timeout=60
            )

        print(
            "SEND DOCUMENT:",
            response.status_code,
            response.text,
            flush=True
        )

        return response.json()

    except Exception as error:

        print(
            "SEND DOCUMENT ERROR:",
            error,
            flush=True
        )

        return {
            "ok": False
        }


# =========================================================
# КЛАВИАТУРЫ
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
                    "text": "📄 Создать Word",
                    "callback_data": "create_word"
                }
            ],

            [
                {
                    "text": "🌐 Перевести",
                    "callback_data": "translate"
                },

                {
                    "text": "✍️ Улучшить",
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

    send_message(
        chat_id,

        "👋 Привет! Я QEVRA 🚀\n\n"

        "Я могу помочь обработать фотографию документа.\n\n"

        "📸 Распознать текст\n"
        "📄 Создать редактируемый Word\n"
        "🌐 Перевести текст\n"
        "✍️ Улучшить распознанный текст\n\n"

        "Просто отправь мне фотографию.",

        main_menu_keyboard()
    )


# =========================================================
# МЕНЮ
# =========================================================

def show_menu(
    chat_id
):

    send_message(
        chat_id,

        "🤖 Что будем делать?",

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

        user_texts[
            user_id
        ] = text

        print(
            "✅ Текст сохранён",
            flush=True
        )

        send_long_message(
            chat_id,

            "📝 Распознанный текст:\n\n"
            + text
        )

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
# WORD
# =========================================================

def process_create_word(
    chat_id,
    user_id
):

    if user_id not in user_texts:

        send_message(
            chat_id,

            "❌ Сначала отправь фотографию документа."
        )

        return

    text = user_texts[
        user_id
    ]

    send_message(
        chat_id,

        "📄 Создаю редактируемый Word-файл..."
    )

    file_path = create_word_document(
        text
    )

    if not file_path:

        send_message(
            chat_id,

            "❌ Не удалось создать Word-файл."
        )

        return

    try:

        result = send_document(
            chat_id,
            file_path,
            "QEVRA_document.docx"
        )

        if result.get("ok"):

            send_message(
                chat_id,

                "✅ Готово!\n\n"
                "📄 Word-файл можно открыть "
                "и редактировать."
            )

        else:

            send_message(
                chat_id,

                "❌ Не удалось отправить Word-файл."
            )

    finally:

        try:

            os.remove(
                file_path
            )

        except Exception:
            pass


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
# ПЕРЕВОД
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
        # OCR
        # -------------------------------------------------

        if callback_data == "ocr":

            telegram(
                "answerCallbackQuery",
                {
                    "callback_query_id": callback_id
                }
            )

            send_message(
                chat_id,

                "📸 Отправь фотографию документа."
            )


        # -------------------------------------------------
        # CREATE WORD
        # -------------------------------------------------

        elif callback_data == "create_word":

            telegram(
                "answerCallbackQuery",
                {
                    "callback_query_id": callback_id,
                    "text": "📄 Создаю Word..."
                }
            )

            process_create_word(
                chat_id,
                user_id
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

            if user_id not in user_texts:

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
