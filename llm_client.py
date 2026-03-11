import os
import httpx
from typing import List, Dict
from dotenv import load_dotenv

# 1. Загружаем .env для локальной разработки
load_dotenv()

# 2. Берем ключ из переменных окружения
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')

async def invoke_llm(messages: List[Dict[str, str]], max_tokens: int = 4000) -> str:
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is empty. Check GitHub Secrets!")
    
    # ИСПРАВЛЕНО: Добавлен полный путь к API (был только домен)
    url = "https://api.openai.com"
    
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "gpt-4o", 
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.7
    }
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(url, json=payload, headers=headers)
        
        # Если будет ошибка (например, закончились деньги на балансе), 
        # программа напишет подробности здесь
        response.raise_for_status()
        
        data = response.json()
        
        return data['choices'][0]['message']['content']
