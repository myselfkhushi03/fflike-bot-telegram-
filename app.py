#━━━━━━━━━━━━━━━━━━━
# 𝗠𝗔𝗗𝗘 𝗕𝗬 CHIKUU LIKE BOT
# 𝗣𝗥𝗢𝗝𝗘𝗖𝗧𝗦 SK
# 𝗠𝗬 𝗨𝗦𝗘𝗥 : @myselfkhushi03
#━━━━━━━━━━━━━━━━━━━
import json
import asyncio
import aiohttp
import base64
import nest_asyncio
from datetime import datetime, timedelta
from pytz import timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    ChatMemberHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
import logging
import os
import sys
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ================= 👑 CONFIG (Environment Variables) =================

CHANNEL_1 = os.getenv("CHANNEL_1", "@YourChannel1")
CHANNEL_2 = os.getenv("CHANNEL_2", "@YourChannel2")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Multiple Owner IDs parsing from comma-separated env string (e.g. "1234,5678")
raw_owners = os.getenv("OWNER_IDS", "")
OWNER_IDS = [int(i.strip()) for i in raw_owners.split(",") if i.strip().isdigit()]

BOT_ENABLED = True

# Allowed Group IDs parsing
raw_groups = os.getenv("ALLOWED_GROUP_IDS", "")
ALLOWED_GROUP_IDS = [int(i.strip()) for i in raw_groups.split(",") if i.strip().isdigit()]

REPORT_CHAT_ID = int(os.getenv("REPORT_CHAT_ID", "0"))

API_URL = os.getenv("API_URL", "http://example.com/api?uid={uid}&server={region}")
DEMO_API_URL = os.getenv("DEMO_API_URL", "http://example.com/demo?uid={uid}&region={region}")
TOKEN_GEN_API_URL = os.getenv("TOKEN_GEN_API_URL", "https://vipjwt.ffbot.site/token?uid={uid}&password={pwd}")

# GitHub Settings
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")  # Format: "username/repo_name"
FILE_PATH_IN_REPO = os.getenv("FILE_PATH_IN_REPO", "token.json")

# Scheduler Setup for 3-Hour Auto Task
scheduler = AsyncIOScheduler()
AUTO_JOB_ID = "auto_jwt_update_job"

SEND_LIKE_TIME = os.getenv("SEND_LIKE_TIME", "04:00 AM")
DATA_FILE = "autolike_data.json"
GROUP_DATA_FILE = "allowed_groups.json"
ADMIN_DATA_FILE = "admin_data.json"
ACCOUNTS_FILE = "accounts.json"
TIMEZONE = timezone("Asia/Kolkata")

# USER DAILY LIMIT
USER_DAILY_LIMIT = int(os.getenv("USER_DAILY_LIMIT", "1"))
USER_USAGE = {}

# ================= 🚀 GITHUB AUTO UPDATE FUNCTIONS =================

async def push_to_github(file_content_str: str) -> bool:
    """GitHub Repository me token.json update karne ka function"""
    if not GITHUB_TOKEN or not GITHUB_REPO:
        logger.error("GitHub Configuration (GITHUB_TOKEN or GITHUB_REPO) is missing!")
        return False

    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{FILE_PATH_IN_REPO}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }

    async with aiohttp.ClientSession() as session:
        sha = None
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                res_data = await response.json()
                sha = res_data.get("sha")

        encoded_content = base64.b64encode(file_content_str.encode('utf-8')).decode('utf-8')

        payload = {
            "message": "Auto 3-Hour JWT Token Update via Bot",
            "content": encoded_content
        }
        if sha:
            payload["sha"] = sha

        async with session.put(url, headers=headers, json=payload) as put_res:
            return put_res.status in [200, 201]


async def auto_update_tokens_task(context: ContextTypes.DEFAULT_TYPE):
    """Har 3 ghante me automatic chalne wala task"""
    try:
        if not os.path.exists(ACCOUNTS_FILE):
            logger.warning(f"Accounts file {ACCOUNTS_FILE} not found. Skipping auto token update.")
            return

        with open(ACCOUNTS_FILE, "r") as f:
            accounts = json.load(f)

        jwt_list = []
        async with aiohttp.ClientSession() as session:
            for acc in accounts:
                uid = acc.get("uid")
                pwd = acc.get("password") or acc.get("pwd")
                if not uid or not pwd:
                    continue
                
                url = TOKEN_GEN_API_URL.format(uid=uid, pwd=pwd)
                try:
                    async with session.get(url, timeout=15) as res:
                        data = await res.json()
                        token = data.get("Jwt token") or data.get("token")
                        if token:
                            jwt_list.append({"uid": uid, "token": token})
                except Exception as e:
                    logger.error(f"Error fetching token for UID {uid}: {e}")

        if jwt_list:
            json_str = json.dumps(jwt_list, indent=2)
            success = await push_to_github(json_str)

            if success and REPORT_CHAT_ID != 0:
                await context.bot.send_message(
                    chat_id=REPORT_CHAT_ID,
                    text="🤖 🔄 **Auto 3-Hour Update Success!**\nNew JWT Tokens updated on GitHub.",
                    parse_mode="Markdown"
                )
            elif not success and REPORT_CHAT_ID != 0:
                await context.bot.send_message(
                    chat_id=REPORT_CHAT_ID,
                    text="❌ **Auto Token Update Failed!** Check GitHub Credentials.",
                    parse_mode="Markdown"
                )
    except Exception as e:
        logger.error(f"Auto Task Execution Error: {e}")

# ================= 🎛️ AUTO COMMAND HANDLERS =================

