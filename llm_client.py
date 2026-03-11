import os
import httpx
from typing import List, Dict
from dotenv import load_dotenv

# 1. Загружаем .env только если он есть (для локалки)
load_dotenv()

# 2. Пытаемся взять ключ напрямую из системы
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')

# Если ключа нет ни в системе, ни в .env, выводим ошибку для отладки
async def invoke_llm(messages: List[Dict[str, str]], max_tokens: int = 4000) -> str:
    if not OPENAI_API_KEY:
        # Это поможет нам увидеть в логах, ЧТО именно видит программа
        raise ValueError(f"OPENAI_API_KEY is empty. Check GitHub Secrets!")
    
    # Новый URL для OpenAI
    url = "https://api.openai.com"
    
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "gpt-4o", # Или "gpt-4o-mini" (он дешевле и быстрее)
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.7
    }
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        return data['choices'][0]['message']['content']
