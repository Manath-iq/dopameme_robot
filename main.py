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

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def get_gallery_keyboard(current_index):
    """Клавиатура для галереи шаблонов"""
    keyboard = [
        [
            InlineKeyboardButton("⬅️", callback_data=f"prev_{current_index}"),
            InlineKeyboardButton("✅ Создать Мем", callback_data=f"select_meme_{current_index}"),
            InlineKeyboardButton("➡️", callback_data=f"next_{current_index}"),
        ],
        [
            InlineKeyboardButton("🖼 Демотиватор", callback_data=f"select_dem_{current_index}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_user_photo_keyboard():
    """Клавиатура для загруженного фото пользователя"""
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

def get_sticker_control_keyboard(pack_link):
    """Клавиатура управления процессом создания пака"""
    keyboard = [
        [InlineKeyboardButton("➕ Добавить ещё стикер", callback_data="sticker_continue")],
        [InlineKeyboardButton("🔗 Ссылка на пак", url=pack_link)],
        [InlineKeyboardButton("🏁 Закончить", callback_data="sticker_finish")]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- ЛОГИКА ОТОБРАЖЕНИЯ ---

async def show_gallery(update: Update, context: ContextTypes.DEFAULT_TYPE, edit=False):
    """Показывает галерею шаблонов (используется и для мемов, и для стикеров)"""
    templates = get_templates()
    if not templates:
        text = "Шаблоны не найдены! Добавьте .jpg файлы в assets/templates"
        if edit:
            await update.callback_query.message.edit_text(text)
        else:
            await update.message.reply_text(text)
        return ConversationHandler.END

    current_index = context.user_data.get('gallery_index', 0)
    template_path = os.path.join(TEMPLATE_DIR, templates[current_index])
    
    caption = "Выберите шаблон для мема:"
    if context.user_data.get('sticker_mode'):
        # Если пак уже создан, показываем ссылку
        link_info = ""
        if context.user_data.get('pack_created'):
            name = context.user_data.get('pack_name')
            link_info = f"\n\nПак уже доступен: t.me/addstickers/{name}"
            
        caption = f"Режим стикерпака.{link_info}\nВыберите шаблон или пришлите фото:"

    with open(template_path, 'rb') as f:
        media = InputMediaPhoto(media=f, caption=caption)
        keyboard = get_gallery_keyboard(current_index)
        
        if edit:
            await update.callback_query.edit_message_media(media=media, reply_markup=keyboard)
        else:
            if update.message:
                await update.message.reply_photo(photo=f, caption=caption, reply_markup=keyboard)
            elif update.callback_query:
                # Если переходим из меню, где не было фото
                await update.callback_query.message.reply_photo(photo=f, caption=caption, reply_markup=keyboard)

# --- ХЕНДЛЕРЫ КОМАНД ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Стартовое меню"""
    context.user_data.clear() # Сброс старых данных
    
    keyboard = [
        [InlineKeyboardButton("🤣 Создать Мем", callback_data="mode_meme")],
        [InlineKeyboardButton("📦 Создать Стикерпак", callback_data="mode_pack")]
    ]
    
    await update.message.reply_text(
        "Привет! Я бот @DopaMemerobot.\nЧто будем делать сегодня?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ConversationHandler.END # Ждем колбэка, состояние не нужно пока

async def handle_user_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка загрузки фото (универсальная)"""
    photo_file = await update.message.photo[-1].get_file()
    file_path = os.path.join(USER_UPLOAD_DIR, f"{uuid.uuid4()}.jpg")
    await photo_file.download_to_drive(file_path)
    
    context.user_data['user_template'] = file_path
    
    sticker_mode = context.user_data.get('sticker_mode', False)
    text = "Фото получено! Выберите режим:"
    if sticker_mode:
        text = "Фото для стикера получено! Выберите режим:"
        
    await update.message.reply_text(text, reply_markup=get_user_photo_keyboard())
    return ConversationHandler.END

# --- ОБРАБОТКА КНОПОК ---

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    # 1. ГЛАВНОЕ МЕНЮ
    if data == "mode_meme":
        context.user_data['sticker_mode'] = False
        await show_gallery(update, context, edit=False)
        await query.message.delete()
        return

    elif data == "mode_pack":
        context.user_data['sticker_mode'] = True
        context.user_data['pack_created'] = False
        
        # Генерируем имя пака заранее
        user_id = update.effective_user.id
        bot = await context.bot.get_me()
        unique_id = str(uuid.uuid4()).replace('-', '')[:8]
        
        # Имя пака: unique per pack session
        pack_name = f"pack_{user_id}_{unique_id}_by_{bot.username}"
        pack_title = f"@DopaMemerobot Pack {unique_id}"
        
        context.user_data['pack_name'] = pack_name
        context.user_data['pack_title'] = pack_title
        
        await query.message.edit_text(f"📦 Новый пак будет называться:\n{pack_title}\n\nСоздавайте мемы, они будут добавляться автоматически!")
        await show_gallery(update, context, edit=False)
        return

    # 2. НАВИГАЦИЯ СТИКЕРПАКА
    elif data == "sticker_continue":
        await show_gallery(update, context, edit=False)
        return
        
    elif data == "sticker_finish":
        # Если пак не был создан (0 стикеров), не даем ссылку
        if not context.user_data.get('pack_created'):
            await query.message.edit_text("Вы не добавили ни одного стикера! Пак не создан.")
            context.user_data.clear()
            return ConversationHandler.END

        # Просто сбрасываем режим и говорим спасибо
        pack_name = context.user_data.get('pack_name')
        link = f"https://t.me/addstickers/{pack_name}"
        await query.message.edit_text(f"✅ **Работа завершена!**\n\nВаш пак здесь: {link}", parse_mode='Markdown')
        context.user_data.clear()
        return ConversationHandler.END

    # 3. ЭФФЕКТЫ (ПОДМЕНЮ)
    elif data == "user_select_effects":
        keyboard = [
            [InlineKeyboardButton("🫠 Жидкий (Liquid)", callback_data="effect_liquid")],
            [InlineKeyboardButton("🍟 Прожарка (Deep Fried)", callback_data="effect_deepfry")],
            [InlineKeyboardButton("🌀 Вихрь (Swirl)", callback_data="effect_warp")],
            [InlineKeyboardButton("👁️‍🗨️ Криспи (Crispy)", callback_data="effect_crispy")],
            [InlineKeyboardButton("👀 Рыбий глаз (Bulge)", callback_data="effect_bulge")],
            [InlineKeyboardButton("🕳️ Дырка (Pinch)", callback_data="effect_pinch")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_user_photo")]
        ]
        await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
        return

    elif data == "back_to_user_photo":
        await query.message.edit_reply_markup(reply_markup=get_user_photo_keyboard())
        return

    # 4. ОБРАБОТКА ЭФФЕКТОВ
    if data.startswith("effect_"):
        if 'user_template' not in context.user_data:
             await query.message.edit_text("Ошибка: фото потеряно. Пришлите снова.")
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

    # 5. ВЫБОР РЕЖИМА
    if data == "user_select_meme":
        if 'user_template' not in context.user_data:
            await query.message.edit_text("Ошибка: фото потеряно. Пришлите снова.")
            return ConversationHandler.END
        context.user_data['template'] = context.user_data['user_template']
        await query.message.edit_text("📝 **Режим Мема**\nВведите текст (Верх . Низ):", parse_mode='Markdown')
        return WAITING_MEME_TEXT
        
    elif data == "user_select_dem":
        if 'user_template' not in context.user_data:
             await query.message.edit_text("Ошибка: фото потеряно. Пришлите снова.")
             return ConversationHandler.END
        context.user_data['template'] = context.user_data['user_template']
        await query.message.edit_text("🖼 **Режим Демотиватора**\nВведите подпись:", parse_mode='Markdown')
        return WAITING_DEMOTIVATOR_TEXT

    # Галерея
    templates = get_templates()
    try:
        parts = data.rsplit('_', 1)
        action_base = parts[0]
        index = int(parts[1])
    except:
        return
        
    if action_base == "prev" or action_base == "next":
        new_index = (index - 1) % len(templates) if action_base == "prev" else (index + 1) % len(templates)
        context.user_data['gallery_index'] = new_index
        await show_gallery(update, context, edit=True)
        return
        
    elif action_base == "select_meme":
        context.user_data['template'] = os.path.join(TEMPLATE_DIR, templates[index])
        await query.message.edit_caption(
            caption="📝 **Режим Мема**\nВведите текст (Верх . Низ):",
            parse_mode='Markdown',
            reply_markup=None
        )
        return WAITING_MEME_TEXT
        
    elif action_base == "select_dem":
        context.user_data['template'] = os.path.join(TEMPLATE_DIR, templates[index])
        await query.message.edit_caption(
            caption="🖼 **Режим Демотиватора**\nВведите подпись:",
            parse_mode='Markdown',
            reply_markup=None
        )
        return WAITING_DEMOTIVATOR_TEXT


# --- ХЕНДЛЕРЫ ГЕНЕРАЦИИ ---

async def generate_meme_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    template_path = context.user_data.get('template')
    
    if not template_path or not os.path.exists(template_path):
        await update.message.reply_text("Шаблон не найден. Начните заново.")
        return ConversationHandler.END
        
    parts = text.split('.', 1)
    top_text = parts[0].strip()
    bottom_text = parts[1].strip() if len(parts) > 1 else ""
    
    msg = await update.message.reply_text("🎨 Рисую мем...")
    
    try:
        output_path = generate_meme(template_path, top_text, bottom_text)
        await finalize_generation(update, context, output_path, msg)
        
        if "user_uploads" in template_path and os.path.exists(template_path):
            os.remove(template_path)
            
    except Exception as e:
        logging.error(f"Error: {e}")
        await msg.edit_text("❌ Ошибка при генерации.")
        
    return ConversationHandler.END

async def generate_demotivator_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    template_path = context.user_data.get('template')
    
    if not template_path or not os.path.exists(template_path):
        await update.message.reply_text("Шаблон не найден. Начните заново.")
        return ConversationHandler.END
        
    msg = await update.message.reply_text("🎨 Рисую демотиватор...")
    
    try:
        output_path = generate_demotivator(template_path, text)
        await finalize_generation(update, context, output_path, msg)
        
        if "user_uploads" in template_path and os.path.exists(template_path):
            os.remove(template_path)

    except Exception as e:
        logging.error(f"Error: {e}")
        await msg.edit_text("❌ Ошибка при генерации.")
        
    return ConversationHandler.END

# --- ФИНАЛИЗАЦИЯ (ИЗМЕНЕНА ДЛЯ ЭКОНОМИИ МЕСТА) ---

async def finalize_generation(update: Update, context: ContextTypes.DEFAULT_TYPE, image_path, loading_msg):
    """
    Если sticker_mode: сразу добавляем в пак и удаляем файл.
    Если обычный: отправляем фото и удаляем файл.
    """
    try:
        if context.user_data.get('sticker_mode'):
            # 1. Конвертация
            sticker_path = prepare_for_sticker(image_path)
            os.remove(image_path) # Удаляем промежуточный JPG
            
            user_id = update.effective_user.id
            pack_name = context.user_data['pack_name']
            pack_title = context.user_data['pack_title']
            pack_link = f"https://t.me/addstickers/{pack_name}"
            
            # 2. Мгновенная загрузка в Telegram
            try:
                with open(sticker_path, 'rb') as f:
                    # InputSticker требует эмодзи. Ставим дефолтный.
                    # format передается в create_new_sticker_set, а не сюда.
                    sticker_input = InputSticker(f, emoji_list=["😀"])
                    
                    if not context.user_data.get('pack_created'):
                        # Создаем новый
                        await context.bot.create_new_sticker_set(
                            user_id=user_id,
                            name=pack_name,
                            title=pack_title,
                            stickers=[sticker_input],
                            sticker_format="static"
                        )
                        context.user_data['pack_created'] = True
                        status_text = f"✅ Пак создан!\nСтикер добавлен."
                    else:
                        # Добавляем в существующий
                        await context.bot.add_sticker_to_set(
                            user_id=user_id,
                            name=pack_name,
                            sticker=sticker_input
                        )
                        status_text = f"✅ Стикер добавлен в пак."

                # 3. Отправляем превью пользователю (просто как документ, файл уже закрыт)
                # Чтобы отправить файл снова, нужно открыть его снова, но лучше отправить успешный статус
                # И отправить САМ файл пользователю, чтобы он видел, что получилось
                with open(sticker_path, 'rb') as f:
                    await loading_msg.delete()
                    await update.effective_message.reply_document(
                        document=f,
                        caption=f"{status_text}\n<{pack_title}>",
                        reply_markup=get_sticker_control_keyboard(pack_link)
                    )

            except Exception as e:
                logging.error(f"Telegram API Error: {e}")
                await loading_msg.edit_text(f"❌ Ошибка Telegram API:\n{e}")
                
            finally:
                # 4. ВАЖНО: Удаляем файл немедленно
                if os.path.exists(sticker_path):
                    os.remove(sticker_path)

        else:
            # Обычный режим
            with open(image_path, 'rb') as f:
                await update.effective_message.reply_photo(f)
            await loading_msg.delete()
            os.remove(image_path)

    except Exception as e:
        logging.error(f"Finalize Error: {e}")
        # Пытаемся почистить даже при ошибке
        if os.path.exists(image_path): os.remove(image_path)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменено. Введите /start.")
    return ConversationHandler.END

# --- ЗАПУСК ---

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
        print(f"Web server running on port {port}")
        server.serve_forever()

    threading.Thread(target=run_web_server, daemon=True).start()

    application = ApplicationBuilder().token(TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            CallbackQueryHandler(button_handler),
            MessageHandler(filters.PHOTO, handle_user_photo)
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