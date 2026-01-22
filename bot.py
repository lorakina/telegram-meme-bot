import os
import json
import random
from datetime import datetime, time

from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ChatType
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# =========================
# 1) НАЛАШТУВАННЯ
# =========================

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

# ID групи/каналу, куди бот буде постити меми кожні 2 години
TARGET_CHAT_ID = int(os.getenv("TARGET_CHAT_ID", "0").strip() or "0")

# Якщо хочеш, щоб бот інколи кидав картинку-стікер/скрін при тригері "ютуб мюзік",
# встав сюди file_id (опційно)
YTM_TRIGGER_IMAGE_FILE_ID = os.getenv("YTM_TRIGGER_IMAGE_FILE_ID", "").strip()

# Тиха година: 22:00–08:00 (за локальним часом Windows)
QUIET_START = time(22, 0)
QUIET_END = time(8, 0)

# Раз на 2 години автопост (у хвилинах)
AUTOPOST_EVERY_MINUTES = 120

# Файл для збереження мемів/історії
DATA_FILE = "memes_data.json"

# ТРИГЕР ЗАВЖДИ (100% реакція)
YTM_REPLY_PROBABILITY = 1.0

# =========================
# 2) ДАНІ (збереження мемів)
# =========================

def load_data() -> dict:
    if not os.path.exists(DATA_FILE):
        return {"memes": [], "cycle_sent": []}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"memes": [], "cycle_sent": []}

def save_data(data: dict) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def add_meme(data: dict, meme: dict) -> None:
    data["memes"].append(meme)

def choose_meme_to_send(data: dict) -> dict | None:
    memes = data.get("memes", [])
    if not memes:
        return None

    sent = set(data.get("cycle_sent", []))
    available = [m for m in memes if m.get("file_id") not in sent]

    # Якщо в цьому циклі всі меми вже були — починаємо новий цикл
    if not available:
        data["cycle_sent"] = []
        save_data(data)
        available = memes[:]

    return random.choice(available) if available else None

def mark_sent(data: dict, file_id: str) -> None:
    data.setdefault("cycle_sent", []).append(file_id)

# =========================
# 3) ЧАС / ТИХА ГОДИНА
# =========================

def is_quiet_time(now: datetime | None = None) -> bool:
    now = now or datetime.now()
    t = now.time()
    return (QUIET_START <= t) or (t < QUIET_END)

# =========================
# 4) ВІДПРАВКА МЕМУ В ЧАТ
# =========================

async def send_meme(context: ContextTypes.DEFAULT_TYPE, chat_id: int, meme: dict) -> None:
    kind = meme.get("kind")
    file_id = meme.get("file_id")
    if not kind or not file_id:
        return

    caption = ""

    if kind == "photo":
        await context.bot.send_photo(chat_id=chat_id, photo=file_id, caption=caption)
    elif kind == "video":
        await context.bot.send_video(chat_id=chat_id, video=file_id, caption=caption)
    elif kind == "animation":
        await context.bot.send_animation(chat_id=chat_id, animation=file_id, caption=caption)
    else:
        await context.bot.send_message(chat_id=chat_id, text="Я знайшла щось дивне замість мема. Я не винна.")

# =========================
# 5) КОМАНДИ
# =========================

LET_TEXT = (
    "Йо 🌈\n"
    "Я офіційно призначена відповідальною за мемну економіку цього чату.\n\n"
    "Працюю просто: ти кидаєш мені в приват мем (🖼 картинки, 🎞 гіфки або 📹 відео), "
    "я його ховаю в сейф — і потім раз на 2 години дістаю звідти щось випадкове, "
    "щоб у вас знову з’явився сенс жити 😌\n\n"
    "Важливі моменти, прошу уваги 👇\n"
    "🌙 З 22:00 до 08:00 я в тихому режимі — навіть меми мають спати, а YouTube Music тим паче.\n"
    "🔁 Повтори я не люблю: поки не закінчаться всі меми, один і той самий вдруге не вилізе.\n"
    "🚫 Текстом мене не годуйте — я мем-бот, не психолог (хоча якщо щось іде в пизду і ви комплексуєте… ну, ви зрозуміли).\n\n"
    "Коротше: кидай меми, неси вайб, неси крінж.\n"
    "Я тут, щоб ця річка текла стабільно 🌊✨"
)

async def let_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(LET_TEXT)

async def meme_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_quiet_time():
        await update.message.reply_text("Тиха година 😴 22:00–08:00. Я не постю, бо мене потім теж зненавидять.")
        return

    if TARGET_CHAT_ID == 0:
        await update.message.reply_text("TARGET_CHAT_ID не заданий у .env (я не знаю, куди кидати меми).")
        return

    data = load_data()
    meme = choose_meme_to_send(data)
    if not meme:
        await update.message.reply_text("У мене ще порожній сейф. Закинь мені в приват перші меми 🙂")
        return

    await send_meme(context, TARGET_CHAT_ID, meme)
    mark_sent(data, meme["file_id"])
    save_data(data)

    await update.message.reply_text("Окей, кинула мем у чат ✅")

