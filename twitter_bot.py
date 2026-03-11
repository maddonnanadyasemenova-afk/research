import asyncio
import random
from typing import Literal

from llm_client import invoke_llm
from twitter_client import post_tweet


ContentType = Literal[
    "stat_insight",
    "practical_tip",
    "question",
    "case_story",
    "hot_take",
]


SYSTEM_PROMPT = (
    "You are a Twitter growth agent for 'Review' — an AI platform for collecting, "
    "analyzing and managing customer reviews for SaaS and small businesses.\n"
    "Target audience: US-based founders, product managers and growth teams.\n"
    "Persona: B2B SaaS expert, not a salesperson.\n"
    "Write as a thinking expert, always adding value (data, frameworks, practical advice).\n"
    "Language: English (US), no Russian.\n"
    "Tone: concise, friendly-professional, 2–4 sentences, max 280 characters.\n"
    "No direct promotion of Review, no links, no more than 2 hashtags.\n"
)


def _build_user_prompt(content_type: ContentType) -> str:
    """
    Формирует промпт для LLM под нужный тип оригинального твита (на английском).
    """
    if content_type == "stat_insight":
        return (
            "Write one original tweet in English for a US SaaS audience in the "
            "\"statistic + insight\" format about customer reviews, NPS, churn or "
            "customer feedback.\n"
            "Structure: surprising number → why it matters → practical takeaway.\n"
            "No links, no emojis, max 280 characters."
        )
    if content_type == "practical_tip":
        return (
            "Write one practical tip tweet in English for US SaaS teams about working "
            "with customer reviews (collecting more reviews, responding to negative "
            "reviews, using reviews in sales).\n"
            "Structure: problem → 2–3 steps to solve it → expected result.\n"
            "No links, no emojis, max 280 characters."
        )
    if content_type == "question":
        return (
            "Write one engaging question tweet in English for US SaaS / startup "
            "audience about customer feedback, reviews, NPS, churn or SaaS growth.\n"
            "Structure: one provocative question + 2–3 answer options in the tweet.\n"
            "No links, no emojis, max 280 characters."
        )
    if content_type == "case_story":
        return (
            "Write a short case-study style tweet in English: situation → what they "
            "did with customer reviews → result in numbers.\n"
            "No real company names, no links, max 280 characters."
        )
    if content_type == "hot_take":
        return (
            "Write a \"hot take\" tweet in English about metrics like NPS/CSAT, "
            "working with customer reviews, or the role of reviews in SaaS growth.\n"
            "Structure: controversial statement → short argument → open question.\n"
            "No links, no emojis, max 280 characters."
        )

    # Fallback — practical tip
    return (
        "Write one practical tip tweet in English for US SaaS teams about working "
        "with customer reviews. No links, no emojis, max 280 characters."
    )


async def generate_tweet(content_type: ContentType) -> str:
    """
    Генерирует текст твита через LLM по заданному типу контента.
    """
    user_prompt = _build_user_prompt(content_type)
    text = await invoke_llm(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=400,
    )
    # На всякий случай обрежем до лимита X (примерно 280 символов для текста)
    return text.strip()[:280]


async def main() -> None:
    # Пока что: при каждом запуске публикуем один твит случайного формата.
    content_type: ContentType = random.choice(
        ["stat_insight", "practical_tip", "question", "case_story", "hot_take"]
    )
    tweet_text = await generate_tweet(content_type)
    tweet_id = post_tweet(tweet_text)
    print("Опубликован твит:", tweet_text)
    print("ID твита:", tweet_id)


if __name__ == "__main__":
    asyncio.run(main())

