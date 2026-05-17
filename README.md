# Запуск проекта с нуля

## 1. Перейти в папку проекта

```bash
cd support_llm_agent
```

## 2. Создать виртуальное окружение

```bash
python -m venv venv
```

## 3. Активировать виртуальное окружение

Для Windows:

```bash
venv\Scripts\activate
```

Для macOS/Linux:

```bash
source venv/bin/activate
```

## 4. Установить зависимости

```bash
pip install -r requirements.txt
```

## 5. Создать файл .env

В папке `support_llm_agent` создайте файл `.env`.

Добавьте в него строку:

```env
OPENROUTER_API_KEY=ваш_ключ_openrouter
```

## 6. Запустить приложение

```bash
python app.py
```

При первом запуске база данных `support_agent.db` создастся автоматически.
