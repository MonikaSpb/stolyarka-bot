import logging
import os
from datetime import datetime
from typing import Dict, Any

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
    Contact,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Стадии диалога
BEEN_BEFORE, BRANCH, AGE, TIME, CHILD_INFO, PHONE = range(6)

# Тексты
WELCOME = (
    "Вас приветствует СТОЛЯРКОБОТ👋\n\n"
    "В Столяркино ваш ребенок научится мастерить из дерева, работать на станках и с инструментами, "
    "станет настоящим хозяином в доме ⚒️\n\n"
    "Я помогу вам записаться в нашу мастерскую и занять место в группе.\n"
    "Тем более расписание на новый учебный год уже готово 🤗\n\n"
    "Скажите, вы уже были у нас?"
)
STEP2 = "Понял вас 😇\n\nВыберите филиал, в который вам удобнее ходить:"
STEP3 = "Отлично 😊\n\nТеперь определимся с возрастной группой вашего ребенка"
STEP4 = "Выберите удобное время для посещения Столяркино 👇"
STEP5 = (
    "Осталось пара шагов — напишите ФИ ребенка и дату рождения\n\n"
    "Например: Иванов Иван, 14.02.2017"
)
STEP6 = (
    "И ваш контактный номер телефона ✍️\n\n"
    "Можно отправить текстом или нажмите кнопку «Отправить телефон»."
)
CANCELLED = "Диалог отменён. Чтобы начать заново — отправьте /start"

# Кнопки
YES_NO_KB = ReplyKeyboardMarkup([["Да", "Нет"]], resize_keyboard=True)
BRANCH_KB = ReplyKeyboardMarkup([["ул. Новосёлов, 105"]], resize_keyboard=True)
AGE_KB = ReplyKeyboardMarkup([["4–6 лет", "7–9 лет", "10+ лет"]], resize_keyboard=True)
TIME_KB = ReplyKeyboardMarkup(
    [["Четверг 17:30", "Суббота 10:00", "Воскресенье 10:00"]],
    resize_keyboard=True,
)
PHONE_KB = ReplyKeyboardMarkup(
    [[KeyboardButton("Отправить телефон", request_contact=True)]],
    resize_keyboard=True,
)

# Память процесса
user_data_store: Dict[int, Dict[str, Any]] = {}

# /id
async def my_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Ваш chat_id: {update.effective_chat.id}")

# Сценарий
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user_data_store[uid] = {"started_at": datetime.utcnow().isoformat()}
    await update.message.reply_text(WELCOME, reply_markup=YES_NO_KB)
    return BEEN_BEFORE

async def been_before(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user_data_store[uid]["been_before"] = (update.message.text or "").strip()
    await update.message.reply_text(STEP2, reply_markup=BRANCH_KB)
    return BRANCH

async def choose_branch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user_data_store[uid]["branch"] = (update.message.text or "").strip()
    await update.message.reply_text(STEP3, reply_markup=AGE_KB)
    return AGE

async def choose_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user_data_store[uid]["age_group"] = (update.message.text or "").strip()
    await update.message.reply_text(STEP4, reply_markup=TIME_KB)
    return TIME

async def choose_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user_data_store[uid]["time_slot"] = (update.message.text or "").strip()
    await update.message.reply_text(STEP5, reply_markup=ReplyKeyboardRemove())
    return CHILD_INFO

async def child_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user_data_store[uid]["child_info"] = (update.message.text or "").strip()
    await update.message.reply_text(STEP6, reply_markup=PHONE_KB)
    return PHONE

async def phone_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user_data_store[uid]["phone"] = (update.message.text or "").strip()
    await send_final(update, context)
    return ConversationHandler.END

async def phone_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    contact: Contact = update.message.contact
    user_data_store[uid]["phone"] = contact.phone_number if contact else ""
    await send_final(update, context)
    return ConversationHandler.END

async def send_final(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    data = user_data_store.get(uid, {})

    # Пользователю — только финал с выбранным временем
    final_msg = (
        f"Ура! Я вас записал 😍\n\n"
        f"Вы выбрали время: {data.get('time_slot','')}\n\n"
        "Наш администратор с вами свяжется для подтверждения записи после нашего отпуска.\n\n"
        "А пока обязательно подпишитесь на наш телеграм-канал:\n"
        "СТОЛЯРКИНО — https://t.me/stolyarkaizh\n"
        "Там будут все актуальные новости о жизни нашей мастерской 🤗"
    )
    await update.message.reply_text(final_msg, reply_markup=ReplyKeyboardRemove())

    # Админ-группа
    ADMIN_GROUP_ID = -4926335845
    summary = (
        "<b>📋 Новая запись в Столяркино</b>\n\n"
        f"👤 <b>Был у нас:</b> {data.get('been_before','')}\n"
        f"📍 <b>Филиал:</b> {data.get('branch','')}\n"
        f"🎯 <b>Возраст:</b> {data.get('age_group','')}\n"
        f"🕒 <b>Время:</b> {data.get('time_slot','')}\n"
        f"🧒 <b>Ребёнок:</b> {data.get('child_info','')}\n"
        f"📱 <b>Телефон:</b> {data.get('phone','')}\n"
        f"⏱ <b>Создано:</b> {data.get('started_at','')}"
    )
    await context.bot.send_message(chat_id=ADMIN_GROUP_ID, text=summary, parse_mode="HTML")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(CANCELLED, reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

def main():
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        raise RuntimeError("Переменная окружения BOT_TOKEN не задана в Render")
    app = Application.builder().token(bot_token).build()

    app.add_handler(CommandHandler("id", my_id))

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            BEEN_BEFORE: [MessageHandler(filters.TEXT & ~filters.COMMAND, been_before)],
            BRANCH:      [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_branch)],
            AGE:         [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_age)],
            TIME:        [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_time)],
            CHILD_INFO:  [MessageHandler(filters.TEXT & ~filters.COMMAND, child_info)],
            PHONE: [
                MessageHandler((filters.TEXT & ~filters.COMMAND) & ~filters.CONTACT, phone_text),
                MessageHandler(filters.CONTACT, phone_contact),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )
    app.add_handler(conv)

    app.run_polling()

if __name__ == "__main__":
    main()
