import os
import json
import requests
import time
import tempfile
import re
import statistics

from flask import Flask, request

from PIL import (
    Image,
    ImageEnhance,
    ImageFilter,
    ImageOps
)

import pytesseract

from pytesseract import Output

from io import BytesIO

from docx import Document

from docx.shared import Pt, Cm

from docx.enum.text import WD_ALIGN_PARAGRAPH

from docx.enum.table import (
    WD_TABLE_ALIGNMENT,
    WD_CELL_VERTICAL_ALIGNMENT
)

from docx.oxml import OxmlElement
from docx.oxml.ns import qn


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

user_ocr_data = {}

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

    image = image.convert(
        "RGB"
    )

    width, height = image.size

    print(
        "Исходный размер:",
        width,
        "x",
        height,
        flush=True
    )

    # -----------------------------------------------------
    # Увеличиваем маленькие изображения
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
    # Ограничиваем максимальный размер
    # -----------------------------------------------------

    max_width = 2400

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
    # Серый
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
    ).enhance(1.35)

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
# ОЧИСТКА ОДНОГО OCR-СЛОВА
# =========================================================

def clean_ocr_word(word):

    if not word:
        return ""

    word = word.replace(
        "\x0c",
        ""
    )

    # Убираем только явно мусорные управляющие символы.
    # Пунктуацию НЕ трогаем.

    word = "".join(
        char
        for char in word
        if char.isprintable()
    )

    return word.strip()


# =========================================================
# OCR С КООРДИНАТАМИ
# =========================================================

def recognize_document(
    image
):

    print(
        "🧠 DOCUMENT OCR START",
        flush=True
    )

    # -----------------------------------------------------
    # Основной режим
    # -----------------------------------------------------

    data = pytesseract.image_to_data(
        image,
        lang="rus+eng",
        config="--oem 3 --psm 3",
        output_type=Output.DICT
    )

    words = []

    total = len(
        data.get("text", [])
    )

    for i in range(total):

        raw_text = data["text"][i]

        text = clean_ocr_word(
            raw_text
        )

        if not text:
            continue

        try:

            confidence = float(
                data["conf"][i]
            )

        except Exception:

            confidence = -1

        if confidence < 15:
            continue

        try:

            left = int(
                data["left"][i]
            )

            top = int(
                data["top"][i]
            )

            width = int(
                data["width"][i]
            )

            height = int(
                data["height"][i]
            )

            block = int(
                data["block_num"][i]
            )

            paragraph = int(
                data["par_num"][i]
            )

            line = int(
                data["line_num"][i]
            )

        except Exception:

            continue

        words.append({

            "text": text,

            "left": left,

            "top": top,

            "right": left + width,

            "bottom": top + height,

            "width": width,

            "height": height,

            "confidence": confidence,

            "block": block,

            "paragraph": paragraph,

            "line": line

        })

    print(
        "OCR WORDS:",
        len(words),
        flush=True
    )

    if not words:
        return None

    # -----------------------------------------------------
    # Группируем слова в визуальные строки
    # -----------------------------------------------------

    lines = group_words_into_lines(
        words
    )

    print(
        "OCR LINES:",
        len(lines),
        flush=True
    )

    return {
        "words": words,
        "lines": lines
    }


# =========================================================
# ГРУППИРОВКА СЛОВ В СТРОКИ
# =========================================================

def group_words_into_lines(
    words
):

    if not words:
        return []

    words = sorted(
        words,
        key=lambda item: (
            item["top"],
            item["left"]
        )
    )

    lines = []

    current = []

    current_top = None

    heights = [
        word["height"]
        for word in words
        if word["height"] > 0
    ]

    if heights:

        median_height = statistics.median(
            heights
        )

    else:

        median_height = 20

    tolerance = max(
        8,
        int(median_height * 0.65)
    )

    for word in words:

        if not current:

            current = [word]

            current_top = word["top"]

            continue

        if abs(
            word["top"] - current_top
        ) <= tolerance:

            current.append(
                word
            )

        else:

            current = sorted(
                current,
                key=lambda item: item["left"]
            )

            lines.append(
                current
            )

            current = [word]

            current_top = word["top"]

    if current:

        current = sorted(
            current,
            key=lambda item: item["left"]
        )

        lines.append(
            current
        )

    return lines


