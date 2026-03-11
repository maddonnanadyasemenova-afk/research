import os
import httpx
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()

# Меняем название переменной для ясности (но можно оставить и старую)
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')

async def invoke_llm(messages: List[Dict[str, str]], max_tokens: int = 4000) -> str:
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY not set in .env file")
    
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