async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    total = len(data.get("memes", []))
    sent = len(set(data.get("cycle_sent", [])))
    await update.message.reply_text(f"Сейф: {total} мемів.\nУ цьому циклі вже відправлено: {sent}.")

# =========================
# 6) ПРИЙОМ МЕМІВ У ПРИВАТІ
# =========================

async def handle_private_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != ChatType.PRIVATE:
        return

    msg = update.message
    if msg is None:
        return

    data = load_data()

    user = update.effective_user
    added_by = f"@{user.username}" if user and user.username else (user.first_name if user else "unknown")
    added_at = datetime.now().isoformat(timespec="seconds")

    if msg.photo:
        file_id = msg.photo[-1].file_id
        add_meme(data, {"file_id": file_id, "kind": "photo", "added_by": added_by, "added_at": added_at})
        save_data(data)
        await msg.reply_text("Забрала в сейф 🧳✅")
        return

    if msg.animation:
        file_id = msg.animation.file_id
        add_meme(data, {"file_id": file_id, "kind": "animation", "added_by": added_by, "added_at": added_at})
        save_data(data)
        await msg.reply_text("Гіфку сховала. Краса ✨✅")
        return

    if msg.video:
        file_id = msg.video.file_id
        add_meme(data, {"file_id": file_id, "kind": "video", "added_by": added_by, "added_at": added_at})
        save_data(data)
        await msg.reply_text("Відео в сейфі. Я горда собою ✅")
        return

    await msg.reply_text("Я харчуюся тільки мемами: 🖼🎞📹. Кинь контент — і я засяю.")

# =========================
# 7) ТРИГЕР "ютуб мюзік" у групі — ЗАВЖДИ
# =========================

YTM_VARIANTS = [
    "ютуб мюзік",
    "ютюб мюзік",
    "youtube music",
    "ютуб музик",
    "ютюб музик",
]

YTM_PHRASES = [
    "Те її слово? А на тобі **ютуб мюзік**. (вибач, я просто виконую свій обов’язок) 😌",
    "Почула «ютуб мюзік» — і в мені прокинувся крінж-радар 📡",
    "Спокійно. Дихай. Це лише «ютуб мюзік». Ми переживали гірше 💅",
    "Я нічого не кажу… але Spotify дивиться на це з осудом 👀",
]

async def handle_group_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.text:
        return

    text = msg.text.lower().strip()

    if any(v in text for v in YTM_VARIANTS):
        # 100% реакція
        if YTM_TRIGGER_IMAGE_FILE_ID:
            # якщо є картинка — кидаємо її КОЖЕН РАЗ (можна змінити на чергування)
            try:
                await msg.reply_photo(photo=YTM_TRIGGER_IMAGE_FILE_ID)
            except Exception:
                # якщо не вийшло — відправимо текст
                phrase = random.choice(YTM_PHRASES)
                await msg.reply_text(phrase, parse_mode="Markdown")
        else:
            phrase = random.choice(YTM_PHRASES)
            await msg.reply_text(phrase, parse_mode="Markdown")

# =========================
# 8) АВТОПОСТ КОЖНІ 2 ГОДИНИ
# =========================

async def autopost_job(context: ContextTypes.DEFAULT_TYPE):
    if is_quiet_time():
        return
    if TARGET_CHAT_ID == 0:
        return

    data = load_data()
    meme = choose_meme_to_send(data)
    if not meme:
        return

    await send_meme(context, TARGET_CHAT_ID, meme)
    mark_sent(data, meme["file_id"])
    save_data(data)

# =========================
# 9) MAIN
# =========================

def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN порожній. Додай BOT_TOKEN у файл .env")

    app = Application.builder().token(BOT_TOKEN).build()

    # Команди
    app.add_handler(CommandHandler("let", let_cmd))
    app.add_handler(CommandHandler("meme", meme_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))

    # Приват: прийом мемів
    app.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & (filters.PHOTO | filters.VIDEO | filters.ANIMATION | filters.TEXT),
        handle_private_media
    ))

    # Група/супергрупа/канал: тригер
    app.add_handler(MessageHandler(filters.TEXT & ~filters.ChatType.PRIVATE, handle_group_text))

    # Автопост кожні 2 години
    if app.job_queue is not None:
        app.job_queue.run_repeating(autopost_job, interval=AUTOPOST_EVERY_MINUTES * 60, first=30)

    print("Мем-бот запущена ✅ (Ctrl+C щоб зупинити)")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
