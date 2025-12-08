import os
import json
import logging
import asyncio
import traceback
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes
)
import database as db
from llm_client import invoke_llm

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
INITIAL_BONUS = int(os.getenv('INITIAL_BONUS_RUBLES', 500))

with open('researches.json', 'r', encoding='utf-8') as f:
    RESEARCHES = json.load(f)

# Хранилище состояний пользователей
user_states = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = await db.get_or_create_user(
        telegram_id=user.id,
        username=user.username,
        first_name=user.first_name,
        initial_bonus=INITIAL_BONUS
    )
    
    is_new = db_user['balance_rubles'] == INITIAL_BONUS
    
    text = f"""🎯 **Добро пожаловать в Marketing Research AI!**

💰 **Ваш баланс:** {db_user['balance_rubles']}₽
"""
    if is_new:
        text += f"\\n🎁 **Бонус {INITIAL_BONUS}₽** зачислен!\\n"
    
    text += """
/research - Начать исследование
/history - История
/balance - Баланс
"""
    
    await update.message.reply_text(text, parse_mode='Markdown')


async def show_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    balance = await db.get_user_balance(user_id)
    await update.message.reply_text(f"💰 **Ваш баланс:** {balance}₽", parse_mode='Markdown')


async def show_researches(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = []
    for i, r in enumerate(RESEARCHES):
        keyboard.append([InlineKeyboardButton(
            f"{r.get('emoji', '📊')} {r['name']} - {r['price_rub']}₽",
            callback_data=f"research_{i}"
        )])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "📊 **Выберите тип исследования:**",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def research_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    research_idx = int(query.data.split('_')[1])
    research = RESEARCHES[research_idx]
    user_id = update.effective_user.id
    
    # Проверка баланса
    balance = await db.get_user_balance(user_id)
    if balance < research['price_rub']:
        await query.edit_message_text(
            f"❌ Недостаточно средств!\\n\\nНужно: {research['price_rub']}₽\\nУ вас: {balance}₽",
            parse_mode='Markdown'
        )
        return
    
    # Извлекаем плейсхолдеры из промта
    import re
    placeholders = re.findall(r'\[([^\]]+)\]', research['prompt'])
    
    if placeholders:
        # Сохраняем состояние
        user_states[user_id] = {
            'research': research,
            'placeholders': placeholders,
            'inputs': {},
            'current_idx': 0
        }
        
        await query.edit_message_text(
            f"📝 **{research['name']}**\\n\\nСтоимость: {research['price_rub']}₽\\n\\nПожалуйста, введите: **{placeholders[0]}**",
            parse_mode='Markdown'
        )
    else:
        # Нет плейсхолдеров, запускаем сразу
        await query.edit_message_text("⏳ Запускаю исследование...")
        await process_research(update, context, user_id, research, {})


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in user_states:
        return
    
    state = user_states[user_id]
    placeholders = state['placeholders']
    current_idx = state['current_idx']
    
    # Сохраняем ввод
    state['inputs'][placeholders[current_idx]] = update.message.text
    
    # Проверяем, есть ли еще плейсхолдеры
    if current_idx + 1 < len(placeholders):
        state['current_idx'] += 1
        next_placeholder = placeholders[current_idx + 1]
        await update.message.reply_text(
            f"✅ Принято!\\n\\nТеперь введите: **{next_placeholder}**",
            parse_mode='Markdown'
        )
    else:
        # Все собрано
        await update.message.reply_text("⏳ Запускаю исследование...")
        research = state['research']
        inputs = state['inputs']
        del user_states[user_id]
        
        await process_research(update, context, user_id, research, inputs)


async def process_research(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, research: dict, user_inputs: dict):
    try:
        # Заменяем плейсхолдеры
        prompt = research['prompt']
        for placeholder, value in user_inputs.items():
            prompt = prompt.replace(f"[{placeholder}]", value)
        
        # Списываем деньги
        await db.update_balance(user_id, -research['price_rub'], 'research', research['name'])
        
        # Создаем запись
        research_id = await db.create_research(
            telegram_id=user_id,
            research_type=research['name'],
            research_name=research['name'],
            user_input=json.dumps(user_inputs, ensure_ascii=False),
            price_rubles=research['price_rub']
        )
        
        # Вызываем LLM
        logger.info(f"Calling LLM for research {research_id}")
        result = await invoke_llm(
            messages=[
                {"role": "system", "content": "You are a professional marketing research expert. Provide detailed, actionable insights in Russian language."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=4000
        )
        
        logger.info(f"LLM response received: {len(result)} chars")
        
        # Сохраняем результат
        await db.update_research_result(research_id, result, 'completed')
        
        # Отправляем результат
        max_length = 4000
        if len(result) > max_length:
            parts = [result[i:i+max_length] for i in range(0, len(result), max_length)]
            for i, part in enumerate(parts):
                if i == 0:
                    header = f"✅ **Исследование завершено!**\\n\\n**{research['name']}**\\n\\n"
                    await context.bot.send_message(chat_id=user_id, text=header + part, parse_mode='Markdown')
                else:
                    await context.bot.send_message(chat_id=user_id, text=part, parse_mode='Markdown')
        else:
            full_message = f"✅ **Исследование завершено!**\\n\\n**{research['name']}**\\n\\n{result}"
            await context.bot.send_message(chat_id=user_id, text=full_message, parse_mode='Markdown')
        
        new_balance = await db.get_user_balance(user_id)
        await context.bot.send_message(
            chat_id=user_id,
            text=f"💰 Списано {research['price_rub']}₽. Ваш баланс: {new_balance}₽"
        )
        
    except Exception as e:
        logger.error(f"Error processing research: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        await db.update_research_result(research_id, str(e), 'failed')
        error_msg = f"❌ Ошибка: {str(e)[:300]}\\n\\nСредства возвращены."
        await context.bot.send_message(chat_id=user_id, text=error_msg)
        await db.update_balance(user_id, research['price_rub'], 'refund', 'Возврат за ошибку')


async def show_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    researches = await db.get_user_researches(user_id, limit=10)
    
    if not researches:
        await update.message.reply_text("📋 У вас пока нет исследований.\\n\\nИспользуйте /research")
        return
    
    text = "📋 **История:**\\n\\n"
    for r in researches:
        status_emoji = {'completed': '✅', 'processing': '⏳', 'failed': '❌'}.get(r['status'], '❓')
        date = datetime.fromisoformat(r['created_at']).strftime('%d.%m.%Y %H:%M')
        text += f"{status_emoji} {r['research_name']} - {r['price_rubles']}₽\\n{date}\\n\\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')


async def main():
    await db.init_db()
    
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("balance", show_balance))
    application.add_handler(CommandHandler("research", show_researches))
    application.add_handler(CommandHandler("history", show_history))
    
    application.add_handler(CallbackQueryHandler(research_selected, pattern="^research_\\d+$"))
    
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    logger.info("Bot started!")
    await application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    import nest_asyncio
    nest_asyncio.apply()
    asyncio.run(main())
