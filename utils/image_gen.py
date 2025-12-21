from PIL import Image, ImageDraw, ImageFont
import textwrap
import os

def generate_meme(template_path: str, top_text: str, bottom_text: str, output_path: str = "meme_output.jpg"):
    """
    Накладывает текст на шаблон мема.
    """
    try:
        image = Image.open(template_path)
    except FileNotFoundError:
        return None

    draw = ImageDraw.Draw(image)
    image_width, image_height = image.size

    # Попытка загрузить шрифт.
    # На macOS часто есть Arial.ttf или similar.
    # Если не найдет, будет использовать дефолтный (мелкий и некрасивый), но рабочий.
    font_path = "/System/Library/Fonts/Supplemental/Arial.ttf"
    if not os.path.exists(font_path):
         font_path = "/System/Library/Fonts/Helvetica.ttc" # Fallback for mac

    try:
        # Размер шрифта зависит от ширины картинки (примерно 10% ширины)
        font_size = int(image_width / 10)
        font = ImageFont.truetype(font_path, font_size)
    except OSError:
        font = ImageFont.load_default()

    # Цвет текста и обводки (Классический мем: белый с черной обводкой)
    text_color = "white"
    stroke_color = "black"
    stroke_width = 2

    def draw_text(text, position):
        if not text:
            return
        
        # Подготовка текста (перенос строк)
        # Примерно 15 символов на строку для такого размера шрифта
        chars_per_line = int(image_width / (font_size * 0.6))
        lines = textwrap.wrap(text.upper(), width=chars_per_line) # Мемы обычно капсом

        # Расчет высоты блока текста
        # getbbox возвращает (left, top, right, bottom)
        # Нам нужна высота одной строки
        sample_bbox = draw.textbbox((0, 0), "A", font=font)
        line_height = sample_bbox[3] - sample_bbox[1] + 5 # + padding
        
        total_text_height = len(lines) * line_height

        # Определение Y координаты начала
        if position == "top":
            y_text = 10
        else: # bottom
            y_text = image_height - total_text_height - 10

        for line in lines:
            # Центрирование
            bbox = draw.textbbox((0, 0), line, font=font)
            line_width = bbox[2] - bbox[0]
            x_text = (image_width - line_width) / 2

            # Рисование обводки (простой способ - рисовать текст несколько раз со смещением)
            # В новых версиях Pillow есть stroke_width, используем его
            draw.text((x_text, y_text), line, font=font, fill=text_color, stroke_width=stroke_width, stroke_fill=stroke_color)
            
            y_text += line_height

    draw_text(top_text, "top")
    draw_text(bottom_text, "bottom")

    image.save(output_path)
    return output_path
