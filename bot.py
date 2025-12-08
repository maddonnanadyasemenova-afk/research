import os
import json
import logging
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    PreCheckoutQueryHandler,
    filters,
    ContextTypes,
    ConversationHandler
)
import database as db
from llm_client import invoke_llm

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
INITIAL_BONUS = int(os.getenv('INITIAL_BONUS_RUBLES', 500))

# Загрузка исследований
with open('researches.json', 'r', encoding='utf-8') as f:
    RESEARCHES = json.load(f)

# Состояния для ConversationHandler
WAITING_FOR_INPUT = 1

# Хранилище временных данных пользователей
user_data_storage = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    
    # Создаем или получаем пользователя с бонусом
    db_user = await db.get_or_create_user(
        telegram_id=user.id,
        username=user.username,
        first_name=user.first_name,
        initial_bonus=INITIAL_BONUS
    )
    
    is_new_user = db_user['balance_rubles'] == INITIAL_BONUS
    
    welcome_text = f"""
🎯 **Добро пожаловать в Marketing Research AI!**

Я помогу вам провести профессиональные маркетинговые исследования с помощью искусственного интеллекта.

💰 **Ваш баланс:** {db_user['balance_rubles']}₽
"""
    
    if is_new_user:
        welcome_text += f"\n🎁 **Бонус {INITIAL_BONUS}₽** зачислен на ваш счёт!\n"
    
    welcome_text += """
📊 **Доступные исследования:**
• Анализ целевой аудитории
• Маркетинговая стратегия
• Анализ каналов сбыта
• Проблемы аудитории
• Международный рынок
• Карта пути клиента
• Программа лояльности

Используйте команды:
/research - Начать новое исследование
/history - История исследований
/balance - Проверить баланс
/topup - Пополнить баланс
"""
    
    await update.message.reply_text(welcome_text, parse_mode='Markdown')


async def show_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать баланс пользователя"""
    user_id = update.effective_user.id
    balance = await db.get_user_balance(user_id)
    
    # Получаем последние транзакции
    transactions = await db.get_user_transactions(user_id, limit=5)
    
    text = f"💰 **Ваш баланс:** {balance}₽\n\n"
    
    if transactions:
        text += "**Последние транзакции:**\n"
        for trans in transactions:
            amount = trans['amount_rubles']
            sign = '+' if amount > 0 else ''
            date = datetime.fromisoformat(trans['created_at']).strftime('%d.%m.%Y %H:%M')
            text += f"• {sign}{amount}₽ - {trans['description']} ({date})\n"
    
    keyboard = [[InlineKeyboardButton("💳 Пополнить баланс", callback_data="topup")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)


async def show_researches(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать список доступных исследований"""
    keyboard = []
    
    for i, research in enumerate(RESEARCHES):
        button_text = f"{research['name']} - {research['price_rub']}₽"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"research_{i}")])
    
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = "📊 **Выберите тип исследования:**\n\nКаждое исследование включает глубокий анализ с помощью ИИ и детальные рекомендации."
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)


async def research_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора типа исследования"""
    query = update.callback_query
    await query.answer()
    
    research_index = int(query.data.split('_')[1])
    research = RESEARCHES[research_index]
    
    user_id = update.effective_user.id
    balance = await db.get_user_balance(user_id)
    
    # Проверяем баланс
    if balance < research['price_rub']:
        keyboard = [[InlineKeyboardButton("💳 Пополнить баланс", callback_data="topup")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"❌ Недостаточно средств!\n\n"
            f"Стоимость исследования: {research['price_rub']}₽\n"
            f"Ваш баланс: {balance}₽\n"
            f"Не хватает: {research['price_rub'] - balance}₽",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        return ConversationHandler.END
    
    # Сохраняем выбранное исследование
    user_data_storage[user_id] = {
        'research_index': research_index,
        'research': research
    }
    
    # Определяем, какие данные нужны от пользователя
    prompt_template = research['prompt']
    
    # Извлекаем плейсхолдеры из промта
    placeholders = []
    import re
    matches = re.findall(r'\[([^\]]+)\]', prompt_template)
    placeholders = list(set(matches))  # Уникальные плейсхолдеры
    
    if placeholders:
        user_data_storage[user_id]['placeholders'] = placeholders
        user_data_storage[user_id]['current_placeholder_index'] = 0
        user_data_storage[user_id]['user_inputs'] = {}
        
        # Запрашиваем первый параметр
        first_placeholder = placeholders[0]
        await query.edit_message_text(
            f"📝 **{research['name']}**\n\n"
            f"Стоимость: {research['price_rub']}₽\n\n"
            f"Пожалуйста, введите: **{first_placeholder}**",
            parse_mode='Markdown'
        )
        
        return WAITING_FOR_INPUT
    else:
        # Если нет плейсхолдеров, запускаем сразу
        await query.edit_message_text("⏳ Запускаю исследование...")
        await process_research(update, context, user_id, research, {})
        return ConversationHandler.END


async def handle_user_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода пользователя для исследования"""
    user_id = update.effective_user.id
    user_input = update.message.text
    
    if user_id not in user_data_storage:
        await update.message.reply_text("❌ Сессия истекла. Начните заново с /research")
        return ConversationHandler.END
    
    data = user_data_storage[user_id]
    placeholders = data['placeholders']
    current_index = data['current_placeholder_index']
    
    # Сохраняем ввод пользователя
    current_placeholder = placeholders[current_index]
    data['user_inputs'][current_placeholder] = user_input
    
    # Проверяем, есть ли еще плейсхолдеры
    if current_index + 1 < len(placeholders):
        # Запрашиваем следующий параметр
        data['current_placeholder_index'] += 1
        next_placeholder = placeholders[current_index + 1]
        
        await update.message.reply_text(
            f"✅ Принято!\n\nТеперь введите: **{next_placeholder}**",
            parse_mode='Markdown'
        )
        return WAITING_FOR_INPUT
    else:
        # Все данные собраны, запускаем исследование
        await update.message.reply_text("⏳ Все данные получены! Запускаю исследование...")
        
        research = data['research']
        user_inputs = data['user_inputs']
        
        # Очищаем временные данные
        del user_data_storage[user_id]
        
        await process_research(update, context, user_id, research, user_inputs)
        return ConversationHandler.END


