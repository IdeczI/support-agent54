import json
import re

from llm_agent import call_openrouter


CATEGORIES = {"Авторизация", "Оплата", "Ошибка сайта", "Доставка", "Возврат", "Другое"}
PRIORITIES = {"Низкий", "Средний", "Высокий"}


def classify_message(message: str) -> dict:
    emergency_result = classify_emergency(message)
    if emergency_result is not None:
        return emergency_result

    llm_result = classify_with_llm(message)
    if llm_result is not None:
        return llm_result
    return fallback_classify(message)


def classify_emergency(message: str) -> dict | None:
    text = message.lower()
    emergency_words = [
        "загорелся",
        "горит",
        "пожар",
        "дым",
        "искрит",
        "искры",
        "плавится",
        "запах гари",
        "короткое замыкание",
        "системный блок",
    ]
    if any(word in text for word in emergency_words) and any(
        word in text for word in ["горит", "загорелся", "пожар", "дым", "искрит", "искры", "гари"]
    ):
        return {
            "category": "Другое",
            "priority": "Высокий",
            "need_operator": True,
            "summary": "Пользователь сообщает об аварийной ситуации с техникой",
        }

    return None


def classify_with_llm(message: str) -> dict | None:
    prompt = f"""
Ты — система автоматической классификации обращений технической поддержки.

Проанализируй обращение пользователя и определи:
1. категорию обращения;
2. приоритет;
3. требуется ли оператор;
4. краткое описание проблемы.

Категории:
- Авторизация
- Оплата
- Ошибка сайта
- Доставка
- Возврат
- Другое

Приоритеты:
- Низкий
- Средний
- Высокий

Правила:
- Если пользователь сообщает о списании денег, невозможности оплатить заказ, серьезной ошибке или нарушении доставки — приоритет высокий.
- Если пользователь сообщает о пожаре, дыме, искрах, возгорании, запахе гари или другой угрозе безопасности — приоритет высокий и need_operator = true.
- Если вопрос стандартный и может быть решен инструкцией — приоритет средний.
- Если вопрос общий или информационный — приоритет низкий.
- Если информации недостаточно, нужна проверка заказа, списание денег или нестандартная проблема — need_operator = true.
- Верни только JSON без пояснений и без markdown.

Формат ответа:
{{
  "category": "Оплата",
  "priority": "Высокий",
  "need_operator": true,
  "summary": "Пользователь не может оплатить заказ банковской картой"
}}

Обращение пользователя:
"{message}"
"""
    content = call_openrouter(
        [
            {
                "role": "system",
                "content": "Ты возвращаешь только валидный JSON без markdown и пояснений.",
            },
            {"role": "user", "content": prompt},
        ]
    )
    if not content:
        return None

    try:
        data = json.loads(content.strip())
    except json.JSONDecodeError:
        # Иногда модели оборачивают JSON лишним текстом. Берем первый объект, если он есть.
        match = re.search(r"\{.*\}", content, flags=re.DOTALL)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None

    return normalize_classification(data)


def normalize_classification(data: dict) -> dict | None:
    category = data.get("category")
    priority = data.get("priority")
    need_operator = data.get("need_operator")
    summary = data.get("summary")

    if category not in CATEGORIES or priority not in PRIORITIES:
        return None
    if not isinstance(need_operator, bool):
        return None
    if not isinstance(summary, str) or not summary.strip():
        return None

    return {
        "category": category,
        "priority": priority,
        "need_operator": need_operator,
        "summary": summary.strip(),
    }


def fallback_classify(message: str) -> dict:
    text = message.lower()
    category = "Другое"

    category_rules = [
        ("Авторизация", ["пароль", "войти", "логин", "аккаунт", "авторизация"]),
        ("Оплата", ["оплата", "карта", "деньги", "платеж", "списали"]),
        ("Ошибка сайта", ["ошибка", "сайт", "не работает", "страница", "баг"]),
        ("Доставка", ["доставка", "курьер", "заказ", "посылка"]),
        ("Возврат", ["возврат", "вернуть", "обмен"]),
    ]

    for rule_category, keywords in category_rules:
        if any(keyword in text for keyword in keywords):
            category = rule_category
            break

    high_priority_words = [
        "срочно",
        "списали",
        "деньги",
        "не работает",
        "ошибка",
        "не пришел",
        "не пришёл",
        "сломано",
    ]
    operator_words = ["списали", "деньги", "срочно", "не пришел", "не пришёл", "сломано"]

    if any(word in text for word in high_priority_words):
        priority = "Высокий"
    elif category != "Другое":
        priority = "Средний"
    else:
        priority = "Низкий"

    need_operator = category == "Другое" or any(word in text for word in operator_words)

    return {
        "category": category,
        "priority": priority,
        "need_operator": need_operator,
        "summary": build_summary(category),
    }


def build_summary(category: str) -> str:
    summaries = {
        "Авторизация": "Пользователь сообщает о проблеме со входом в аккаунт",
        "Оплата": "Пользователь сообщает о проблеме с оплатой",
        "Ошибка сайта": "Пользователь сообщает об ошибке при работе с сайтом",
        "Доставка": "Пользователь задает вопрос по доставке или заказу",
        "Возврат": "Пользователь хочет оформить возврат или обмен товара",
        "Другое": "Обращение не относится к стандартным категориям",
    }
    return summaries.get(category, summaries["Другое"])
