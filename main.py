import os
import logging
import uuid
import asyncio
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputSticker
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler

from utils.image_generator import generate_meme, generate_demotivator, prepare_for_sticker
from utils.effects import liquid_resize, deep_fry_effect, warp_effect, crispy_effect, lens_bulge_effect, lens_pinch_effect

# Загрузка переменных окружения
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Состояния
WAITING_MEME_TEXT = 1
WAITING_DEMOTIVATOR_TEXT = 2

# Директории
TEMPLATE_DIR = "assets/templates"
USER_UPLOAD_DIR = "assets/user_uploads"

if not os.path.exists(USER_UPLOAD_DIR):
    os.makedirs(USER_UPLOAD_DIR)

def get_templates():
    return sorted([f for f in os.listdir(TEMPLATE_DIR) if f.lower().endswith(('.jpg', '.jpeg', '.png'))])

# --- КЛАВИАТУРЫ ---

def get_gallery_keyboard(current_index, sticker_mode=False):
    select_text = "✅ Выбрать"
    keyboard = [
        [
            InlineKeyboardButton("⬅️", callback_data=f"prev_{current_index}"),
            InlineKeyboardButton(select_text, callback_data=f"select_meme_{current_index}"),
            InlineKeyboardButton("➡️", callback_data=f"next_{current_index}"),
        ],
        [
            InlineKeyboardButton("🖼 Демотиватор", callback_data=f"select_dem_{current_index}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_user_photo_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("✅ Мем", callback_data="user_select_meme"),
            InlineKeyboardButton("🖼 Демотиватор", callback_data="user_select_dem")
        ],
        [
            InlineKeyboardButton("✨ Эффекты", callback_data="user_select_effects")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_sticker_intermediate_keyboard():
    keyboard = [
        [InlineKeyboardButton("➕ Добавить ещё", callback_data="sticker_continue")],
        [InlineKeyboardButton("🏁 Завершить пак", callback_data="sticker_finish")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_sticker_final_keyboard(url):
    keyboard = [
        [InlineKeyboardButton("📥 Сохранить стикерпак", url=url)]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- УТИЛИТА ОБРАБОТКИ ФОТО ---

async def process_photo_setup(update: Update, context: ContextTypes.DEFAULT_TYPE, photo_obj):
    """Универсальная функция: скачивает фото и показывает меню выбора действий."""
    photo_file = await photo_obj.get_file()
    file_path = os.path.join(USER_UPLOAD_DIR, f"{uuid.uuid4()}.jpg")
    await photo_file.download_to_drive(file_path)
    
    context.user_data['user_template'] = file_path
    
    # Проверяем режим стикеров
    sticker_mode = context.user_data.get('sticker_mode', False)
    text = "Фото получено! Что делаем?"
    if sticker_mode:
        text = "Фото для стикера загружено. Выберите обработку:"
        
    await update.effective_message.reply_text(text, reply_markup=get_user_photo_keyboard())
    return ConversationHandler.END

# --- ЛОГИКА ОТОБРАЖЕНИЯ ГАЛЕРЕИ ---

async def show_gallery(update: Update, context: ContextTypes.DEFAULT_TYPE, edit=False):
    templates = get_templates()
    chat_id = update.effective_chat.id
    
    if not templates:
        text = "Шаблоны не найдены! Добавьте .jpg файлы в assets/templates"
        if edit and update.callback_query:
            await update.callback_query.message.edit_text(text)
        else:
            await context.bot.send_message(chat_id=chat_id, text=text)
        return ConversationHandler.END

    current_index = context.user_data.get('gallery_index', 0)
    if current_index >= len(templates) or current_index < 0:
        current_index = 0
        context.user_data['gallery_index'] = 0
        
    template_path = os.path.join(TEMPLATE_DIR, templates[current_index])
    sticker_mode = context.user_data.get('sticker_mode', False)
    
    if sticker_mode:
        caption = "🎨 Создание стикерпака\nВыберите шаблон или отправьте своё фото:"
    else:
        caption = "Выберите шаблон для мема или отправьте своё фото:"

    keyboard = get_gallery_keyboard(current_index, sticker_mode)

    try:
        if edit and update.callback_query:
            with open(template_path, 'rb') as f:
                media = InputMediaPhoto(media=f, caption=caption)
                await update.callback_query.edit_message_media(media=media, reply_markup=keyboard)
        else:
            with open(template_path, 'rb') as f:
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=f,
                    caption=caption,
                    reply_markup=keyboard
                )
    except Exception as e:
        logging.error(f"Gallery error: {e}")
        await context.bot.send_message(chat_id=chat_id, text="❌ Ошибка при загрузке изображения.")

# --- ХЕНДЛЕРЫ КОМАНД ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Стартовое меню ИЛИ обработка реплая на фото.
    """
    message = update.message
    
    # СЦЕНАРИЙ 1: Пользователь ответил тегом бота на чье-то фото
    if message.reply_to_message and message.reply_to_message.photo:
        # Берем фото из оригинального сообщения (самое большое качество)
        photo = message.reply_to_message.photo[-1]
        await process_photo_setup(update, context, photo)
        return ConversationHandler.END

    # СЦЕНАРИЙ 2: Обычный запуск (Галерея)
    context.user_data.clear() 
    
    keyboard = [
        [InlineKeyboardButton("🤣 Создать Мем", callback_data="mode_meme")],
        [InlineKeyboardButton("📦 Создать Стикерпак", callback_data="mode_pack")]
    ]
    
    await message.reply_text(
        "Привет! Я **DopaMeme Bot**.\nЧто будем создавать?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    return ConversationHandler.END

async def handle_user_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка прямой отправки фото (с подписью или в личке)"""
    photo = update.message.photo[-1]
    await process_photo_setup(update, context, photo)
    return ConversationHandler.END

# --- ОБРАБОТКА КНОПОК И ГЕНЕРАЦИЯ ---
# (Остальной код остается без изменений, но я его полностью приведу для целостности файла)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    # 1. МЕНЮ
    if data == "mode_meme":
        context.user_data['sticker_mode'] = False
        await query.message.delete()
        await show_gallery(update, context, edit=False)
        return

    elif data == "mode_pack":
        context.user_data['sticker_mode'] = True
        context.user_data['pack_created'] = False
        user_id = update.effective_user.id
        bot = await context.bot.get_me()
        unique_id = str(uuid.uuid4()).replace('-', '')[:8]
        context.user_data['pack_name'] = f"pack_{user_id}_{unique_id}_by_{bot.username}"
        context.user_data['pack_title'] = f"DopaMeme Pack {unique_id}"
        await query.message.delete()
        await show_gallery(update, context, edit=False)
        return

    # 2. СТИКЕРЫ
    elif data == "sticker_continue":
        await query.message.delete()
        await show_gallery(update, context, edit=False)
        return
    elif data == "sticker_finish":
        if not context.user_data.get('pack_created'):
            await query.message.edit_text("Пак пуст. Создайте хотя бы один мем!")
            return ConversationHandler.END
        pack_name = context.user_data.get('pack_name')
        link = f"https://t.me/addstickers/{pack_name}"
        await query.message.delete()
        await query.message.reply_text("✅ **Стикерпак готов!**\n\nНажмите кнопку ниже, чтобы добавить его к себе.", reply_markup=get_sticker_final_keyboard(link), parse_mode='Markdown')
        context.user_data.clear()
        return ConversationHandler.END

    # 3. ЭФФЕКТЫ
    elif data == "user_select_effects":
        keyboard = [
            [InlineKeyboardButton("🫠 Жидкий", callback_data="effect_liquid")],
            [InlineKeyboardButton("🍟 Прожарка", callback_data="effect_deepfry")],
            [InlineKeyboardButton("🌀 Вихрь", callback_data="effect_warp")],
            [InlineKeyboardButton("👁️‍🗨️ Криспи", callback_data="effect_crispy")],
            [InlineKeyboardButton("👀 Рыбий глаз", callback_data="effect_bulge")],
            [InlineKeyboardButton("🕳️ Дырка", callback_data="effect_pinch")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_user_photo")]
        ]
        await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
        return
    elif data == "back_to_user_photo":
        await query.message.edit_reply_markup(reply_markup=get_user_photo_keyboard())
        return

    if data.startswith("effect_"):
        if 'user_template' not in context.user_data:
             await query.message.edit_text("Ошибка: фото потеряно.")
             return ConversationHandler.END
        template_path = context.user_data['user_template']
        effect_map = {
            "effect_liquid": (liquid_resize, {"scale": 0.5}, "🫠"),
            "effect_deepfry": (deep_fry_effect, {}, "🍟"),
            "effect_warp": (warp_effect, {}, "🌀"),
            "effect_crispy": (crispy_effect, {}, "👁️‍🗨️"),
            "effect_bulge": (lens_bulge_effect, {}, "👀"),
            "effect_pinch": (lens_pinch_effect, {}, "🕳️"),
        }
        func, kwargs, emoji = effect_map[data]
        await query.message.edit_text(f"{emoji} Обрабатываю...", reply_markup=None)
        msg = query.message
        try:
            output_path = func(template_path, **kwargs)
            await finalize_generation(update, context, output_path, msg)
            if os.path.exists(template_path): os.remove(template_path)
            return ConversationHandler.END
        except Exception as e:
            logging.error(f"Effect error: {e}")
            await msg.edit_text("❌ Ошибка при обработке.")
            return ConversationHandler.END

    # 4. ВЫБОР РЕЖИМА
    if data == "user_select_meme":
        if 'user_template' not in context.user_data:
            await query.message.edit_text("Ошибка: фото потеряно.")
            return ConversationHandler.END
        context.user_data['template'] = context.user_data['user_template']
        await query.message.edit_text("📝 Введите текст для мема (Верх . Низ):")
        return WAITING_MEME_TEXT
    elif data == "user_select_dem":
        if 'user_template' not in context.user_data:
             await query.message.edit_text("Ошибка: фото потеряно.")
             return ConversationHandler.END
        context.user_data['template'] = context.user_data['user_template']
        await query.message.edit_text("🖼 Введите текст для демотиватора:")
        return WAITING_DEMOTIVATOR_TEXT

    # 5. ГАЛЕРЕЯ
    try:
        parts = data.rsplit('_', 1)
        action_base = parts[0]
        index = int(parts[1])
    except:
        return 
    templates = get_templates()
    if action_base == "prev" or action_base == "next":
        new_index = (index - 1) % len(templates) if action_base == "prev" else (index + 1) % len(templates)
        context.user_data['gallery_index'] = new_index
        await show_gallery(update, context, edit=True)
        return
    elif action_base == "select_meme":
        context.user_data['template'] = os.path.join(TEMPLATE_DIR, templates[index])
        await query.message.edit_caption(caption="📝 Введите текст для мема (Верх . Низ):", reply_markup=None)
        return WAITING_MEME_TEXT
    elif action_base == "select_dem":
        context.user_data['template'] = os.path.join(TEMPLATE_DIR, templates[index])
        await query.message.edit_caption(caption="🖼 Введите текст для демотиватора:", reply_markup=None)
        return WAITING_DEMOTIVATOR_TEXT

async def generate_meme_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    template_path = context.user_data.get('template')
    if not template_path or not os.path.exists(template_path):
        await update.message.reply_text("Ошибка: шаблон не найден.")
        return ConversationHandler.END
    parts = text.split('.', 1)
    top_text = parts[0].strip()
    bottom_text = parts[1].strip() if len(parts) > 1 else ""
    msg = await update.message.reply_text("🎨 Рисую...")
    try:
        output_path = generate_meme(template_path, top_text, bottom_text)
        await finalize_generation(update, context, output_path, msg)
        if "user_uploads" in template_path and os.path.exists(template_path):
            os.remove(template_path)
    except Exception as e:
        logging.error(f"Generate Meme Error: {e}")
        await msg.edit_text("❌ Ошибка генерации.")
    return ConversationHandler.END

async def generate_demotivator_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    template_path = context.user_data.get('template')
    if not template_path or not os.path.exists(template_path):
        await update.message.reply_text("Ошибка: шаблон не найден.")
        return ConversationHandler.END
    msg = await update.message.reply_text("🎨 Рисую...")
    try:
        output_path = generate_demotivator(template_path, text)
        await finalize_generation(update, context, output_path, msg)
        if "user_uploads" in template_path and os.path.exists(template_path):
            os.remove(template_path)
    except Exception as e:
        logging.error(f"Generate Dem Error: {e}")
        await msg.edit_text("❌ Ошибка генерации.")
    return ConversationHandler.END

async def finalize_generation(update: Update, context: ContextTypes.DEFAULT_TYPE, image_path, loading_msg):
    try:
        if context.user_data.get('sticker_mode'):
            sticker_path = prepare_for_sticker(image_path)
            os.remove(image_path)
            user_id = update.effective_user.id
            pack_name = context.user_data['pack_name']
            pack_title = context.user_data['pack_title']
            try:
                with open(sticker_path, 'rb') as f:
                    sticker_input = InputSticker(f, emoji_list=["😀"])
                    if not context.user_data.get('pack_created'):
                        await context.bot.create_new_sticker_set(user_id=user_id, name=pack_name, title=pack_title, stickers=[sticker_input], sticker_format="static")
                        context.user_data['pack_created'] = True
                    else:
                        await context.bot.add_sticker_to_set(user_id=user_id, name=pack_name, sticker=sticker_input)
                with open(sticker_path, 'rb') as f:
                    await loading_msg.delete()
                    await update.effective_message.reply_document(document=f, caption="✅ Стикер добавлен!", reply_markup=get_sticker_intermediate_keyboard())
            except Exception as e:
                logging.error(f"Sticker API Error: {e}")
                await loading_msg.edit_text(f"❌ Ошибка Telegram: {e}")
            finally:
                if os.path.exists(sticker_path): os.remove(sticker_path)
        else:
            with open(image_path, 'rb') as f:
                await update.effective_message.reply_photo(f)
            await loading_msg.delete()
            os.remove(image_path)
    except Exception as e:
        logging.error(f"Finalize Error: {e}")
        if os.path.exists(image_path): os.remove(image_path)
        await loading_msg.edit_text("❌ Критическая ошибка.")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменено. Введите /start.")
    return ConversationHandler.END

def cleanup_temp_files():
    dirs_to_clean = [USER_UPLOAD_DIR, "assets/generated"]
    for d in dirs_to_clean:
        if os.path.exists(d):
            for f in os.listdir(d):
                file_path = os.path.join(d, f)
                try:
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                except Exception as e:
                    print(f"Error cleaning {file_path}: {e}")

if __name__ == '__main__':
    if not TOKEN:
        print("Error: BOT_TOKEN not found in .env")
        exit(1)
    cleanup_temp_files()
    import threading
    from http.server import HTTPServer, BaseHTTPRequestHandler
    class HealthCheck(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Bot is alive!")
    def run_web_server():
        port = int(os.environ.get("PORT", 8080))
        server = HTTPServer(('0.0.0.0', port), HealthCheck)
        server.serve_forever()
    threading.Thread(target=run_web_server, daemon=True).start()
    
    application = ApplicationBuilder().token(TOKEN).build()
    
    # ФИЛЬТРЫ ЗАПУСКА
    # start_filter ловит:
    # 1. Личку: текст без команд
    # 2. Группы: текст с упоминанием (@bot)
    # 3. ВСЕ ЧАТЫ: Реплай на сообщение (чтобы поймать реплай на фото с тегом)
    start_filter = (
        (filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND) | 
        ((filters.ChatType.GROUPS | filters.ChatType.SUPERGROUP) & filters.TEXT & filters.Mention)
    )

    # ФИЛЬТР ДЛЯ ФОТО
    # photo_filter ловит:
    # 1. Личка: любое фото
    # 2. Группы: фото, в подписи которого есть упоминание (@bot)
    photo_filter = filters.PHOTO & (filters.ChatType.PRIVATE | filters.Mention)

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            MessageHandler(start_filter, start),
            CallbackQueryHandler(button_handler),
            MessageHandler(photo_filter, handle_user_photo)
        ],
        states={
            WAITING_MEME_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, generate_meme_handler)],
            WAITING_DEMOTIVATOR_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, generate_demotivator_handler)],
        },
        fallbacks=[CommandHandler('cancel', cancel), CommandHandler('start', start)]
    )
    
    application.add_handler(conv_handler)
    print("Бот запущен!")
    application.run_polling()