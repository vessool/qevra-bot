import os
import json
import requests
import time
import tempfile
import re

from flask import Flask, request

from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import pytesseract

from pytesseract import Output

from io import BytesIO

from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT


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
# ПОДГОТОВКА ИЗОБРАЖЕНИЯ
# =========================================================

def prepare_image(image):

    print(
        "🖼️ ПОДГОТОВКА ИЗОБРАЖЕНИЯ",
        flush=True
    )

    image = image.convert("RGB")

    width, height = image.size

    print(
        "Исходный размер:",
        width,
        "x",
        height,
        flush=True
    )

    # -----------------------------------------------------
    # Увеличиваем небольшие фотографии
    # -----------------------------------------------------

    target_width = 1800

    if width < target_width:

        scale = target_width / width

        image = image.resize(
            (
                int(width * scale),
                int(height * scale)
            ),
            Image.Resampling.LANCZOS
        )

    # -----------------------------------------------------
    # Не даём изображению становиться чрезмерно большим
    # -----------------------------------------------------

    max_width = 2200

    if image.width > max_width:

        scale = max_width / image.width

        image = image.resize(
            (
                max_width,
                int(image.height * scale)
            ),
            Image.Resampling.LANCZOS
        )

    # -----------------------------------------------------
    # Оттенки серого
    # -----------------------------------------------------

    image = ImageOps.grayscale(
        image
    )

    # -----------------------------------------------------
    # Автоконтраст
    # -----------------------------------------------------

    image = ImageOps.autocontrast(
        image
    )

    # -----------------------------------------------------
    # Контраст
    # -----------------------------------------------------

    image = ImageEnhance.Contrast(
        image
    ).enhance(1.5)

    # -----------------------------------------------------
    # Резкость
    # -----------------------------------------------------

    image = image.filter(
        ImageFilter.SHARPEN
    )

    print(
        "Размер после подготовки:",
        image.size,
        flush=True
    )

    return image


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

        image = prepare_image(
            image
        )

        print(
            "Запускаем Tesseract...",
            flush=True
        )

        # -------------------------------------------------
        # Основной OCR
        # -------------------------------------------------

        text = pytesseract.image_to_string(
            image,
            lang="rus+eng",
            config="--psm 6"
        )

        text = clean_ocr_text(
            text
        )

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
# ОЧИСТКА OCR
# =========================================================

def clean_ocr_text(text):

    if not text:
        return ""

    lines = []

    for raw_line in text.splitlines():

        line = raw_line.strip()

        if not line:

            lines.append("")

            continue

        # Убираем повторяющиеся пробелы
        line = re.sub(
            r"[ \t]+",
            " ",
            line
        )

        # Исправляем пробелы перед знаками
        line = re.sub(
            r"\s+([,.!?;:%])",
            r"\1",
            line
        )

        # Исправляем скобки
        line = re.sub(
            r"\(\s+",
            "(",
            line
        )

        line = re.sub(
            r"\s+\)",
            ")",
            line
        )

        lines.append(
            line
        )

    # Убираем слишком большое количество
    # пустых строк подряд

    result = []

    empty_count = 0

    for line in lines:

        if not line:

            empty_count += 1

            if empty_count <= 1:

                result.append("")

        else:

            empty_count = 0

            result.append(
                line
            )

    return "\n".join(
        result
    ).strip()


# =========================================================
# ОПРЕДЕЛЕНИЕ ЗАГОЛОВКА
# =========================================================

def is_heading(line):

    line = line.strip()

    if not line:
        return False

    words = line.split()

    # Слишком длинная строка почти наверняка
    # является обычным текстом

    if len(words) > 14:
        return False

    if len(line) > 120:
        return False

    # Если это пункт списка — не заголовок

    if re.match(
        r"^(\d+[\.\)]|\d+\.\d+[\.\)]|[-•*–])",
        line
    ):

        return False

    letters = [
        char
        for char in line
        if char.isalpha()
    ]

    if not letters:
        return False

    uppercase = [
        char
        for char in letters
        if char.isupper()
    ]

    ratio = (
        len(uppercase)
        /
        len(letters)
    )

    # Полностью или преимущественно заглавная строка

    if ratio >= 0.65:

        return True

    # Короткая строка без точки в конце

    if (
        len(words) <= 8
        and len(line) <= 70
        and not line.endswith(
            (".", ",", ";", ":")
        )
    ):

        # Если первая буква заглавная
        if line[0].isupper():

            return True

    return False