async def start_auto_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command: /startauto -> Har 3 ghante me auto update chalu karega"""
    if not await is_owner(update):
        await update.message.reply_text("🚫 Owner Only")
        return

    if scheduler.get_job(AUTO_JOB_ID):
        await update.message.reply_text("⚠️ **Auto Update pehle se active hai!** (Har 3 ghante me chal raha hai)", parse_mode="Markdown")
        return

    scheduler.add_job(
        auto_update_tokens_task,
        'interval',
        hours=3,
        id=AUTO_JOB_ID,
        kwargs={'context': context}
    )

    asyncio.create_task(auto_update_tokens_task(context))

    await update.message.reply_text(
        "✅ **Auto-Update Started!**\n\n"
        "⚡ Ab bot har **3 Ghante** me automatic tokens generate karke GitHub pe update karta rahega.\n"
        "🛑 Stop karne ke liye `/stopauto` command bhejien.",
        parse_mode="Markdown"
    )


async def stop_auto_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command: /stopauto -> Auto update process stop kar dega"""
    if not await is_owner(update):
        await update.message.reply_text("🚫 Owner Only")
        return

    job = scheduler.get_job(AUTO_JOB_ID)
    if job:
        scheduler.remove_job(AUTO_JOB_ID)
        await update.message.reply_text("🛑 **Auto Update Process STOPPED successfully!**", parse_mode="Markdown")
    else:
        await update.message.reply_text("⚠️ **Auto Update active nahi tha.**", parse_mode="Markdown")

# ================= 📁 ADMIN DATA MANAGEMENT =================

def load_admin_data():
    try:
        with open(ADMIN_DATA_FILE, "r") as f:
            return json.load(f)
    except:
        return {"admins": [], "admin_limits": {}}

def save_admin_data(data):
    with open(ADMIN_DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def is_admin(user_id):
    if user_id in OWNER_IDS:
        return True
    admin_data = load_admin_data()
    return user_id in admin_data.get("admins", [])

# ================= 📁 GROUP DATA MANAGEMENT =================

def load_group_data():
    try:
        with open(GROUP_DATA_FILE, "r") as f:
            data = json.load(f)
            return data.get("groups", [])
    except:
        return []

def is_group_allowed(chat_id):
    if chat_id in ALLOWED_GROUP_IDS:
        return True
    if chat_id < 0 and abs(chat_id) in ALLOWED_GROUP_IDS:
        return True
    if chat_id > 0 and -chat_id in ALLOWED_GROUP_IDS:
        return True
    return False

# ================= ⚙ BASIC =================

async def is_owner(update: Update):
    return update.effective_user.id in OWNER_IDS

def hide_uid(uid):
    uid = str(uid)
    if len(uid) <= 7:
        return uid
    return uid[:4] + "****" + uid[-3:]

def load_data():
    try:
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
    except:
        data = {}
    data.setdefault("last_run_date", None)
    data.setdefault("uids", [])
    data.setdefault("total_likes_given", 0)
    return data

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

async def group_only(update: Update):
    chat = update.effective_chat
    if chat.type == "private":
        if update.message and update.message.text:
            command = update.message.text.split()[0].lower()
            if command in ["/help", "/start", "/startauto", "/stopauto", "/autolike", "/runall"]:
                return True
        await update.message.reply_text(
            f"🚫 This bot works only in the official group.\n\n👉 Join here:\nhttps://t.me/{CHANNEL_1.replace('@', '')}"
        )
        return False
    return True

# ================= 🌐 API =================

async def call_api(session, uid, region, api_url=None):
    if api_url is None:
        api_url = API_URL
    try:
        async with session.get(api_url.format(uid=uid, region=region), timeout=35) as r:
            return await r.json()
    except Exception as e:
        logger.error(f"API Error: {e}")
        return None

# ================= ❤️ SEND LIKE =================

async def send_like(app, session, entry, remaining):
    uid = entry["uid"]
    region = entry["region"]
    tg_id = entry.get("tg_id")

    js = await call_api(session, uid, region)
    if not js:
        return False

    likes_given = int(js.get("LikesGivenByAPI", 0))
    if likes_given > 0:
        entry["likes_given"] = entry.get("likes_given", 0) + likes_given
    return likes_given > 0

# ================= ⏰ AUTO PROCESS =================

async def perform_auto_like(app, manual=False):
    data = load_data()
    if not data["uids"]:
        return

    async with aiohttp.ClientSession() as session:
        for entry in data["uids"]:
            await send_like(app, session, entry, 1)
            await asyncio.sleep(3)

    save_data(data)

# ================= COMMANDS =================

async def runall_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await group_only(update) or not await is_owner(update):
        return
    await update.message.reply_text("🔄 Manual auto-like triggered...")
    await perform_auto_like(context.application, manual=True)

async def set_bot_commands(application):
    commands = [
        BotCommand("startauto", "Start Auto 3-Hour GitHub Token Update"),
        BotCommand("stopauto", "Stop Auto Token Update"),
        BotCommand("runall", "Run Like Process Manually"),
        BotCommand("autolike", "Add UID for Auto Like")
    ]
    await application.bot.set_my_commands(commands)

# ================= 🚀 MAIN FUNCTION =================

def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN missing in environment variables!")
        return

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # Register Commands
    app.add_handler(CommandHandler("startauto", start_auto_cmd))
    app.add_handler(CommandHandler("stopauto", stop_auto_cmd))
    app.add_handler(CommandHandler("runall", runall_cmd))

    # Set Menu Commands
    app.post_init = set_bot_commands

    # Start Scheduler
    scheduler.start()

    logger.info("Bot started successfully with Auto-Update Scheduler...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
