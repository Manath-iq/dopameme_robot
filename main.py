import os
import logging
import uuid
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler

from utils.image_generator import generate_meme, generate_demotivator
from utils.effects import liquid_resize, deep_fry_effect, warp_effect

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

# Клавиатура навигации
def get_keyboard(current_index):
    keyboard = [
        [
            InlineKeyboardButton("⬅️", callback_data=f"prev_{current_index}"),
            InlineKeyboardButton("✅", callback_data=f"select_meme_{current_index}"),
            InlineKeyboardButton("➡️", callback_data=f"next_{current_index}"),
        ],
        [
            InlineKeyboardButton("Демотиватор", callback_data=f"select_dem_{current_index}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    templates = get_templates()
    if not templates:
        await update.message.reply_text("Шаблоны не найдены! Добавьте .jpg файлы в assets/templates")
        return ConversationHandler.END

    welcome_text = (
        "Привет! Я бот для создания мемов и демотиваторов.\n\n"
        "1. Выберите картинку стрелками ИЛИ **пришлите свою картинку**.\n"
        "2. Нажмите ✅ для мема или 'Демотиватор' для демотиватора."
    )
    
    first_template = os.path.join(TEMPLATE_DIR, templates[0])
    with open(first_template, 'rb') as f:
        await update.message.reply_photo(
            photo=f,
            caption=welcome_text,
            reply_markup=get_keyboard(0)
        )
    return ConversationHandler.END

async def handle_user_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo_file = await update.message.photo[-1].get_file()
    
    file_path = os.path.join(USER_UPLOAD_DIR, f"{uuid.uuid4()}.jpg")
    await photo_file.download_to_drive(file_path)
    
    context.user_data['user_template'] = file_path
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Сделать Мем", callback_data="user_select_meme"),
            InlineKeyboardButton("Демотиватор", callback_data="user_select_dem")
        ],
        [
            InlineKeyboardButton("✨ Эффекты", callback_data="user_select_effects")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "Фото получено! Выберите режим:", 
        reply_markup=reply_markup
    )
    return ConversationHandler.END

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    # Обработка пользовательских кнопок
    if data == "user_select_meme":
        if 'user_template' not in context.user_data:
            await query.message.edit_text("Ошибка: фото потеряно. Пришлите снова.")
            return ConversationHandler.END
        context.user_data['template'] = context.user_data['user_template']
        # Редактируем сообщение с меню, превращая его в инструкцию
        await query.message.edit_text("📝 **Режим Мема**\nВведите текст (Верх . Низ):", parse_mode='Markdown')
        return WAITING_MEME_TEXT
        
    elif data == "user_select_dem":
        if 'user_template' not in context.user_data:
             await query.message.edit_text("Ошибка: фото потеряно. Пришлите снова.")
             return ConversationHandler.END
        context.user_data['template'] = context.user_data['user_template']
        # Редактируем сообщение с меню
        await query.message.edit_text("🖼 **Режим Демотиватора**\nВведите подпись:", parse_mode='Markdown')
        return WAITING_DEMOTIVATOR_TEXT

    elif data == "user_select_effects":
        if 'user_template' not in context.user_data:
             await query.message.edit_text("Ошибка: фото потеряно. Пришлите снова.")
             return ConversationHandler.END
        
        keyboard = [
            [InlineKeyboardButton("🫠 Жидкий (Liquid)", callback_data="effect_liquid")],
            [InlineKeyboardButton("🍟 Прожарка (Deep Fried)", callback_data="effect_deepfry")],
            [InlineKeyboardButton("🌀 Вихрь (Swirl)", callback_data="effect_warp")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
        ]
        # Редактируем, чтобы показать подменю
        await query.message.edit_text("✨ Выберите эффект:", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    elif data == "back_to_main":
        keyboard = [
            [
                InlineKeyboardButton("✅ Сделать Мем", callback_data="user_select_meme"),
                InlineKeyboardButton("Демотиватор", callback_data="user_select_dem")
            ],
            [
                InlineKeyboardButton("✨ Эффекты", callback_data="user_select_effects")
            ]
        ]
        await query.message.edit_text("Фото получено! Выберите режим:", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    elif data == "effect_liquid":
        if 'user_template' not in context.user_data:
             await query.message.edit_text("Ошибка: фото потеряно. Пришлите снова.")
             return ConversationHandler.END
        
        template_path = context.user_data['user_template']
        # Меню превращается в статус "Обработка"
        await query.message.edit_text("🫠 Применяю эффект (это может занять время)...", reply_markup=None)
        msg = query.message # Используем это сообщение для удаления
        
        try:
            output_path = liquid_resize(template_path, scale=0.5)
            with open(output_path, 'rb') as f:
                await query.message.reply_photo(f)
            await msg.delete() # Удаляем сообщение "Обработка" (бывшее меню)
            os.remove(output_path)
            if os.path.exists(template_path): os.remove(template_path)
            return ConversationHandler.END
        except Exception as e:
            logging.error(f"Effect error: {e}")
            await msg.edit_text("❌ Ошибка при обработке изображения.")
            return ConversationHandler.END

    elif data == "effect_deepfry":
        if 'user_template' not in context.user_data:
             await query.message.edit_text("Ошибка: фото потеряно. Пришлите снова.")
             return ConversationHandler.END
        
        template_path = context.user_data['user_template']
        # Меню превращается в статус
        await query.message.edit_text("🍟 Жарю в масле...", reply_markup=None)
        msg = query.message 
        
        try:
            output_path = deep_fry_effect(template_path)
            with open(output_path, 'rb') as f:
                await query.message.reply_photo(f)
            await msg.delete()
            os.remove(output_path)
            if os.path.exists(template_path): os.remove(template_path)
            return ConversationHandler.END
        except Exception as e:
            logging.error(f"Effect error: {e}")
            await msg.edit_text("❌ Ошибка при обработке изображения.")
            return ConversationHandler.END

    elif data == "effect_warp":
        if 'user_template' not in context.user_data:
             await query.message.edit_text("Ошибка: фото потеряно. Пришлите снова.")
             return ConversationHandler.END
        
        template_path = context.user_data['user_template']
        # Меню превращается в статус
        await query.message.edit_text("🌀 Закручиваю...", reply_markup=None)
        msg = query.message
        
        try:
            output_path = warp_effect(template_path)
            with open(output_path, 'rb') as f:
                await query.message.reply_photo(f)
            await msg.delete()
            os.remove(output_path)
            if os.path.exists(template_path): os.remove(template_path)
            return ConversationHandler.END
        except Exception as e:
            logging.error(f"Effect error: {e}")
            await msg.edit_text("❌ Ошибка при обработке изображения.")
            return ConversationHandler.END

    # Обработка стандартной навигации
    try:
        action, index = data.rsplit('_', 1)
        index = int(index)
    except ValueError:
        return ConversationHandler.END
    
    templates = get_templates()
    
    if action == "prev":
        new_index = (index - 1) % len(templates)
        with open(os.path.join(TEMPLATE_DIR, templates[new_index]), 'rb') as f:
             new_media = InputMediaPhoto(media=f, caption="Выберите шаблон или пришлите свой:")
             await query.edit_message_media(media=new_media, reply_markup=get_keyboard(new_index))
        return ConversationHandler.END
        
    elif action == "next":
        new_index = (index + 1) % len(templates)
        with open(os.path.join(TEMPLATE_DIR, templates[new_index]), 'rb') as f:
             new_media = InputMediaPhoto(media=f, caption="Выберите шаблон или пришлите свой:")
             await query.edit_message_media(media=new_media, reply_markup=get_keyboard(new_index))
        return ConversationHandler.END
        
    elif action == "select_meme":
        context.user_data['template'] = os.path.join(TEMPLATE_DIR, templates[index])
        # Убираем кнопки у шаблона
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            "📝 **Режим Мема**\n\n"
            "Напишите текст в формате:\n"
            "`Верхний текст . Нижний текст`",
            parse_mode='Markdown'
        )
        return WAITING_MEME_TEXT
        
    elif action == "select_dem":
        context.user_data['template'] = os.path.join(TEMPLATE_DIR, templates[index])
        # Убираем кнопки у шаблона
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            "🖼 **Режим Демотиватора**\n\n"
            "Напишите подпись для демотиватора:",
            parse_mode='Markdown'
        )
        return WAITING_DEMOTIVATOR_TEXT

async def generate_meme_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    template_path = context.user_data.get('template')
    
    if not template_path or not os.path.exists(template_path):
        await update.message.reply_text("Ошибка: Шаблон не найден. Начните заново.")
        return ConversationHandler.END
        
    parts = text.split('.', 1)
    top_text = parts[0].strip()
    bottom_text = parts[1].strip() if len(parts) > 1 else ""
    
    msg = await update.message.reply_text("🎨 Рисую мем...")
    
    try:
        output_path = generate_meme(template_path, top_text, bottom_text)
        with open(output_path, 'rb') as f:
            await update.message.reply_photo(f)
        await msg.delete()
        os.remove(output_path) # Удаляем готовый мем
        
        # Если это было фото пользователя, удаляем исходник
        if "user_uploads" in template_path:
            try:
                os.remove(template_path)
            except Exception as e:
                logging.error(f"Failed to remove user upload: {e}")
                
    except Exception as e:
        logging.error(f"Error: {e}")
        await msg.edit_text("❌ Произошла ошибка при генерации.")
        
    return ConversationHandler.END

async def generate_demotivator_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    template_path = context.user_data.get('template')
    
    if not template_path or not os.path.exists(template_path):
        await update.message.reply_text("Ошибка: Шаблон не найден. Начните заново.")
        return ConversationHandler.END
        
    msg = await update.message.reply_text("🎨 Рисую демотиватор...")
    
    try:
        output_path = generate_demotivator(template_path, text)
        with open(output_path, 'rb') as f:
            await update.message.reply_photo(f)
        await msg.delete()
        os.remove(output_path) # Удаляем готовый демотиватор
        
        # Если это было фото пользователя, удаляем исходник
        if "user_uploads" in template_path:
            try:
                os.remove(template_path)
            except Exception as e:
                logging.error(f"Failed to remove user upload: {e}")
                
    except Exception as e:
        logging.error(f"Error: {e}")
        await msg.edit_text("❌ Произошла ошибка при генерации.")
        
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменено. Введите /start.")
    return ConversationHandler.END

def cleanup_temp_files():
    """Очистка временных файлов при запуске"""
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
        
    # Очистка мусора перед запуском
    cleanup_temp_files()

    # --- ЗАПУСК ФЕЙКОВОГО ВЕБ-СЕРВЕРА ДЛЯ RENDER ---
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

    # Запускаем сервер в фоновом потоке
    threading.Thread(target=run_web_server, daemon=True).start()
    # -----------------------------------------------

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