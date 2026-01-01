# Используем современный и легкий образ Python
FROM python:3.11-slim

# Переменные окружения для оптимизации Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем системные зависимости (если нужны для Pillow/Scipy)
# Обычно slim хватает, но для надежности добавим минимальный набор
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Сначала копируем только requirements.txt для кэширования слоев Docker
COPY requirements.txt .

# Устанавливаем Python-зависимости
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Копируем остальной код проекта
COPY . .

# Создаем необходимые директории явно (для прав доступа)
RUN mkdir -p assets/generated assets/user_uploads assets/templates assets/fonts

# Объявляем порт (хотя Render игнорирует EXPOSE, это хорошая документация)
EXPOSE 8080

# Запускаем бота
CMD ["python", "main.py"]