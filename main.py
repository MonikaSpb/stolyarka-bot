import logging
import os
from datetime import datetime
from typing import Dict, Any, List

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

# ---- стадии диалога ----
PARENT_NAME, BEEN_BEFORE, BRANCH, AGE, TIME, CHILD_INFO, PHONE = range(7)

# ---- тексты ----
WELCOME = (
    "Вас приветствует СТОЛЯРКОБОТ👋\n\n"
    "В Столяркино ваш ребенок научится мастерить из дерева, работать на станках и с инструментами, "
    "станет настоящим хозяином в доме ⚒️\n\n"
    "Я помогу вам записаться в нашу мастерскую и занять место в группе.\n"
    "Тем более расписание на новый учебный год уже готово 🤗\n\n"
    "Скажите, вы уже были у нас?"
)
ASK_NAME = "Как вас зовут?"
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

# ---- кнопки ----
BACK_BTN = "◀️ Назад"

def with_back(kb_rows: List[List[str]]) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(kb_rows + [[BACK_BTN]], resize_keyboard=True)

YES_NO_KB = with_back([["Да", "Нет"]])
BRANCH_KB = with_back([["ул. Новосёлов, 105"]])
AGE_KB = with_back([["4–6 лет", "7–9 лет", "10+ лет", "7–14 лет"]])

# ---- расписания по возрастам ----
SCHEDULE_BY_AGE = {
    "4–6 лет": [
        "Среда 17:45", "Суббота 10:00", "Воскресенье 10:00"
    ],
    "7–9 лет": [
        "Четверг 16:00", "Суббота 11:45", "Воскресенье 11:45"
    ],
    "10+ лет": [
        "Четверг 17:45", "Пятница 17:45", "Суббота 17:30", "Воскресенье 17:30"
    ],
    "7–14 лет": [
        "Среда 10:00", "Среда 16:00", "Четверг 10:00",
        "Пятница 10:00", "Пятница 16:00",
        "Суббота 13:45", "Суббота 15:30",
        "Воскресенье 13:45", "Воскресенье 15:30",
    ],
}

def chunk(lst: List[str], n: int) -> List[List[str]]:
    return [lst[i:i+n] for i in range(0, len(lst), n)]

def time_keyboard_for_age(age_group: str) -> ReplyKeyboardMarkup:
    slots = SCHEDULE_BY_AGE.get(age_group, [])
    rows = chunk(slots, 2 if len(slots) > 4 else 3)
    return with_back(rows)

# ---- временное хранилище ----
user_data_store: Dict[int, Dict[str, Any]] = {}

# /id
async def my_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Ваш chat_id: {update.effective_chat.id}")

# ---- сценарий ----
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user_data_store[uid] = {"started_at": datetime.utcnow().isoformat()}
    # 1) приветствие
    await update.message.reply_text(WELCOME, reply_markup=ReplyKeyboardRemove())
    # 2) сразу после — спросить имя (с кнопкой «Назад», которая просто повторит вопрос)
    await update.message.reply_text(ASK_NAME, reply_markup=ReplyKeyboardMarkup([[BACK_BTN]], resize_keyboard=True))
    return PARENT_NAME

async def parent_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Обработка «Назад»: просто повторить вопрос имени
    if (update.message.text or "").strip() == BACK_BTN:
        await update.message.reply_text(ASK_NAME, reply_markup=ReplyKeyboardMarkup([[BACK_BTN]], resize_keyboard=True))
        return PARENT_NAME

    uid = update.effective_user.id
    user_data_store[uid]["parent_name"] = (update.message.text or "").strip()
    await update.message.reply_text("Скажите, вы уже были у нас?", reply_markup=YES_NO_KB)
    return BEEN_BEFORE

