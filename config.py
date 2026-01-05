# config.py

import os

# --- General Configuration ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "@dopamemechan")

# --- Directories ---
TEMPLATE_DIR = "assets/templates"
USER_UPLOAD_DIR = "assets/user_uploads"
GENERATED_DIR = "assets/generated"
FONTS_DIR = "assets/fonts"

# --- Telegram Bot States ---
WAITING_MEME_TEXT = 1
WAITING_DEMOTIVATOR_TEXT = 2

# --- Sticker Configuration ---
STICKER_SIZE = 512 # One side exactly 512px, the other <= 512px
STICKER_EMOJI = "😀" # Default emoji for stickers
STICKER_FORMAT = "static" # Telegram sticker format

# --- Image Generation Configuration (image_generator.py) ---
MEME_FONT_NAME = "Impact"
DEMOTIVATOR_FONT_NAME = "Times New Roman"
WATERMARK_TEXT = "@dopamemerobot"
WATERMARK_FONT_SIZE_FACTOR = 0.035 # Factor of min(width, height) for watermark font size
WATERMARK_OUTLINE_WIDTH_FACTOR = 15 # Outline width = font_size // this factor
WATERMARK_ALPHA = 153 # Alpha transparency for watermark (out of 255)

# Meme specific
MEME_TOP_TEXT_Y_OFFSET = 10
MEME_BOTTOM_TEXT_Y_OFFSET = 0
MEME_TEXT_OUTLINE_WIDTH = 3
MEME_TEXT_PADDING = 20 # Padding for text wrapping
MEME_FONT_SIZE_SMALL_TEXT = 22 # For text > 50 chars
MEME_FONT_SIZE_MEDIUM_TEXT = 15 # For text 20-50 chars
MEME_FONT_SIZE_LARGE_TEXT = 10 # For text < 20 chars

# Demotivator specific
DEMOTIVATOR_BORDER_WIDTH = 3
DEMOTIVATOR_INNER_BORDER_WIDTH = 1
DEMOTIVATOR_PADDING_TOP = 50
DEMOTIVATOR_PADDING_SIDE = 50
DEMOTIVATOR_PADDING_BOTTOM_MIN = 100
DEMOTIVATOR_LINE_SPACING = 15 # Added to font_size for line height

# --- Effect Configuration (effects.py) ---
EFFECTS_MAX_SIZE_DEFAULT = 600 # Default max size for images before applying effects
EFFECTS_MAX_SIZE_DEEPFRY = 800 # Specific max size for deep fry
EFFECTS_MAX_SIZE_CRISPY = 800 # Specific max size for crispy

# Liquid Resize
LIQUID_RESIZE_MAX_SIZE = 500
LIQUID_RESIZE_SEAM_SAFETY_LIMIT = 200 # Max seams to remove in one dimension

# Deep Fry
DEEPFRY_NOISE_RANGE = (0, 25) # Min, Max for noise
DEEPFRY_COLOR_ENHANCE_FACTOR = 3.0
DEEPFRY_CONTRAST_ENHANCE_FACTOR = 2.0
DEEPFRY_SHARPNESS_ENHANCE_FACTOR = 5.0
DEEPFRY_JPEG_QUALITY = 8

# Warp (Swirl)
WARP_STRENGTH = 5.0

# Lens (Bulge/Pinch)
BULGE_K_VALUE = -0.5 # Negative for bulge
PINCH_K_VALUE = 0.5  # Positive for pinch

# Crispy
CRISPY_SHARPNESS_ENHANCE_FACTOR = 15.0
CRISPY_CONTRAST_ENHANCE_FACTOR = 3.0
CRISPY_BRIGHTNESS_ENHANCE_FACTOR = 1.5

# --- Callback Data ---
CALLBACK_MODE_MEME = "mode_meme"
CALLBACK_MODE_PACK = "mode_pack"

CALLBACK_STICKER_CONTINUE = "sticker_continue"
CALLBACK_STICKER_FINISH = "sticker_finish"

CALLBACK_USER_SELECT_MEME = "user_select_meme"
CALLBACK_USER_SELECT_DEM = "user_select_dem"
CALLBACK_USER_SELECT_EFFECTS = "user_select_effects"

CALLBACK_EFFECT_LIQUID = "effect_liquid"
CALLBACK_EFFECT_DEEPFRY = "effect_deepfry"
CALLBACK_EFFECT_WARP = "effect_warp"
CALLBACK_EFFECT_CRISPY = "effect_crispy"
CALLBACK_EFFECT_BULGE = "effect_bulge"
CALLBACK_EFFECT_PINCH = "effect_pinch"
CALLBACK_BACK_TO_USER_PHOTO = "back_to_user_photo"

# Gallery navigation
CALLBACK_GALLERY_PREV_PREFIX = "prev_"
CALLBACK_GALLERY_NEXT_PREFIX = "next_"
CALLBACK_GALLERY_SELECT_MEME_PREFIX = "select_meme_"
CALLBACK_GALLERY_SELECT_DEM_PREFIX = "select_dem_"
