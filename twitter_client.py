import os
from pathlib import Path
from typing import List, Optional, Tuple

import tweepy
from dotenv import load_dotenv


# Всегда читаем .env рядом с этим файлом (не зависит от текущей папки запуска)
load_dotenv(dotenv_path=Path(__file__).with_name(".env"))


# Поддерживаем оба варианта имён: API_* и CONSUMER_*
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY") or os.getenv("TWITTER_CONSUMER_KEY")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET") or os.getenv("TWITTER_CONSUMER_SECRET")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_TOKEN_SECRET = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")


def get_client() -> tweepy.Client:
    """
    Клиент X API v2 с user context.
    """
    missing = [
        name
        for name, value in [
            ("TWITTER_API_KEY / TWITTER_CONSUMER_KEY", TWITTER_API_KEY),
            ("TWITTER_API_SECRET / TWITTER_CONSUMER_SECRET", TWITTER_API_SECRET),
            ("TWITTER_ACCESS_TOKEN", TWITTER_ACCESS_TOKEN),
            ("TWITTER_ACCESS_TOKEN_SECRET", TWITTER_ACCESS_TOKEN_SECRET),
        ]
        if not value
    ]

    if missing:
        raise ValueError(
            "Missing Twitter credentials in .env: " + ", ".join(missing)
        )

    return tweepy.Client(
        consumer_key=TWITTER_API_KEY,
        consumer_secret=TWITTER_API_SECRET,
        access_token=TWITTER_ACCESS_TOKEN,
        access_token_secret=TWITTER_ACCESS_TOKEN_SECRET,
    )


def post_tweet(text: str) -> Optional[str]:
    """
    Публикует твит от имени подключённого аккаунта через X API v2.

    Возвращает ID опубликованного твита (строкой) или None при ошибке.
    """
    client = get_client()
    response = client.create_tweet(text=text)
    if response and hasattr(response, "data") and isinstance(response.data, dict):
        tweet_id = response.data.get("id")
        return str(tweet_id) if tweet_id is not None else None
    return None


def reply_to_tweet(tweet_id: str, text: str) -> Optional[str]:
    """
    Отвечает на указанный твит.
    """
    client = get_client()
    response = client.create_tweet(text=text, in_reply_to_tweet_id=tweet_id)
    if response and hasattr(response, "data") and isinstance(response.data, dict):
        reply_id = response.data.get("id")
        return str(reply_id) if reply_id is not None else None
    return None


def quote_tweet(tweet_id: str, text: str) -> Optional[str]:
    """
    Создаёт quote‑твит (комментарий к чужому твиту).
    """
    client = get_client()
    response = client.create_tweet(text=text, quote_tweet_id=tweet_id)
    if response and hasattr(response, "data") and isinstance(response.data, dict):
        new_id = response.data.get("id")
        return str(new_id) if new_id is not None else None
    return None


def search_recent_tweets(
    query: str,
    max_results: int = 20,
) -> Tuple[List[tweepy.Tweet], dict]:
    """
    Ищет свежие твиты по запросу, возвращает список твитов и словарь авторов.

    Словарь authors_by_id: {user_id: tweepy.User}
    """
    # Для поиска достаточно app-only аутентификации (Bearer Token)
    if not TWITTER_BEARER_TOKEN:
        raise ValueError("Missing TWITTER_BEARER_TOKEN in .env for search_recent_tweets")

    client = tweepy.Client(
        bearer_token=TWITTER_BEARER_TOKEN,
    )

    response = client.search_recent_tweets(
        query=query,
        max_results=max_results,
        tweet_fields=["created_at", "author_id", "public_metrics", "reply_settings"],
        user_fields=["username", "public_metrics"],
        expansions=["author_id"],
    )

    if not response or not response.data:
        return [], {}

    tweets: List[tweepy.Tweet] = list(response.data)
    users = {u.id: u for u in (response.includes.get("users", []) or [])}
    return tweets, users

