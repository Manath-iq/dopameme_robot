from PIL import Image, ImageDraw, ImageFont, ImageOps
import os
import uuid

# Попытка найти шрифты
def get_font(size, font_name="Arial"):
    # Always look in the project's assets/fonts directory first
    local_font_path = os.path.join("assets", "fonts", f"{font_name}.ttf")
    if os.path.exists(local_font_path):
        return ImageFont.truetype(local_font_path, size)
    
    # Fallback to default if not found
    print(f"Warning: Font {font_name}.ttf not found in assets/fonts/, using default.")
    return ImageFont.load_default()

def wrap_text(text, font, max_width, draw):
    lines = []
    words = text.split()
    current_line = []
    
    for word in words:
        test_line = current_line + [word]
        bbox = draw.textbbox((0, 0), " ".join(test_line), font=font)
        w = bbox[2] - bbox[0]
        if w > max_width:
            if len(current_line) > 0:
                lines.append(" ".join(current_line))
                current_line = [word]
            else:
                # Слово длиннее ширины, придется писать как есть
                lines.append(word)
                current_line = []
        else:
            current_line = test_line
            
    if current_line:
        lines.append(" ".join(current_line))
    return lines

def generate_meme(template_path, top_text, bottom_text):
    img = Image.open(template_path).convert("RGB")
    draw = ImageDraw.Draw(img)
    width, height = img.size
    
    # Helper to calculate font size based on text length
    def get_dynamic_font(text):
        if not text:
            return get_font(int(width / 10), "Impact")
            
        length = len(text)
        if length < 20:
            size = int(width / 10)
        elif length < 50:
            size = int(width / 15)
        else:
            size = int(width / 22)
            
        # Minimum readable size
        size = max(size, 20)
        return get_font(size, "Impact")
    
    def draw_text_with_outline(text, y_pos, is_bottom=False):
        if not text: return
        
        # Get specific font for this text block
        font = get_dynamic_font(text)
        
        lines = wrap_text(text, font, width - 20, draw)
        
        total_text_height = 0
        line_heights = []
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            h = bbox[3] - bbox[1]
            line_heights.append(h + 10)
            total_text_height += h + 10
            
        current_y = y_pos
        if is_bottom:
             current_y = height - total_text_height - 20

        for i, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=font)
            w = bbox[2] - bbox[0]
            x = (width - w) / 2
            
            # Outline
            outline_width = 3
            for dx in range(-outline_width, outline_width+1):
                for dy in range(-outline_width, outline_width+1):
                    draw.text((x+dx, current_y+dy), line, font=font, fill="black")
            
            draw.text((x, current_y), line, font=font, fill="white")
            current_y += line_heights[i]

    draw_text_with_outline(top_text.upper(), 10)
    draw_text_with_outline(bottom_text.upper(), 0, is_bottom=True)
    
    if not os.path.exists("assets/generated"):
        os.makedirs("assets/generated")
        
    output_path = f"assets/generated/{uuid.uuid4()}.jpg"
    img.save(output_path)
    return output_path

def generate_demotivator(template_path, text):
    img = Image.open(template_path).convert("RGB")
    
    # Рамка вокруг фото
    border_width = 3
    img_with_border = ImageOps.expand(img, border=border_width, fill='white')
    # Дополнительная черная мини-рамка внутри (классика)
    img_with_border = ImageOps.expand(img_with_border, border=1, fill='black')
    
    iw, ih = img_with_border.size
    
    padding_top = 50
    padding_side = 50
    padding_bottom_min = 100
    
    font_size = int(iw / 12)
    font = get_font(font_size, "Times New Roman")
    
    # Считаем высоту текста
    # Создаем временный канвас для измерения
    dummy = Image.new('RGB', (1,1))
    draw_dummy = ImageDraw.Draw(dummy)
    lines = wrap_text(text, font, iw, draw_dummy)
    
    text_height = len(lines) * (font_size + 15)
    padding_bottom = max(padding_bottom_min, text_height + 50)
    
    canvas_w = iw + padding_side * 2
    canvas_h = ih + padding_top + padding_bottom
    
    canvas = Image.new('RGB', (canvas_w, canvas_h), "black")
    canvas.paste(img_with_border, (padding_side, padding_top))
    
    draw = ImageDraw.Draw(canvas)
    
    current_y = padding_top + ih + 30
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        w = bbox[2] - bbox[0]
        x = (canvas_w - w) / 2
        draw.text((x, current_y), line, font=font, fill="white")
        current_y += font_size + 15
        
    if not os.path.exists("assets/generated"):
        os.makedirs("assets/generated")
    output_path = f"assets/generated/{uuid.uuid4()}.jpg"
    
    canvas.save(output_path)
    return output_path
