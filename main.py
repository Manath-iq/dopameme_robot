import os
import logging
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler

from utils.image_generator import generate_meme, generate_demotivator

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

# Список шаблонов
TEMPLATE_DIR = "assets/templates"
def get_templates():
    return sorted([f for f in os.listdir(TEMPLATE_DIR) if f.endswith(('.jpg', '.png'))])

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
        "1. Выберите картинку стрелками.\n"
        "2. Нажмите ✅ для мема или 'Демотиватор' для демотиватора."
    )
    
    first_template = os.path.join(TEMPLATE_DIR, templates[0])
    with open(first_template, 'rb') as f:
        await update.message.reply_photo(
            photo=f,
            caption=welcome_text,
            reply_markup=get_keyboard(0)
        )
    return ConversationHandler.END # Мы не начинаем разговор, пока не нажмут кнопку выбора

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer() # Обязательно отвечать, чтобы убрались часики
    
    data = query.data
    action, index = data.rsplit('_', 1)
    index = int(index)
    templates = get_templates()
    
    if action == "prev":
        new_index = (index - 1) % len(templates)
        # InputMediaPhoto требует opened file или url или file_id. 
        # Открываем каждый раз заново - безопасно.
        with open(os.path.join(TEMPLATE_DIR, templates[new_index]), 'rb') as f:
             new_media = InputMediaPhoto(media=f, caption="Выберите шаблон:")
             await query.edit_message_media(media=new_media, reply_markup=get_keyboard(new_index))
        return ConversationHandler.END # Не начинаем стейт
        
    elif action == "next":
        new_index = (index + 1) % len(templates)
        with open(os.path.join(TEMPLATE_DIR, templates[new_index]), 'rb') as f:
             new_media = InputMediaPhoto(media=f, caption="Выберите шаблон:")
             await query.edit_message_media(media=new_media, reply_markup=get_keyboard(new_index))
        return ConversationHandler.END
        
    elif action == "select_meme":
        context.user_data['template'] = os.path.join(TEMPLATE_DIR, templates[index])
        await query.message.reply_text(
            "📝 **Режим Мема**\n\n"
            "Напишите текст в формате:\n"
            "`Верхний текст . Нижний текст`\n\n"
            "(Если нужен только верхний или только нижний, используйте точку соответственно, например `. Снизу` или `Сверху .`)",
            parse_mode='Markdown'
        )
        return WAITING_MEME_TEXT
        
    elif action == "select_dem":
        context.user_data['template'] = os.path.join(TEMPLATE_DIR, templates[index])
        await query.message.reply_text(
            "🖼 **Режим Демотиватора**\n\n"
            "Напишите подпись для демотиватора:",
            parse_mode='Markdown'
        )
        return WAITING_DEMOTIVATOR_TEXT

async def generate_meme_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    template_path = context.user_data.get('template')
    
    if not template_path:
        await update.message.reply_text("Что-то пошло не так. Пожалуйста, начните заново с /start")
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
        os.remove(output_path) # Удаляем временный файл
    except Exception as e:
        logging.error(f"Error: {e}")
        await msg.edit_text("❌ Произошла ошибка при генерации.")
        
    return ConversationHandler.END

async def generate_demotivator_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    template_path = context.user_data.get('template')
    
    if not template_path:
        await update.message.reply_text("Что-то пошло не так. Пожалуйста, начните заново с /start")
        return ConversationHandler.END
        
    msg = await update.message.reply_text("🎨 Рисую демотиватор...")
    
    try:
        output_path = generate_demotivator(template_path, text)
        with open(output_path, 'rb') as f:
            await update.message.reply_photo(f)
        await msg.delete()
        os.remove(output_path)
    except Exception as e:
        logging.error(f"Error: {e}")
        await msg.edit_text("❌ Произошла ошибка при генерации.")
        
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменено. Введите /start.")
    return ConversationHandler.END

if __name__ == '__main__':
    if not TOKEN:
        print("Error: BOT_TOKEN not found in .env")
        exit(1)

    application = ApplicationBuilder().token(TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            CallbackQueryHandler(button_handler)
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