# =========================================================
# ОПРЕДЕЛЕНИЕ СПИСКА
# =========================================================

def is_list_item(line):

    return bool(
        re.match(
            r"^(\d+[\.\)]|\d+\.\d+[\.\)]|[-•*–])\s+",
            line
        )
    )


# =========================================================
# ОПРЕДЕЛЕНИЕ НУМЕРОВАННОГО ПУНКТА
# =========================================================

def is_numbered_item(line):

    return bool(
        re.match(
            r"^\d+[\.\)]\s+",
            line
        )
    ) or bool(
        re.match(
            r"^\d+\.\d+[\.\)]\s+",
            line
        )
    )


# =========================================================
# ПОПЫТКА ОПРЕДЕЛИТЬ ТАБЛИЦУ
# =========================================================

def looks_like_table(lines):

    if len(lines) < 2:
        return False

    table_lines = 0

    for line in lines:

        # Несколько больших промежутков
        # между словами часто означают колонки

        if re.search(
            r"\s{3,}",
            line
        ):

            table_lines += 1

            continue

        # Разделители таблиц

        if "|" in line:

            table_lines += 1

    return table_lines >= 2


# =========================================================
# РАЗБОР ПРОСТОЙ ТАБЛИЦЫ
# =========================================================

def parse_table(lines):

    rows = []

    for line in lines:

        line = line.strip()

        if not line:
            continue

        # Таблица через |

        if "|" in line:

            cells = [
                cell.strip()
                for cell in line.split("|")
            ]

        else:

            # Таблица через несколько пробелов

            cells = [
                cell.strip()
                for cell in re.split(
                    r"\s{3,}",
                    line
                )
                if cell.strip()
            ]

        if len(cells) >= 2:

            rows.append(
                cells
            )

    return rows


# =========================================================
# ДОБАВЛЕНИЕ ТАБЛИЦЫ
# =========================================================

def add_table(
    document,
    rows
):

    if not rows:
        return

    max_columns = max(
        len(row)
        for row in rows
    )

    if max_columns < 2:
        return

    table = document.add_table(
        rows=len(rows),
        cols=max_columns
    )

    table.style = "Table Grid"

    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    for row_index, row in enumerate(rows):

        for column_index in range(
            max_columns
        ):

            cell = table.cell(
                row_index,
                column_index
            )

            cell.vertical_alignment = (
                WD_CELL_VERTICAL_ALIGNMENT.CENTER
            )

            if column_index < len(row):

                cell.text = row[
                    column_index
                ]

            else:

                cell.text = ""

            for paragraph in cell.paragraphs:

                paragraph.paragraph_format.space_after = Pt(0)

                for run in paragraph.runs:

                    run.font.name = "Arial"
                    run.font.size = Pt(10)

                    if row_index == 0:

                        run.bold = True


# =========================================================
# СОЗДАНИЕ WORD
# =========================================================