async def process_research(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, research: dict, user_inputs: dict):
    """Обработка исследования с помощью ИИ"""
    try:
        # Заменяем плейсхолдеры в промте
        prompt = research['prompt']
        for placeholder, value in user_inputs.items():
            prompt = prompt.replace(f"[{placeholder}]", value)
        
        # Создаем запись в БД
        research_id = await db.create_research(
            telegram_id=user_id,
            research_type=research['name'],
            research_name=research['name'],
            user_input=json.dumps(user_inputs, ensure_ascii=False),
            price_rubles=research['price_rub']
        )
        
        # Вызываем Manus LLM API
        result = await invoke_llm(
            messages=[
                {"role": "system", "content": "You are a professional marketing research expert. Provide detailed, actionable insights in Russian language."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=4000
        )
        
        # Сохраняем результат
        await db.update_research_result(research_id, result, 'completed')
        
        # Отправляем результат пользователю
        # Разбиваем на части, если слишком длинный
        max_length = 4000
        if len(result) > max_length:
            parts = [result[i:i+max_length] for i in range(0, len(result), max_length)]
            for i, part in enumerate(parts):
                if i == 0:
                    header = f"✅ **Исследование завершено!**\n\n**{research['name']}**\n\n"
                    await context.bot.send_message(chat_id=user_id, text=header + part, parse_mode='Markdown')
                else:
                    await context.bot.send_message(chat_id=user_id, text=part, parse_mode='Markdown')
        else:
            full_message = f"✅ **Исследование завершено!**\n\n**{research['name']}**\n\n{result}"
            await context.bot.send_message(chat_id=user_id, text=full_message, parse_mode='Markdown')
        
        # Показываем обновленный баланс
        new_balance = await db.get_user_balance(user_id)
        await context.bot.send_message(
            chat_id=user_id,
            text=f"💰 Списано {research['price_rub']}₽. Ваш баланс: {new_balance}₽"
        )
        
    except Exception as e:
        logger.error(f"Error processing research: {e}")
        await db.update_research_result(research_id, str(e), 'failed')
        await context.bot.send_message(
            chat_id=user_id,
            text=f"❌ Произошла ошибка при обработке исследования. Средства возвращены на ваш счёт."
        )
        # Возвращаем деньги
        await db.update_balance(user_id, research['price_rub'], 'refund', 'Возврат за ошибку')


async def show_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать историю исследований"""
    user_id = update.effective_user.id
    researches = await db.get_user_researches(user_id, limit=10)
    
    if not researches:
        await update.message.reply_text(
            "📋 У вас пока нет исследований.\n\nИспользуйте /research чтобы начать!"
        )
        return
    
    text = "📋 **История ваших исследований:**\n\n"
    
    keyboard = []
    for r in researches:
        status_emoji = {
            'completed': '✅',
            'processing': '⏳',
            'failed': '❌'
        }.get(r['status'], '❓')
        
        date = datetime.fromisoformat(r['created_at']).strftime('%d.%m.%Y %H:%M')
        text += f"{status_emoji} **{r['research_name']}** - {r['price_rubles']}₽\n"
        text += f"   {date}\n\n"
        
        if r['status'] == 'completed':
            keyboard.append([InlineKeyboardButton(
                f"📄 {r['research_name'][:30]}...",
                callback_data=f"view_{r['id']}"
            )])
    
    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)


async def view_research(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Просмотр результатов исследования"""
    query = update.callback_query
    await query.answer()
    
    research_id = int(query.data.split('_')[1])
    research = await db.get_research_by_id(research_id)
    
    if not research or research['status'] != 'completed':
        await query.edit_message_text("❌ Исследование не найдено или ещё не завершено.")
        return
    
    result = research['result']
    max_length = 4000
    
    if len(result) > max_length:
        parts = [result[i:i+max_length] for i in range(0, len(result), max_length)]
        for i, part in enumerate(parts):
            if i == 0:
                header = f"📄 **{research['research_name']}**\n\n"
                await query.message.reply_text(header + part, parse_mode='Markdown')
            else:
                await query.message.reply_text(part, parse_mode='Markdown')
    else:
        full_message = f"📄 **{research['research_name']}**\n\n{result}"
        await query.message.reply_text(full_message, parse_mode='Markdown')


async def topup_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню пополнения баланса"""
    keyboard = [
        [InlineKeyboardButton("500₽ (50 ⭐)", callback_data="pay_500")],
        [InlineKeyboardButton("1000₽ (100 ⭐)", callback_data="pay_1000")],
        [InlineKeyboardButton("2000₽ (200 ⭐)", callback_data="pay_2000")],
        [InlineKeyboardButton("5000₽ (500 ⭐)", callback_data="pay_5000")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = "💳 **Пополнение баланса**\n\nВыберите сумму для пополнения:"
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)


async def process_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка платежа через Telegram Stars"""
    query = update.callback_query
    await query.answer()
    
    # Получаем сумму из callback_data
    amount_rub = int(query.data.split('_')[1])
    stars_amount = amount_rub // 10  # 1 Star = 10 рублей
    
    # Создаем инвойс для Telegram Stars
    title = f"Пополнение баланса на {amount_rub}₽"
    description = f"Пополнение баланса для проведения маркетинговых исследований"
    payload = f"topup_{amount_rub}_{update.effective_user.id}"
    
    prices = [LabeledPrice(label=f"{amount_rub}₽", amount=stars_amount)]
    
    await context.bot.send_invoice(
        chat_id=update.effective_chat.id,
        title=title,
        description=description,
        payload=payload,
        provider_token="",  # Пустой для Telegram Stars
        currency="XTR",  # Telegram Stars currency
        prices=prices
    )


async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверка перед оплатой"""
    query = update.pre_checkout_query
    await query.answer(ok=True)


async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка успешной оплаты"""
    payment = update.message.successful_payment
    
    # Извлекаем сумму из payload
    payload_parts = payment.invoice_payload.split('_')
    amount_rub = int(payload_parts[1])
    
    user_id = update.effective_user.id
    
    # Пополняем баланс
    await db.update_balance(
        telegram_id=user_id,
        amount=amount_rub,
        transaction_type='payment',
        description=f'Пополнение через Telegram Stars'
    )
    
    new_balance = await db.get_user_balance(user_id)
    
    await update.message.reply_text(
        f"✅ **Оплата прошла успешно!**\n\n"
        f"На ваш счёт зачислено: {amount_rub}₽\n"
        f"💰 Ваш баланс: {new_balance}₽",
        parse_mode='Markdown'
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена текущей операции"""
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text("❌ Операция отменена.")
    
    user_id = update.effective_user.id
    if user_id in user_data_storage:
        del user_data_storage[user_id]
    
    return ConversationHandler.END


async def main():
    """Запуск бота"""
    # Инициализация БД
    await db.init_db()
    
    # Создание приложения
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("balance", show_balance))
    application.add_handler(CommandHandler("history", show_history))
    application.add_handler(CommandHandler("topup", topup_menu))
    
    # ConversationHandler для исследований
    research_handler = ConversationHandler(
        entry_points=[CommandHandler("research", show_researches)],
        states={
            WAITING_FOR_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_input)]
        },
        fallbacks=[CallbackQueryHandler(cancel, pattern="^cancel$")]
    )
    application.add_handler(research_handler)
    
    # Обработчики callback кнопок
    application.add_handler(CallbackQueryHandler(research_selected, pattern="^research_\\d+$"))
    application.add_handler(CallbackQueryHandler(view_research, pattern="^view_\\d+$"))
    application.add_handler(CallbackQueryHandler(topup_menu, pattern="^topup$"))
    application.add_handler(CallbackQueryHandler(process_payment, pattern="^pay_\\d+$"))
    application.add_handler(CallbackQueryHandler(cancel, pattern="^cancel$"))
    
    # Обработчики платежей
    application.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
    
    # Запуск бота
    logger.info("Bot started!")
    await application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    import nest_asyncio; nest_asyncio.apply(); asyncio.run(main())
