import os

from dotenv import load_dotenv
from openai import OpenAI


MODEL_NAME = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free"
BASE_URL = "https://openrouter.ai/api/v1"


def get_openrouter_client() -> OpenAI | None:
    load_dotenv()
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key or not api_key.strip():
        return None

    return OpenAI(base_url=BASE_URL, api_key=api_key.strip())


def call_openrouter(messages: list[dict]) -> str | None:
    client = get_openrouter_client()
    if client is None:
        return None

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            extra_body={
                "reasoning": {
                    "enabled": True,
                }
            },
        )
        return response.choices[0].message.content
    except Exception as exc:
        print(f"Ошибка OpenRouter API: {exc}")
        return None


def generate_support_answer(
    user_message: str,
    category: str,
    priority: str,
    need_operator: bool,
    knowledge_context: str,
) -> str | None:
    system_prompt = (
        "Ты — LLM-агент чата технической поддержки. Отвечай на русском языке, "
        "кратко, вежливо и по делу. Используй только переданный контекст базы знаний. "
        "Не выдумывай номера заказов, сроки, факты и действия, которых нет в контексте. "
        "Если нужна проверка специалистом, прямо напиши об этом."
    )
    user_prompt = f"""
Сообщение пользователя:
{user_message}

Категория: {category}
Приоритет: {priority}
Нужен оператор: {"да" if need_operator else "нет"}

Короткий контекст базы знаний:
{knowledge_context}

Сформируй готовый ответ пользователю без markdown и без технических подробностей.
Если Нужен оператор = да, в конце добавь, что обращение будет передано оператору.
"""

    answer = call_openrouter(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
    )
    if answer:
        return answer.strip()

    return None