def create_word_document(text):

    try:

        print(
            "📄 СОЗДАЁМ СТРУКТУРИРОВАННЫЙ WORD",
            flush=True
        )

        document = Document()

        # -------------------------------------------------
        # Настройка страницы
        # -------------------------------------------------

        section = document.sections[0]

        section.top_margin = Cm(2)
        section.bottom_margin = Cm(2)
        section.left_margin = Cm(2)
        section.right_margin = Cm(2)

        # -------------------------------------------------
        # Основной стиль
        # -------------------------------------------------

        normal_style = document.styles["Normal"]

        normal_style.font.name = "Arial"
        normal_style.font.size = Pt(11)

        # -------------------------------------------------
        # Получаем строки
        # -------------------------------------------------

        raw_lines = text.splitlines()

        lines = []

        for line in raw_lines:

            line = line.strip()

            if not line:

                lines.append("")

                continue

            line = re.sub(
                r"[ \t]+",
                " ",
                line
            )

            lines.append(
                line
            )

        # -------------------------------------------------
        # Проверяем, похож ли блок на таблицу
        # -------------------------------------------------

        table_candidate = looks_like_table(
            lines
        )

        if table_candidate:

            table_rows = parse_table(
                lines
            )

            if (
                table_rows
                and max(
                    len(row)
                    for row in table_rows
                ) >= 2
            ):

                print(
                    "📊 Обнаружена возможная таблица",
                    flush=True
                )

                add_table(
                    document,
                    table_rows
                )

                # Если таблица занимала практически
                # весь документ — заканчиваем

                non_empty = [
                    line
                    for line in lines
                    if line
                ]

                if len(table_rows) >= len(
                    non_empty
                ) * 0.7:

                    return save_word_document(
                        document
                    )

        # -------------------------------------------------
        # Обычный структурированный документ
        # -------------------------------------------------

        previous_was_heading = False

        for line in lines:

            # -------------------------------------------------
            # Пустая строка
            # -------------------------------------------------

            if not line:

                paragraph = document.add_paragraph()

                paragraph.paragraph_format.space_after = Pt(2)

                continue

            # -------------------------------------------------
            # Заголовок
            # -------------------------------------------------

            if is_heading(line):

                paragraph = document.add_paragraph()

                paragraph.alignment = (
                    WD_ALIGN_PARAGRAPH.CENTER
                )

                paragraph.paragraph_format.space_before = Pt(8)
                paragraph.paragraph_format.space_after = Pt(8)

                run = paragraph.add_run(
                    line
                )

                run.bold = True
                run.font.name = "Arial"

                # Заголовок крупнее обычного текста

                if len(line) <= 50:

                    run.font.size = Pt(15)

                else:

                    run.font.size = Pt(13)

                previous_was_heading = True

                continue

            # -------------------------------------------------
            # Нумерованный пункт
            # -------------------------------------------------

            if is_numbered_item(line):

                paragraph = document.add_paragraph()

                paragraph.paragraph_format.left_indent = Cm(0.4)
                paragraph.paragraph_format.first_line_indent = Cm(0)

                paragraph.paragraph_format.space_after = Pt(5)
                paragraph.paragraph_format.line_spacing = 1.15

                run = paragraph.add_run(
                    line
                )

                run.font.name = "Arial"
                run.font.size = Pt(11)

                previous_was_heading = False

                continue

            # -------------------------------------------------
            # Маркированный список
            # -------------------------------------------------

            if is_list_item(line):

                paragraph = document.add_paragraph()

                paragraph.paragraph_format.left_indent = Cm(0.7)
                paragraph.paragraph_format.first_line_indent = Cm(0)

                paragraph.paragraph_format.space_after = Pt(4)

                run = paragraph.add_run(
                    line
                )

                run.font.name = "Arial"
                run.font.size = Pt(11)

                previous_was_heading = False

                continue

            # -------------------------------------------------
            # Обычный абзац
            # -------------------------------------------------

            paragraph = document.add_paragraph()

            paragraph.paragraph_format.space_after = Pt(6)
            paragraph.paragraph_format.line_spacing = 1.15

            # Отступ первой строки

            paragraph.paragraph_format.first_line_indent = Cm(0.7)

            run = paragraph.add_run(
                line
            )

            run.font.name = "Arial"
            run.font.size = Pt(11)

            previous_was_heading = False

        return save_word_document(
            document
        )

    except Exception as error:

        print(
            "WORD ERROR:",
            error,
            flush=True
        )

        return None


# =========================================================
# СОХРАНЕНИЕ WORD
# =========================================================

def save_word_document(
    document
):

    try:

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
            "SAVE WORD ERROR:",
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

        "Я могу обработать фотографию документа.\n\n"

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
# СОЗДАНИЕ WORD
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

        "📄 Анализирую структуру документа...\n\n"
        "Это может занять немного времени."
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
                "📄 Создан редактируемый Word-файл.\n"
                "Можно открыть его и изменить текст."
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
