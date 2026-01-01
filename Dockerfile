# Используем легкий образ Python
FROM python:3.10-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файл зависимостей и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь код бота
COPY . .

# Создаем необходимые папки (если их нет в git)
RUN mkdir -p assets/generated assets/user_uploads

# Запускаем бота
CMD ["python", "main.py"]