async def been_before(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    # Назад → снова спросим имя
    if text == BACK_BTN:
        await update.message.reply_text(ASK_NAME, reply_markup=ReplyKeyboardMarkup([[BACK_BTN]], resize_keyboard=True))
        return PARENT_NAME

    uid = update.effective_user.id
    user_data_store[uid]["been_before"] = text
    await update.message.reply_text(STEP2, reply_markup=BRANCH_KB)
    return BRANCH

async def choose_branch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if text == BACK_BTN:
        await update.message.reply_text("Скажите, вы уже были у нас?", reply_markup=YES_NO_KB)
        return BEEN_BEFORE

    uid = update.effective_user.id
    user_data_store[uid]["branch"] = text
    await update.message.reply_text(STEP3, reply_markup=AGE_KB)
    return AGE

async def choose_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if text == BACK_BTN:
        await update.message.reply_text(STEP2, reply_markup=BRANCH_KB)
        return BRANCH

    uid = update.effective_user.id
    user_data_store[uid]["age_group"] = text
    await update.message.reply_text(STEP4, reply_markup=time_keyboard_for_age(text))
    return TIME

async def choose_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    uid = update.effective_user.id

    if text == BACK_BTN:
        # вернуться к выбору возраста
        await update.message.reply_text(STEP3, reply_markup=AGE_KB)
        return AGE

    user_data_store[uid]["time_slot"] = text
    await update.message.reply_text(STEP5, reply_markup=ReplyKeyboardMarkup([[BACK_BTN]], resize_keyboard=True))
    return CHILD_INFO

async def child_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    uid = update.effective_user.id

    if text == BACK_BTN:
        age = user_data_store[uid].get("age_group", "")
        await update.message.reply_text(STEP4, reply_markup=time_keyboard_for_age(age))
        return TIME

    user_data_store[uid]["child_info"] = text
    phone_kb = ReplyKeyboardMarkup(
        [[KeyboardButton("Отправить телефон", request_contact=True)], [BACK_BTN]],
        resize_keyboard=True,
    )
    await update.message.reply_text(STEP6, reply_markup=phone_kb)
    return PHONE

async def phone_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    uid = update.effective_user.id

    if text == BACK_BTN:
        await update.message.reply_text(STEP5, reply_markup=ReplyKeyboardMarkup([[BACK_BTN]], resize_keyboard=True))
        return CHILD_INFO

    user_data_store[uid]["phone"] = text
    await send_final(update, context)
    return ConversationHandler.END

async def phone_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    contact: Contact = update.message.contact
    # контакт пришёл → завершаем
    user_data_store[uid]["phone"] = contact.phone_number if contact else ""
    await send_final(update, context)
    return ConversationHandler.END

async def send_final(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    data = user_data_store.get(uid, {})

    # пользователю — только финал с выбранным временем
    final_msg = (
        f"Ура! Я вас записал 😍\n\n"
        f"Вы выбрали время: {data.get('time_slot','')}\n\n"
        "Наш администратор с вами свяжется для подтверждения записи после нашего отпуска.\n\n"
        "А пока обязательно подпишитесь на наш телеграм-канал:\n"
        "СТОЛЯРКИНО — https://t.me/stolyarkaizh\n"
        "Там будут все актуальные новости о жизни нашей мастерской 🤗"
    )
    await update.message.reply_text(final_msg, reply_markup=ReplyKeyboardRemove())

    # админ-группа — без строки «Создано»
    ADMIN_GROUP_ID = -4926335845
    summary = (
        "<b>📋 Новая запись в Столяркино</b>\n\n"
        f"👨‍👩‍👧 <b>Родитель:</b> {data.get('parent_name','')}\n"
        f"👤 <b>Был у нас:</b> {data.get('been_before','')}\n"
        f"📍 <b>Филиал:</b> {data.get('branch','')}\n"
        f"🎯 <b>Возраст:</b> {data.get('age_group','')}\n"
        f"🕒 <b>Время:</b> {data.get('time_slot','')}\n"
        f"🧒 <b>Ребёнок:</b> {data.get('child_info','')}\n"
        f"📱 <b>Телефон:</b> {data.get('phone','')}\n"
    )
    await context.bot.send_message(chat_id=ADMIN_GROUP_ID, text=summary, parse_mode="HTML")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(CANCELLED, reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# ---- сборка приложения ----
def build_app() -> Application:
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        raise RuntimeError("BOT_TOKEN не задан в переменных окружения Render")
    app = Application.builder().token(bot_token).build()

    app.add_handler(CommandHandler("id", my_id))
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            PARENT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, parent_name)],
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
    return app

def main():
    app = build_app()
    public_url = os.environ.get("PUBLIC_URL")  # например, https://stolyarka-bot.onrender.com
    if not public_url:
        raise RuntimeError("PUBLIC_URL не задан. Укажите домен сервиса Render в переменной PUBLIC_URL")

    path_token = os.environ.get("WEBHOOK_PATH", "tg-webhook")
    port = int(os.environ.get("PORT", 10000))
    webhook_url = f"{public_url.rstrip('/')}/{path_token}"

    app.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path=path_token,
        webhook_url=webhook_url,
        secret_token=None
    )

if __name__ == "__main__":
    main()
