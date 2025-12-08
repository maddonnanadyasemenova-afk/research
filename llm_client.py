import os
import httpx
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv( )

GROQ_API_KEY = os.getenv('GROQ_API_KEY', '')


async def invoke_llm(messages: List[Dict[str, str]], max_tokens: int = 4000) -> str:
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY not set")
    
    url = "https://api.groq.com/openai/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.7
    }
    
    async with httpx.AsyncClient(timeout=120.0 ) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        return data['choices'][0]['message']['content']
