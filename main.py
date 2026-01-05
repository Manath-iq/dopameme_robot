import os
import logging
import uuid
import asyncio
import random
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputSticker
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler

from utils.image_generator import generate_meme, generate_demotivator, prepare_for_sticker
from utils.effects import liquid_resize, deep_fry_effect, warp_effect, crispy_effect, lens_bulge_effect, lens_pinch_effect
import config

# Загрузка переменных окружения
load_dotenv()

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Директории
if not os.path.exists(config.USER_UPLOAD_DIR):
    os.makedirs(config.USER_UPLOAD_DIR)

# Caching for templates
_templates_cache = None

def get_templates():
    global _templates_cache
    if _templates_cache is None:
        _templates_cache = sorted([f for f in os.listdir(config.TEMPLATE_DIR) if f.lower().endswith(('.jpg', '.jpeg', '.png'))])
    return _templates_cache

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

async def check_subscription(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Проверяет, подписан ли пользователь на указанный канал."""
    try:
        member = await context.bot.get_chat_member(chat_id=config.CHANNEL_USERNAME, user_id=user_id)
        # Статусы, указывающие на то, что пользователь является участником канала
        if member.status in ['member', 'administrator', 'creator']:
            return True
        else:
            return False
    except Exception as e:
        logging.error(f"Ошибка при проверке подписки для {user_id} на {config.CHANNEL_USERNAME}: {e}. Возможно, бот не является администратором в канале.")
        return False

# --- КЛАВИАТУРЫ ---

def get_gallery_keyboard(current_index, sticker_mode=False):
    select_text = "✅ Выбрать"
    keyboard = [
        [
            InlineKeyboardButton("⬅️", callback_data=f"{config.CALLBACK_GALLERY_PREV_PREFIX}{current_index}"),
            InlineKeyboardButton(select_text, callback_data=f"{config.CALLBACK_GALLERY_SELECT_MEME_PREFIX}{current_index}"),
            InlineKeyboardButton("➡️", callback_data=f"{config.CALLBACK_GALLERY_NEXT_PREFIX}{current_index}"),
        ],
        [
            InlineKeyboardButton("🖼 Демотиватор", callback_data=f"{config.CALLBACK_GALLERY_SELECT_DEM_PREFIX}{current_index}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_user_photo_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("✅ Мем", callback_data=config.CALLBACK_USER_SELECT_MEME),
            InlineKeyboardButton("🖼 Демотиватор", callback_data=config.CALLBACK_USER_SELECT_DEM)
        ],
        [
            InlineKeyboardButton("✨ Эффекты", callback_data=config.CALLBACK_USER_SELECT_EFFECTS)
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_sticker_intermediate_keyboard():
    keyboard = [
        [InlineKeyboardButton("➕ Добавить ещё", callback_data=config.CALLBACK_STICKER_CONTINUE)],
        [InlineKeyboardButton("🏁 Завершить пак", callback_data=config.CALLBACK_STICKER_FINISH)]
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
    file_path = os.path.join(config.USER_UPLOAD_DIR, f"{uuid.uuid4()}.jpg")
    await photo_file.download_to_drive(file_path)
    
    context.user_data['user_template'] = file_path
    
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
        
    template_path = os.path.join(config.TEMPLATE_DIR, templates[current_index])
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
    Стартовое меню, обработка реплая на фото, и проверка подписки на канал.
    """
    message = update.message
    user_id = update.effective_user.id

    # Проверка подписки на канал
    if not await check_subscription(user_id, context):
        keyboard = InlineKeyboardMarkup([[ 
            InlineKeyboardButton("Подписаться на канал", url=f"https://t.me/{config.CHANNEL_USERNAME.lstrip('@')}")
        ]])
        await update.effective_message.reply_text(
            f"Для использования бота, пожалуйста, подпишитесь на наш канал: {config.CHANNEL_USERNAME}",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        return ConversationHandler.END # Завершаем диалог, пока пользователь не подпишется

    # СЦЕНАРИЙ 1: Пользователь ответил тегом бота на чье-то фото
    if message.reply_to_message and message.reply_to_message.photo:
        photo = message.reply_to_message.photo[-1]
        await process_photo_setup(update, context, photo)
        return ConversationHandler.END

    # СЦЕНАРИЙ 2: Обычный запуск (Галерея или Главное меню)
    context.user_data.clear() 
    
    keyboard = [
        [InlineKeyboardButton("🤣 Создать Мем", callback_data=config.CALLBACK_MODE_MEME)],
        [InlineKeyboardButton("📦 Создать Стикерпак", callback_data=config.CALLBACK_MODE_PACK)]
    ]
    
    await message.reply_text(
        "Привет! Я **DopaMeme Bot**.\nЧто будем создавать?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    return ConversationHandler.END

async def handle_user_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка прямой отправки фото (с подписью или в личке)"""
    user_id = update.effective_user.id
    # Проверка подписки на канал
    if not await check_subscription(user_id, context):
        keyboard = InlineKeyboardMarkup([[ 
            InlineKeyboardButton("Подписаться на канал", url=f"https://t.me/{config.CHANNEL_USERNAME.lstrip('@')}")
        ]])
        await update.effective_message.reply_text(
            f"Для использования бота, пожалуйста, подпишитесь на наш канал: {config.CHANNEL_USERNAME}",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        return ConversationHandler.END

    photo = update.message.photo[-1]
    await process_photo_setup(update, context, photo)
    return ConversationHandler.END

# --- HELPER FUNCTIONS FOR button_handler REFACTORING ---

async def _handle_menu_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
    query = update.callback_query
    templates = get_templates()
    # Set random starting index if templates exist
    if templates:
        context.user_data['gallery_index'] = random.randint(0, len(templates) - 1)
    else:
        context.user_data['gallery_index'] = 0

    if data == config.CALLBACK_MODE_MEME:
        context.user_data['sticker_mode'] = False
        await query.message.delete()
        await show_gallery(update, context, edit=False)
    elif data == config.CALLBACK_MODE_PACK:
        context.user_data['sticker_mode'] = True
        context.user_data['pack_created'] = False
        user_id = update.effective_user.id
        bot = await context.bot.get_me()
        unique_id = str(uuid.uuid4()).replace('-', '')[:8]
        context.user_data['pack_name'] = f"pack_{user_id}_{unique_id}_by_{bot.username}"
        context.user_data['pack_title'] = f"DopaMeme Pack {unique_id}"
        await query.message.delete()
        await show_gallery(update, context, edit=False)
    return ConversationHandler.END # End conversation after initial menu selection

async def _handle_sticker_flow(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
    query = update.callback_query
    if data == config.CALLBACK_STICKER_CONTINUE:
        templates = get_templates()
        if templates:
            context.user_data['gallery_index'] = random.randint(0, len(templates) - 1)
        await query.message.delete()
        await show_gallery(update, context, edit=False)
        return # Do not end conversation, user continues adding stickers
    elif data == config.CALLBACK_STICKER_FINISH:
        if not context.user_data.get('pack_created'):
            await query.message.edit_text("Пак пуст. Создайте хотя бы один мем!")
            return ConversationHandler.END
        pack_name = context.user_data.get('pack_name')
        link = f"https://t.me/addstickers/{pack_name}"
        await query.message.delete()
        await query.message.reply_text("✅ **Стикерпак готов!**\n\nНажмите кнопку ниже, чтобы добавить его к себе.", reply_markup=get_sticker_final_keyboard(link), parse_mode='Markdown')
        context.user_data.clear()
        return ConversationHandler.END
    return ConversationHandler.END

async def _handle_effect_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
    query = update.callback_query
    if data == config.CALLBACK_USER_SELECT_EFFECTS:
        keyboard = [
            [InlineKeyboardButton("🫠 Жидкий", callback_data=config.CALLBACK_EFFECT_LIQUID)],
            [InlineKeyboardButton("🍟 Прожарка", callback_data=config.CALLBACK_EFFECT_DEEPFRY)],
            [InlineKeyboardButton("🌀 Вихрь", callback_data=config.CALLBACK_EFFECT_WARP)],
            [InlineKeyboardButton("👁️‍🗨️ Криспи", callback_data=config.CALLBACK_EFFECT_CRISPY)],
            [InlineKeyboardButton("👀 Рыбий глаз", callback_data=config.CALLBACK_EFFECT_BULGE)],
            [InlineKeyboardButton("🕳️ Дырка", callback_data=config.CALLBACK_EFFECT_PINCH)],
            [InlineKeyboardButton("🔙 Назад", callback_data=config.CALLBACK_BACK_TO_USER_PHOTO)]
        ]
        await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
        return # Do not end conversation, user chooses effect
    elif data == config.CALLBACK_BACK_TO_USER_PHOTO:
        await query.message.edit_reply_markup(reply_markup=get_user_photo_keyboard())
        return # Do not end conversation, user goes back to photo menu

    if data.startswith("effect_"):
        if 'user_template' not in context.user_data:
             await query.message.edit_text("Ошибка: фото потеряно.")
             return ConversationHandler.END
        template_path = context.user_data['user_template']
        effect_map = {
            config.CALLBACK_EFFECT_LIQUID: (liquid_resize, {"scale": 0.5}, "🫠"),
            config.CALLBACK_EFFECT_DEEPFRY: (deep_fry_effect, {}, "🍟"),
            config.CALLBACK_EFFECT_WARP: (warp_effect, {}, "🌀"),
            config.CALLBACK_EFFECT_CRISPY: (crispy_effect, {}, "👁️‍🗨️"),
            config.CALLBACK_EFFECT_BULGE: (lens_bulge_effect, {}, "👀"),
            config.CALLBACK_EFFECT_PINCH: (lens_pinch_effect, {}, "🕳️"),
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
    return ConversationHandler.END # Default end, though specific effect handlers usually end it.

async def _handle_user_photo_action(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
    query = update.callback_query
    if 'user_template' not in context.user_data:
        await query.message.edit_text("Ошибка: фото потеряно.")
        return ConversationHandler.END
    context.user_data['template'] = context.user_data['user_template']
    if data == config.CALLBACK_USER_SELECT_MEME:
        await query.message.edit_text("📝 Введите текст для мема (Верх . Низ):")
        return config.WAITING_MEME_TEXT
    elif data == config.CALLBACK_USER_SELECT_DEM:
        await query.message.edit_text("🖼 Введите текст для демотиватора:")
        return config.WAITING_DEMOTIVATOR_TEXT
    return ConversationHandler.END

async def _handle_gallery_action(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
    query = update.callback_query
    try:
        parts = data.rsplit('_', 1)
        action_base = parts[0] + "_"
        index = int(parts[1])
    except:
        logging.error(f"Invalid gallery callback data: {data}")
        return ConversationHandler.END 
    
    templates = get_templates()
    if action_base == config.CALLBACK_GALLERY_PREV_PREFIX or action_base == config.CALLBACK_GALLERY_NEXT_PREFIX:
        new_index = (index - 1) % len(templates) if action_base == config.CALLBACK_GALLERY_PREV_PREFIX else (index + 1) % len(templates)
        context.user_data['gallery_index'] = new_index
        await show_gallery(update, context, edit=True)
        return # Do not end conversation, user navigates gallery
    elif action_base == config.CALLBACK_GALLERY_SELECT_MEME_PREFIX:
        context.user_data['template'] = os.path.join(config.TEMPLATE_DIR, templates[index])
        await query.message.edit_caption(caption="📝 Введите текст для мема (Верх . Низ):", reply_markup=None)
        return config.WAITING_MEME_TEXT
    elif action_base == config.CALLBACK_GALLERY_SELECT_DEM_PREFIX:
        context.user_data['template'] = os.path.join(config.TEMPLATE_DIR, templates[index])
        await query.message.edit_caption(caption="🖼 Введите текст для демотиватора:", reply_markup=None)
        return config.WAITING_DEMOTIVATOR_TEXT
    return ConversationHandler.END

# --- Refactored button_handler ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    user_id = update.effective_user.id
    # Subscription check remains here as it's a critical gate for all interactions
    if not await check_subscription(user_id, context):
        keyboard = InlineKeyboardMarkup([[ 
            InlineKeyboardButton("Подписаться на канал", url=f"https://t.me/{config.CHANNEL_USERNAME.lstrip('@')}")
        ]])
        await update.effective_message.reply_text(
            f"Для использования бота, пожалуйста, подпишитесь на наш канал: {config.CHANNEL_USERNAME}",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        return ConversationHandler.END

    # Route to helper functions based on callback data
    if data in [config.CALLBACK_MODE_MEME, config.CALLBACK_MODE_PACK]:
        return await _handle_menu_selection(update, context, data)
    elif data in [config.CALLBACK_STICKER_CONTINUE, config.CALLBACK_STICKER_FINISH]:
        return await _handle_sticker_flow(update, context, data)
    elif data == config.CALLBACK_USER_SELECT_EFFECTS or data == config.CALLBACK_BACK_TO_USER_PHOTO or data.startswith("effect_"):
        return await _handle_effect_selection(update, context, data)
    elif data == config.CALLBACK_USER_SELECT_MEME or data == config.CALLBACK_USER_SELECT_DEM:
        return await _handle_user_photo_action(update, context, data)
    elif data.startswith(config.CALLBACK_GALLERY_PREV_PREFIX) or \
         data.startswith(config.CALLBACK_GALLERY_NEXT_PREFIX) or \
         data.startswith(config.CALLBACK_GALLERY_SELECT_MEME_PREFIX) or \
         data.startswith(config.CALLBACK_GALLERY_SELECT_DEM_PREFIX):
        return await _handle_gallery_action(update, context, data)
    
    # Fallback for unhandled callback data - should ideally not be reached
    logging.warning(f"Unhandled callback data: {data}")
    return ConversationHandler.END
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
                    sticker_input = InputSticker(f, emoji_list=[config.STICKER_EMOJI])
                    if not context.user_data.get('pack_created'):
                        await context.bot.create_new_sticker_set(user_id=user_id, name=pack_name, title=pack_title, stickers=[sticker_input], sticker_format=config.STICKER_FORMAT)
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
    dirs_to_clean = [config.USER_UPLOAD_DIR, config.GENERATED_DIR]
    for d in dirs_to_clean:
        if os.path.exists(d):
            for f in os.listdir(d):
                file_path = os.path.join(d, f)
                try:
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                except Exception as e:
                    logging.error(f"Error cleaning {file_path}: {e}")

if __name__ == '__main__':
    if not config.BOT_TOKEN:
        print("Error: BOT_TOKEN not found in .env")
        exit(1)
    if not config.CHANNEL_USERNAME:
        print("Error: CHANNEL_USERNAME not found in .env or hardcoded. Set CHANNEL_USERNAME for subscription check.")
        exit(1)
    os.makedirs(config.GENERATED_DIR, exist_ok=True) # Ensure generated directory exists
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
    
    application = ApplicationBuilder().token(config.BOT_TOKEN).build()
    
    # ФИЛЬТРЫ ЗАПУСКА
    # start_filter ловит:
    # 1. Личку: текст без команд
    # 2. Группы: текст с упоминанием (@bot)
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
            CommandHandler(['start', 'dopa'], start),
            MessageHandler(start_filter, start),
            CallbackQueryHandler(button_handler),
            MessageHandler(photo_filter, handle_user_photo)
        ],
        states={
            config.WAITING_MEME_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, generate_meme_handler)],
            config.WAITING_DEMOTIVATOR_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, generate_demotivator_handler)],
        },
        fallbacks=[CommandHandler('cancel', cancel), CommandHandler('start', start)]
    )
    
    application.add_handler(conv_handler)
    print("Бот запущен!")
    application.run_polling()
