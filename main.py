import asyncio
import logging
import os
import sys
import uuid
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, html, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import (
    Message, 
    FSInputFile, 
    InlineQuery, 
    InlineQueryResultArticle, 
    InputTextMessageContent
)
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# Загрузка переменных окружения
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

# Настройка логирования
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# Инициализация бота и хранилища состояний
dp = Dispatcher(storage=MemoryStorage())

# Импорт генератора
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from utils.image_gen import generate_meme

# Определение состояний
class MemeForm(StatesGroup):
    waiting_for_text = State()

# Список доступных шаблонов (в реальном проекте лучше сканировать папку)
TEMPLATES = {
    "default": "templates/default.jpg",
    "black": "templates/black.jpg",
    "white": "templates/white.jpg"
}

@dp.message(CommandStart())
async def command_start_handler(message: Message, state: FSMContext) -> None:
    """
    Приветствие. Сбрасывает состояние.
    """
    await state.clear()
    await message.answer(f"Привет, {html.bold(message.from_user.full_name)}!\n"
                         f"Чтобы создать мем, используй inline-режим: набери @dopamemerobot в поле ввода и выбери шаблон.\n"
                         f"Или просто используй команду /cancel для отмены.")

@dp.inline_query()
async def inline_query_handler(inline_query: InlineQuery):
    """
    Обработчик inline-запросов. Показывает список шаблонов.
    """
    results = []
    
    # Формируем результаты для каждого шаблона
    for name, path in TEMPLATES.items():
        # Текст, который отправится при выборе
        message_content = InputTextMessageContent(
            message_text=f"/meme {name}"
        )
        
        item = InlineQueryResultArticle(
            id=str(uuid.uuid4()),
            title=f"Шаблон: {name.capitalize()}",
            description="Нажми, чтобы выбрать этот шаблон",
            input_message_content=message_content,
            # В идеале тут нужен thumb_url, но для локального бота пока без него
        )
        results.append(item)

    # cache_time=0 чтобы изменения подтягивались сразу при разработке
    await inline_query.answer(results, cache_time=1, is_personal=True)

@dp.message(Command("meme"))
async def meme_command_handler(message: Message, state: FSMContext):
    """
    Ловит команду /meme <template_name> (отправляется из inline).
    """
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Пожалуйста, выберите шаблон через inline-режим.")
        return

    template_name = args[1]
    if template_name not in TEMPLATES:
        await message.answer("Неизвестный шаблон.")
        return

    # Сохраняем выбранный шаблон в контекст состояния
    await state.update_data(template=template_name)
    await state.set_state(MemeForm.waiting_for_text)
    
    await message.answer(f"Выбран шаблон: {html.bold(template_name)}.\n"
                         f"Теперь отправь текст для мема.\n"
                         f"Формат: `Верх . Низ` (точка разделяет части).")

@dp.message(MemeForm.waiting_for_text)
async def process_meme_text(message: Message, state: FSMContext):
    """
    Генерирует мем, когда пользователь вводит текст в нужном состоянии.
    """
    data = await state.get_data()
    template_name = data.get("template")
    template_path = TEMPLATES.get(template_name)

    if not template_path:
        await message.answer("Ошибка: шаблон потерян. Начните заново.")
        await state.clear()
        return

    text = message.text
    if "." in text:
        parts = text.split(".", 1)
        top_text = parts[0].strip()
        bottom_text = parts[1].strip()
    else:
        top_text = text.strip()
        bottom_text = ""

    await message.answer("Генерирую мем... 🎨")

    output_filename = f"meme_{message.from_user.id}_{uuid.uuid4().hex[:8]}.jpg"
    result_path = generate_meme(template_path, top_text, bottom_text, output_path=output_filename)

    if result_path:
        photo = FSInputFile(result_path)
        await message.answer_photo(photo, caption="Твой мем готов!")
        try:
            os.remove(result_path)
        except OSError:
            pass
    else:
        await message.answer("Не удалось создать мем. Проверьте шаблон.")
    
    # Сбрасываем состояние после генерации (или можно оставить, чтобы генерировать дальше)
    await state.clear()

@dp.message(Command("cancel"))
async def cancel_handler(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        return
    await state.clear()
    await message.answer("Действие отменено.")

async def main() -> None:
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    # Удаляем вебхук и запускаем поллинг (на случай если был вебхук)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
