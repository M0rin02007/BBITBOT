import logging
import re
import os
from telegram import Update, constants
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from openai import OpenAI
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Конфигурация
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_KEY = os.getenv("API_KEY")

# Проверка токенов
if not BOT_TOKEN:
    logging.error("BOT_TOKEN не установлен.")
    exit(1)

if not API_KEY:
    logging.error("API_KEY не установлен.")
    exit(1)

# Инициализация клиентов
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=API_KEY
)
conversation_history = {}

def escape_markdown_v2(text):
    """Экранирует специальные символы для MarkdownV2."""
    escape_chars = r"_*[]()~`>#+-=|{}.!"
    return re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", text)

async def start(update: Update, context: CallbackContext):
    """Обработчик команды /start."""
    user_id = update.message.from_user.id
    conversation_history.setdefault(user_id, [])
    
    welcome_text = (
        "Привет! Я умный телеграм бот с нейросетью. Задавай любой вопрос.\n"
        "Используйте /help для получения справки."
    )
    await update.message.reply_text(
        escape_markdown_v2(welcome_text),
        parse_mode=constants.ParseMode.MARKDOWN_V2
    )

async def help_command(update: Update, context: CallbackContext):
    """Обработчик команды /help."""
    help_text = (
        "*Список команд:*\n"
        "/start - Начать диалог\n"
        "/help - Помощь\n"
        "/reset - Сбросить историю\n"
        "\nПо вопросам: @mor1n0"
    )
    await update.message.reply_text(
        escape_markdown_v2(help_text),
        parse_mode=constants.ParseMode.MARKDOWN_V2
    )

async def reset_command(update: Update, context: CallbackContext):
    """Обработчик команды /reset."""
    user_id = update.message.from_user.id
    if user_id in conversation_history:
        del conversation_history[user_id]
        msg = "История сброшена."
    else:
        msg = "Истории нет."
    
    await update.message.reply_text(
        escape_markdown_v2(msg),
        parse_mode=constants.ParseMode.MARKDOWN_V2
    )

async def handle_message(update: Update, context: CallbackContext):
    """Обработчик текстовых сообщений."""
    user_id = update.message.from_user.id
    user_message = update.message.text
    logging.info(f"Сообщение от {user_id}: {user_message}")

    # Инициализация истории 
    conversation_history.setdefault(user_id, [])
    conversation_history[user_id].append({"role": "user", "content": user_message})

    try:
        # Отправка запроса к API
        completion = client.chat.completions.create(
            model="deepseek/deepseek-chat-v3-0324:free",
            messages=conversation_history[user_id],
            timeout=30
        )

        if completion.choices and completion.choices[0].message.content:
            content = completion.choices[0].message.content.strip()
            escaped_content = escape_markdown_v2(content)
            cleaned_content = re.sub(r'<.*?>', '', escaped_content).strip()

            if not cleaned_content:
                await update.message.reply_text("Пустой ответ от нейросети.")
                return

            # Разбивка длинных сообщений
            max_length = 4096
            chunks = [
                cleaned_content[i:i+max_length] 
                for i in range(0, len(cleaned_content), max_length)
            ]

            for i, chunk in enumerate(chunks):
                if i == 0:
                    response = f"*Ответ:*\n{chunk}"
                else:
                    response = chunk
                
                try:
                    await update.message.reply_text(
                        response,
                        parse_mode=constants.ParseMode.MARKDOWN_V2
                    )
                except Exception as e:
                    logging.warning(f"Ошибка форматирования: {e}")
                    await update.message.reply_text(chunk)

            # Сохранение ответа в истории
            conversation_history[user_id].append(
                {"role": "assistant", "content": content}
            )
        else:
            await update.message.reply_text("Нет ответа от API.")

    except Exception as e:
        logging.error(f"Ошибка API: {e}")
        await update.message.reply_text(f"Ошибка: {str(e)}")

async def error_handler(update: Update, context: CallbackContext):
    """Обработчик ошибок."""
    logging.error(f"Ошибка: {context.error}")
    if update and update.message:
        await update.message.reply_text("⚠️ Произошла ошибка. Попробуйте позже.")

def main():
    """Основная функция бота."""
    logging.basicConfig(
        format='%(asctime)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )

    app = Application.builder().token(BOT_TOKEN).build()

    # Регистрация обработчиков
    handlers = [
        CommandHandler("start", start),
        CommandHandler("help", help_command),
        CommandHandler("reset", reset_command),
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    ]
    
    for handler in handlers:
        app.add_handler(handler)
    
    app.add_error_handler(error_handler)
    app.run_polling()

if __name__ == '__main__':
    main() 