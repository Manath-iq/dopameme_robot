from PIL import Image, ImageDraw, ImageFont, ImageOps
import os
import uuid
import logging
import config

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Попытка найти шрифты
_loaded_fonts = {}

def get_font(size, font_name="Arial"):
    # Check if font is already loaded for this size
    font_key = (font_name, size)
    if font_key in _loaded_fonts:
        return _loaded_fonts[font_key]

    # Try to load from assets/fonts
    local_font_path = os.path.join(config.FONTS_DIR, f"{font_name}.ttf")
    if os.path.exists(local_font_path):
        font = ImageFont.truetype(local_font_path, size)
        _loaded_fonts[font_key] = font
        return font
    
    # Fallback to default if not found
    logging.warning(f"Font {font_name}.ttf not found in {config.FONTS_DIR}, using default.")
    font = ImageFont.load_default(size=size) # load_default can take size in newer PIL
    _loaded_fonts[font_key] = font
    return font

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

def add_watermark(img):
    """Adds a semi-transparent watermark @dopamemerobot to the bottom-left."""
    try:
        # Create a drawing context for the watermark
        # Use RGBA for transparency
        if img.mode != 'RGBA':
            img = img.convert("RGBA")
            
        width, height = img.size
        txt = Image.new('RGBA', img.size, (255,255,255,0))
        d = ImageDraw.Draw(txt)
        
        # Calculate size proportional to image (Reduced to 3.5%)
        # Using min(width, height) is safer for extreme aspect ratios
        font_size = max(15, int(min(width, height) * config.WATERMARK_FONT_SIZE_FACTOR)) 
        font = get_font(font_size, config.MEME_FONT_NAME) # Using MEME_FONT_NAME for watermark for now
        
        text = config.WATERMARK_TEXT
        
        # Get text size
        bbox = d.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        
        # Position: bottom left with margin
        margin = max(10, int(font_size / 2))
        x = margin
        y = height - text_h - margin * 1.5 
        
        # Dynamic outline width (proportional to font size)
        outline_width = max(1, int(font_size // config.WATERMARK_OUTLINE_WIDTH_FACTOR))
        
        # Draw outline (black, 60% opacity)
        for dx in range(-outline_width, outline_width+1):
            for dy in range(-outline_width, outline_width+1):
                if dx == 0 and dy == 0: continue
                # Draw circular-ish stroke for better quality
                if dx*dx + dy*dy > outline_width*outline_width: continue
                
                d.text((x+dx, y+dy), text, font=font, fill=(0, 0, 0, config.WATERMARK_ALPHA))
        
        # Draw main text (white, 60% opacity)
        d.text((x, y), text, font=font, fill=(255, 255, 255, config.WATERMARK_ALPHA))
        
        # Composite
        out = Image.alpha_composite(img, txt)
        return out.convert("RGB")
        
    except Exception as e:
        logging.error(f"Watermark failed: {e}")
        return img.convert("RGB")

def generate_meme(template_path, top_text, bottom_text):
    img = Image.open(template_path).convert("RGB")
    draw = ImageDraw.Draw(img)
    width, height = img.size
    
    # Helper to calculate font size based on text length
    def get_dynamic_font(text):
        if not text:
            return get_font(int(width / config.MEME_FONT_SIZE_LARGE_TEXT), config.MEME_FONT_NAME)
            
        length = len(text)
        if length < 20:
            size = int(width / config.MEME_FONT_SIZE_LARGE_TEXT)
        elif length < 50:
            size = int(width / config.MEME_FONT_SIZE_MEDIUM_TEXT)
        else:
            size = int(width / config.MEME_FONT_SIZE_SMALL_TEXT)
            
        # Minimum readable size
        size = max(size, 20)
        return get_font(size, config.MEME_FONT_NAME)
    
    def draw_text_with_outline(text, y_pos, is_bottom=False):
        if not text: return
        
        # Get specific font for this text block
        font = get_dynamic_font(text)
        
        lines = wrap_text(text, font, width - config.MEME_TEXT_PADDING, draw)
        
        total_text_height = 0
        line_heights = []
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            h = bbox[3] - bbox[1]
            line_heights.append(h + 10)
            total_text_height += h + 10
            
        current_y = y_pos
        if is_bottom:
             current_y = height - total_text_height - config.MEME_TEXT_PADDING

        for i, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=font)
            w = bbox[2] - bbox[0]
            x = (width - w) / 2
            
            # Outline
            outline_width = config.MEME_TEXT_OUTLINE_WIDTH
            for dx in range(-outline_width, outline_width+1):
                for dy in range(-outline_width, outline_width+1):
                    draw.text((x+dx, current_y+dy), line, font=font, fill="black")
            
            draw.text((x, current_y), line, font=font, fill="white")
            current_y += line_heights[i]

    draw_text_with_outline(top_text.upper(), config.MEME_TOP_TEXT_Y_OFFSET)
    draw_text_with_outline(bottom_text.upper(), config.MEME_BOTTOM_TEXT_Y_OFFSET, is_bottom=True)
    
    # Add Watermark
    img = add_watermark(img)
        
    output_path = f"{config.GENERATED_DIR}/{uuid.uuid4()}.jpg"
    img.save(output_path)
    return output_path

def generate_demotivator(template_path, text):
    img = Image.open(template_path).convert("RGB")
    
    # Рамка вокруг фото
    border_width = config.DEMOTIVATOR_BORDER_WIDTH
    img_with_border = ImageOps.expand(img, border=border_width, fill='white')
    # Дополнительная черная мини-рамка внутри (классика)
    img_with_border = ImageOps.expand(img_with_border, border=config.DEMOTIVATOR_INNER_BORDER_WIDTH, fill='black')
    
    iw, ih = img_with_border.size
    
    padding_top = config.DEMOTIVATOR_PADDING_TOP
    padding_side = config.DEMOTIVATOR_PADDING_SIDE
    padding_bottom_min = config.DEMOTIVATOR_PADDING_BOTTOM_MIN
    
    font_size = int(iw / 12)
    font = get_font(font_size, config.DEMOTIVATOR_FONT_NAME)
    
    # Считаем высоту текста
    # Создаем временный канвас для измерения
    dummy = Image.new('RGB', (1,1))
    draw_dummy = ImageDraw.Draw(dummy)
    lines = wrap_text(text, font, iw, draw_dummy)
    
    text_height = len(lines) * (font_size + config.DEMOTIVATOR_LINE_SPACING)
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
        current_y += font_size + config.DEMOTIVATOR_LINE_SPACING
    
    # Add Watermark
    canvas = add_watermark(canvas)
        
    output_path = f"{config.GENERATED_DIR}/{uuid.uuid4()}.jpg"
    
    canvas.save(output_path)
    return output_path

def prepare_for_sticker(image_path):
    """
    Converts an image to Telegram sticker format:
    - PNG or WEBP
    - One side exactly 512px, the other <= 512px
    """
    img = Image.open(image_path).convert("RGBA")
    
    width, height = img.size
    
    if width >= height:
        new_width = config.STICKER_SIZE
        new_height = int(height * (config.STICKER_SIZE / width))
    else:
        new_height = config.STICKER_SIZE
        new_width = int(width * (config.STICKER_SIZE / height))
        
    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
    output_path = f"{config.GENERATED_DIR}/{uuid.uuid4()}.png"
    img.save(output_path, "PNG")
    return output_path