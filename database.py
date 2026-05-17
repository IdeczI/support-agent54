import sqlite3
from datetime import datetime
from pathlib import Path


DB_PATH = Path(__file__).resolve().parent / "support_agent.db"


START_KNOWLEDGE = [
    (
        "Авторизация",
        "Проблемы со входом в аккаунт",
        "Если пользователь не может войти в аккаунт, необходимо предложить проверить "
        "правильность логина и пароля, восстановить пароль через форму восстановления, "
        "очистить кэш браузера или попробовать другой браузер. Если проблема сохраняется, "
        "нужно передать обращение оператору.",
    ),
    (
        "Оплата",
        "Не проходит оплата банковской картой",
        "Если оплата банковской картой не проходит, необходимо предложить проверить "
        "правильность данных карты, срок действия карты, наличие средств, ограничения "
        "и лимиты банка. Также можно предложить попробовать другой способ оплаты. "
        "Если деньги списались, но заказ не оформился, обращение нужно передать оператору.",
    ),
    (
        "Ошибка сайта",
        "Ошибка при работе с сайтом",
        "Если сайт работает некорректно, необходимо предложить обновить страницу, "
        "очистить кэш и cookies, попробовать другой браузер или устройство. Также нужно "
        "попросить пользователя приложить скриншот ошибки и описать, на каком шаге она возникает.",
    ),
    (
        "Доставка",
        "Вопросы по доставке",
        "Если пользователь спрашивает о доставке, необходимо попросить номер заказа "
        "и уточнить город доставки. Затем нужно сообщить, что статус доставки можно "
        "проверить по номеру заказа. Если срок доставки нарушен, обращение нужно передать оператору.",
    ),
    (
        "Возврат",
        "Возврат товара",
        "Если пользователь хочет вернуть товар, необходимо попросить номер заказа, "
        "дату покупки и причину возврата. Нужно сообщить, что возврат оформляется "
        "согласно правилам магазина. Если товар поврежден или пришел не тот товар, "
        "обращение нужно передать оператору.",
    ),
    (
        "Другое",
        "Аварийная ситуация с техникой",
        "Если пользователь сообщает о возгорании, дыме, искрах, запахе гари или другой угрозе безопасности, необходимо рекомендовать немедленно прекратить использование устройства, по возможности безопасно отключить питание, не трогать поврежденные провода и оборудование, отойти от устройства и обратиться в экстренные службы по номеру 112. После устранения угрозы обращение нужно передать специалисту для дальнейшей проверки.",
    ),
    (
        "Другое",
        "Общие обращения",
        "Если обращение не относится к стандартным категориям, необходимо поблагодарить "
        "пользователя за сообщение и передать обращение оператору для дополнительной проверки.",
    ),
]


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Создает таблицы и заполняет базу знаний стартовыми статьями."""
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_message TEXT,
                category TEXT,
                priority TEXT,
                need_operator INTEGER,
                generated_answer TEXT,
                status TEXT,
                created_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS knowledge_base (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT,
                title TEXT,
                content TEXT
            )
            """
        )

        count = conn.execute("SELECT COUNT(*) FROM knowledge_base").fetchone()[0]
        if count == 0:
            conn.executemany(
                """
                INSERT INTO knowledge_base (category, title, content)
                VALUES (?, ?, ?)
                """,
                START_KNOWLEDGE,
            )
        else:
            # Добавляет новые стартовые статьи в уже существующую базу без дублей.
            for category, title, content in START_KNOWLEDGE:
                exists = conn.execute(
                    "SELECT 1 FROM knowledge_base WHERE title = ? LIMIT 1",
                    (title,),
                ).fetchone()
                if not exists:
                    conn.execute(
                        """
                        INSERT INTO knowledge_base (category, title, content)
                        VALUES (?, ?, ?)
                        """,
                        (category, title, content),
                    )
        conn.commit()


def add_ticket(
    user_message: str,
    category: str,
    priority: str,
    need_operator: bool,
    generated_answer: str,
    status: str,
) -> int:
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO tickets (
                user_message, category, priority, need_operator,
                generated_answer, status, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_message,
                category,
                priority,
                int(need_operator),
                generated_answer,
                status,
                created_at,
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)


def update_ticket_status(ticket_id: int, status: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE tickets SET status = ? WHERE id = ?",
            (status, ticket_id),
        )
        conn.commit()


def get_recent_tickets(limit: int = 10) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT id, created_at, category, priority, need_operator, status, user_message
            FROM tickets
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()


def get_knowledge_by_category(category: str) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT id, category, title, content
            FROM knowledge_base
            WHERE category = ?
            ORDER BY id
            """,
            (category,),
        ).fetchall()


def get_all_knowledge() -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT id, category, title, content
            FROM knowledge_base
            ORDER BY id
            """
        ).fetchall()