# =========================================================
# СОЕДИНЕНИЕ СЛОВ В СТРОКУ
# =========================================================

def line_to_text(
    line
):

    if not line:
        return ""

    result = ""

    previous = None

    for word in line:

        text = word["text"]

        if previous is None:

            result = text

        else:

            gap = (
                word["left"]
                -
                previous["right"]
            )

            # Если расстояние большое —
            # обычный пробел.
            #
            # Мы не используем несколько пробелов
            # как основу структуры. Структура берётся
            # из координат.

            if gap > 2:

                result += " "

            result += text

        previous = word

    return result.strip()


# =========================================================
# СОЗДАНИЕ ТЕКСТА ИЗ OCR
# =========================================================

def ocr_to_text(
    ocr_data
):

    if not ocr_data:
        return ""

    lines = ocr_data.get(
        "lines",
        []
    )

    result = []

    for line in lines:

        text = line_to_text(
            line
        )

        if text:

            result.append(
                text
            )

    return "\n".join(
        result
    ).strip()


# =========================================================
# ОЧИСТКА OCR ТЕКСТА
# =========================================================

def clean_ocr_text(
    text
):

    if not text:
        return ""

    result = []

    for raw_line in text.splitlines():

        # Не делаем strip агрессивно.
        # Убираем только лишние крайние пробелы.

        line = raw_line.strip()

        if not line:

            result.append("")

            continue

        # Повторяющиеся пробелы внутри текста
        # можно сократить.
        #
        # Но пунктуацию не изменяем.

        line = re.sub(
            r"[ \t]{2,}",
            " ",
            line
        )

        result.append(
            line
        )

    # Не больше двух пустых строк подряд.

    final = []

    empty_count = 0

    for line in result:

        if not line:

            empty_count += 1

            if empty_count <= 2:

                final.append("")

        else:

            empty_count = 0

            final.append(
                line
            )

    return "\n".join(
        final
    ).strip()


# =========================================================
# ОПРЕДЕЛЕНИЕ ЗАГОЛОВКА
# =========================================================

