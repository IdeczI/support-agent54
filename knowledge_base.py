import re

from database import get_all_knowledge, get_knowledge_by_category


def find_relevant_knowledge(message: str, category: str) -> str:
    articles = get_knowledge_by_category(category)
    if not articles:
        articles = get_all_knowledge()

    emergency_article = find_emergency_article(message, articles)
    if emergency_article is not None:
        return format_article(emergency_article)

    ranked_articles = rank_articles(message, articles)
    if ranked_articles:
        selected = ranked_articles[:1]
    else:
        selected = articles or get_knowledge_by_category("Другое")

    if not selected:
        return "Информация в базе знаний не найдена."

    return "\n\n".join(format_article(article) for article in selected[:1])


def find_emergency_article(message: str, articles: list):
    text = message.lower()
    emergency_words = [
        "загорелся",
        "горит",
        "пожар",
        "дым",
        "искрит",
        "искры",
        "запах гари",
        "короткое замыкание",
    ]
    if not any(word in text for word in emergency_words):
        return None

    for article in articles:
        article_text = f"{article['title']} {article['content']}".lower()
        if "аварийная ситуация" in article_text or "экстренные службы" in article_text:
            return article

    return None


def rank_articles(message: str, articles: list) -> list:
    words = extract_keywords(message)
    scored = []
    for article in articles:
        haystack = f"{article['title']} {article['content']}".lower()
        score = sum(1 for word in words if word in haystack)
        if score > 0:
            scored.append((score, article))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [article for _, article in scored]


def extract_keywords(text: str) -> set[str]:
    words = re.findall(r"[а-яёa-z0-9]+", text.lower())
    return {word for word in words if len(word) >= 4}


def format_article(article) -> str:
    content = article["content"]
    if len(content) > 700:
        content = content[:697].rstrip() + "..."

    return (
        f"Категория: {article['category']}\n"
        f"Статья: {article['title']}\n"
        f"Информация: {content}"
    )