def is_heading(
    line
):

    line = line.strip()

    if not line:
        return False

    words = line.split()

    if len(words) > 10:
        return False

    if len(line) > 90:
        return False

    # Никогда не считаем пункт списка заголовком

    if re.match(
        r"^(\d+[\.\)]|\d+\.\d+[\.\)]|[-•*–])\s+",
        line
    ):

        return False

    # Если строка заканчивается
    # обычной пунктуацией — скорее всего текст.

    if line.endswith(
        (".", ",", ";", ":", "?", "!")
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

    # Явный CAPS-заголовок

    if (
        ratio >= 0.80
        and len(words) <= 8
    ):

        return True

    # Очень короткая строка,
    # но только если она визуально похожа
    # на отдельный заголовок.

    if (
        len(words) <= 5
        and len(line) <= 55
        and line[0].isupper()
    ):

        # Не превращаем обычные предложения
        # в заголовки.

        if not re.search(
            r"[,.!?;:]",
            line
        ):

            return True

    return False


# =========================================================
# СПИСКИ
# =========================================================

def is_list_item(
    line
):

    return bool(
        re.match(
            r"^(\d+[\.\)]|\d+\.\d+[\.\)]|[-•*–])\s+",
            line
        )
    )


def is_numbered_item(line):

    return (
        bool(
            re.match(
                r"^\d+[\.\)]\s+",
                line
            )
        )
        or
        bool(
            re.match(
                r"^\d+\.\d+[\.\)]\s+",
                line
            )
        )
    )
# =========================================================
# АНАЛИЗ КОЛОНОК
# =========================================================

def get_line_gaps(
    line
):

    if len(line) < 2:
        return []

    gaps = []

    for i in range(
        1,
        len(line)
    ):

        previous = line[i - 1]

        current = line[i]

        gap = (
            current["left"]
            -
            previous["right"]
        )

        if gap > 0:

            gaps.append({
                "position": current["left"],
                "gap": gap
            })

    return gaps


# =========================================================
# ОПРЕДЕЛЕНИЕ ТАБЛИЦЫ ПО КООРДИНАТАМ
# =========================================================

def detect_table_blocks(
    lines
):

    if len(lines) < 2:
        return []

    candidates = []

    for index, line in enumerate(lines):

        if len(line) < 2:
            continue

        gaps = get_line_gaps(
            line
        )

        if not gaps:
            continue

        large_gaps = [
            gap
            for gap in gaps
            if gap["gap"] >= 35
        ]

        if large_gaps:

            candidates.append(
                index
            )

    if len(candidates) < 2:

        return []

    blocks = []

    current = [
        candidates[0]
    ]

    for index in candidates[1:]:

        previous = current[-1]

        if index - previous <= 2:

            current.append(
                index
            )

        else:

            if len(current) >= 2:

                blocks.append(
                    current
                )

            current = [
                index
            ]

    if len(current) >= 2:

        blocks.append(
            current
        )

    return blocks


# =========================================================
# ПОЛУЧЕНИЕ КОЛОНОК ТАБЛИЦЫ
# =========================================================

def build_table_from_lines(
    lines
):

    if len(lines) < 2:
        return None

    # -----------------------------------------------------
    # Собираем все позиции потенциальных колонок
    # -----------------------------------------------------

    positions = []

    for line in lines:

        gaps = get_line_gaps(
            line
        )

        for gap in gaps:

            if gap["gap"] >= 35:

                positions.append(
                    gap["position"]
                )

    if len(positions) < 2:

        return None

    # -----------------------------------------------------
    # Группируем близкие позиции
    # -----------------------------------------------------

    positions.sort()

    clusters = []

    for position in positions:

        if not clusters:

            clusters.append(
                [position]
            )

            continue

        if abs(
            position - statistics.mean(
                clusters[-1]
            )
        ) <= 60:

            clusters[-1].append(
                position
            )

        else:

            clusters.append(
                [position]
            )

    column_positions = [
        int(
            statistics.mean(
                cluster
            )
        )
        for cluster in clusters
        if cluster
    ]

    # Нужны хотя бы две колонки

    if len(column_positions) < 2:

        return None

    # -----------------------------------------------------
    # Ограничиваем количество колонок
    # -----------------------------------------------------

    if len(column_positions) > 8:

        column_positions = column_positions[:8]

    rows = []

    for line in lines:

        cells = [
            ""
            for _ in column_positions
        ]

        for word in line:

            x = word["left"]

            # Ищем ближайшую колонку слева

            distances = [
                abs(
                    x - position
                )
                for position in column_positions
            ]

            nearest = min(
                range(
                    len(distances)
                ),
                key=lambda i: distances[i]
            )

            # Если слово находится слишком далеко
            # от предполагаемой структуры,
            # относим его к первой подходящей колонке.

            if nearest >= len(cells):

                continue

            if cells[nearest]:

                cells[nearest] += " "

            cells[nearest] += word["text"]

        # -------------------------------------------------
        # Удаляем пустые хвостовые колонки
        # -------------------------------------------------

        while cells and not cells[-1]:

            cells.pop()

        if cells:

            rows.append(
                cells
            )

    if len(rows) < 2:

        return None

    # -----------------------------------------------------
    # Таблица должна действительно иметь
    # несколько заполненных колонок
    # -----------------------------------------------------

    filled_rows = 0

    for row in rows:

        if sum(
            1
            for cell in row
            if cell.strip()
        ) >= 2:

            filled_rows += 1

    if filled_rows < 2:

        return None

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

    # ВАЖНО:
    # больше не центрируем саму таблицу.

    table.alignment = (
        WD_TABLE_ALIGNMENT.LEFT
    )

    # Автоматическая ширина

    table.autofit = True

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

                value = row[
                    column_index
                ].strip()

            else:

                value = ""

            cell.text = value

            for paragraph in cell.paragraphs:

                paragraph.alignment = (
                    WD_ALIGN_PARAGRAPH.LEFT
                )

                paragraph.paragraph_format.space_after = Pt(0)
                paragraph.paragraph_format.space_before = Pt(0)

                for run in paragraph.runs:

                    run.font.name = "Arial"
                    run.font.size = Pt(10)

                    # Заголовок таблицы
                    # выделяем только если это
                    # первая строка.

                    if row_index == 0:

                        run.bold = True


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
# СОЗДАНИЕ WORD
# =========================================================

def create_word_document(
    text,
    ocr_data=None
):

    try:

        print(
            "📄 СОЗДАЁМ WORD",
            flush=True
        )

        document = Document()

        # -------------------------------------------------
        # Страница
        # -------------------------------------------------

        section = document.sections[0]

        section.top_margin = Cm(2)
        section.bottom_margin = Cm(2)
        section.left_margin = Cm(2)
        section.right_margin = Cm(2)

        # -------------------------------------------------
        # Основной стиль
        # -------------------------------------------------

        normal_style = document.styles[
            "Normal"
        ]

        normal_style.font.name = "Arial"
        normal_style.font.size = Pt(11)

        # -------------------------------------------------
        # Если есть OCR-координаты —
        # пытаемся восстановить таблицы.
        # -------------------------------------------------

        used_table_lines = set()

        if ocr_data:

            visual_lines = ocr_data.get(
                "lines",
                []
            )

            table_blocks = detect_table_blocks(
                visual_lines
            )

            print(
                "📊 Возможных таблиц:",
                len(table_blocks),
                flush=True
            )

            for block in table_blocks:

                block_lines = [
                    visual_lines[i]
                    for i in block
                    if i < len(visual_lines)
                ]

                table_rows = build_table_from_lines(
                    block_lines
                )

                if table_rows:

                    print(
                        "📊 Таблица восстановлена:",
                        len(table_rows),
                        "строк",
                        flush=True
                    )

                    add_table(
                        document,
                        table_rows
                    )

                    document.add_paragraph()

                    for index in block:

                        used_table_lines.add(
                            index
                        )

        # -------------------------------------------------
        # Если OCR-координат нет —
        # работаем обычным текстом.
        # -------------------------------------------------

        if ocr_data:

            lines = [
                line_to_text(line)
                for line in ocr_data.get(
                    "lines",
                    []
                )
            ]

        else:

            lines = text.splitlines()

        # -------------------------------------------------
        # Создаём обычный документ
        # -------------------------------------------------

        for index, line in enumerate(
            lines
        ):

            line = line.strip()

            # Пропускаем строки,
            # которые уже попали в таблицу.

            if index in used_table_lines:

                continue

            # Пустая строка

            if not line:

                paragraph = document.add_paragraph()

                paragraph.paragraph_format.space_after = Pt(2)

                continue

            # -------------------------------------------------
            # Заголовок
            # -------------------------------------------------

            if is_heading(line):

                paragraph = document.add_paragraph()

                # ВАЖНО:
                # только настоящий заголовок центрируем.

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

                if len(line) <= 50:

                    run.font.size = Pt(14)

                else:

                    run.font.size = Pt(12)

                continue

            # -------------------------------------------------
            # Нумерованный список
            # -------------------------------------------------

            if is_numbered_item(line):

                paragraph = document.add_paragraph()

                paragraph.alignment = (
                    WD_ALIGN_PARAGRAPH.LEFT
                )

                paragraph.paragraph_format.left_indent = Cm(0.4)

                paragraph.paragraph_format.first_line_indent = Cm(0)

                paragraph.paragraph_format.space_after = Pt(5)

                paragraph.paragraph_format.line_spacing = 1.15

                run = paragraph.add_run(
                    line
                )

                run.font.name = "Arial"
                run.font.size = Pt(11)

                continue

            # -------------------------------------------------
            # Маркированный список
            # -------------------------------------------------

            if is_list_item(line):

                paragraph = document.add_paragraph()

                paragraph.alignment = (
                    WD_ALIGN_PARAGRAPH.LEFT
                )

                paragraph.paragraph_format.left_indent = Cm(0.7)

                paragraph.paragraph_format.first_line_indent = Cm(0)

                paragraph.paragraph_format.space_after = Pt(4)

                run = paragraph.add_run(
                    line
                )

                run.font.name = "Arial"
                run.font.size = Pt(11)

                continue

            # -------------------------------------------------
            # Обычный текст
            # -------------------------------------------------

            paragraph = document.add_paragraph()

            paragraph.alignment = (
                WD_ALIGN_PARAGRAPH.LEFT
            )

            paragraph.paragraph_format.space_after = Pt(5)

            paragraph.paragraph_format.line_spacing = 1.15

            # ВАЖНО:
            # убираем искусственный отступ первой строки.
            #
            # Для OCR-документа он часто портит
            # исходное расположение.

            paragraph.paragraph_format.first_line_indent = Cm(0)

            run = paragraph.add_run(
                line
            )

            run.font.name = "Arial"
            run.font.size = Pt(11)

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
                    "text": "📸 Распознать документ",
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

        "Я могу превратить фотографию документа "
        "в редактируемый Word-файл.\n\n"

        "📸 Распознать документ\n"
        "📄 Восстановить Word\n"
        "🌐 Перевести текст\n"
        "✍️ Улучшить текст\n\n"

        "Просто отправь фотографию документа.",

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
        "🔎 Анализирую документ..."
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

        # Берём максимальное доступное качество

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

        # -------------------------------------------------
        # Открываем и готовим изображение
        # -------------------------------------------------

        image = Image.open(
            BytesIO(image_bytes)
        )

        prepared_image = prepare_image(
            image
        )

        # -------------------------------------------------
        # OCR
        # -------------------------------------------------

        ocr_data = recognize_document(
            prepared_image
        )

        if not ocr_data:

            send_message(
                chat_id,

                "😔 Я не смог распознать текст.\n\n"
                "Попробуй сфотографировать документ "
                "при хорошем освещении и без наклона."
            )

            return

        # -------------------------------------------------
        # Текст
        # -------------------------------------------------

        text = ocr_to_text(
            ocr_data
        )

        text = clean_ocr_text(
            text
        )

        if not text:

            send_message(
                chat_id,

                "😔 Текст на фотографии не найден."
            )

            return

        # -------------------------------------------------
        # Сохраняем и текст,
        # и координаты OCR
        # -------------------------------------------------

        user_texts[
            user_id
        ] = text

        user_ocr_data[
            user_id
        ] = ocr_data

        print(
            "✅ OCR СОХРАНЁН",
            "Символов:",
            len(text),
            "Слов:",
            len(
                ocr_data.get(
                    "words",
                    []
                )
            ),
            flush=True
        )

        send_long_message(
            chat_id,

            "📝 Распознанный текст:\n\n"
            + text
        )

        send_message(
            chat_id,

            "🤖 Документ проанализирован.\n\n"
            "Можно восстановить его структуру в Word.",

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

    ocr_data = user_ocr_data.get(
        user_id
    )

    send_message(
        chat_id,

        "📄 Восстанавливаю документ...\n\n"
        "🔎 Анализирую расположение текста\n"
        "📊 Проверяю таблицы\n"
        "📝 Формирую Word"
    )

    file_path = create_word_document(
        text,
        ocr_data
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
                "📄 Документ восстановлен в Word.\n\n"
                "Если что-то получилось неправильно — "
                "пришли фотографию, и мы будем улучшать "
                "распознавание."
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

            # Не меняем символы.
            # Только удаляем лишние пробелы.

            line = re.sub(
                r"[ \t]+",
                " ",
                line
            ).strip()

            if line:

                lines.append(
                    line
                )

        return "\n".join(
            lines
        ).strip()

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
                    "text": "📄 Восстанавливаю документ..."
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
