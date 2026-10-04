import os
import sqlite3
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("ADMIN_ID", "0") or 0)
SEED_ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()]
DB = "chats.db"
MAX_ADMINS = 5

logging.basicConfig(level=logging.INFO)


def db():
    return sqlite3.connect(DB)


def init_db():
    con = db()
    con.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            chat_id INTEGER PRIMARY KEY,
            chat_type TEXT,
            title TEXT,
            username TEXT
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY
        )
    """)

    # Bootstrap admins from environment variables only when they are not already stored.
    current = [r[0] for r in con.execute("SELECT user_id FROM admins ORDER BY user_id").fetchall()]
    seed = []
    if OWNER_ID:
        seed.append(OWNER_ID)
    seed.extend(SEED_ADMIN_IDS)
    for uid in seed:
        if uid not in current and len(current) < MAX_ADMINS:
            con.execute("INSERT OR IGNORE INTO admins(user_id) VALUES(?)", (uid,))
            current.append(uid)

    con.commit()
    con.close()


def get_admins():
    con = db()
    rows = con.execute("SELECT user_id FROM admins ORDER BY user_id").fetchall()
    con.close()
    return [r[0] for r in rows]


def is_admin(user_id):
    return user_id in get_admins()


def is_owner(user_id):
    return OWNER_ID != 0 and user_id == OWNER_ID


def save_chat(chat):
    title = chat.title or chat.first_name or ""
    username = chat.username or ""
    con = db()
    con.execute(
        "INSERT OR REPLACE INTO chats(chat_id, chat_type, title, username) VALUES(?,?,?,?)",
        (chat.id, chat.type, title, username)
    )
    con.commit()
    con.close()


def get_chats():
    con = db()
    rows = con.execute("SELECT chat_id FROM chats").fetchall()
    con.close()
    return [row[0] for row in rows]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_chat(update.effective_chat)
    if update.effective_chat.type == "private":
        await update.message.reply_text(
            "👋 Welcome!\n\n"
            "မေးချင်တာရှိရင် ဒီမှာ ပို့ပါ။\n"
            "Admin ဆီကို မေးခွန်းပို့ပေးပါမယ်။"
        )
    else:
        await update.message.reply_text("✅ ဒီ Group ကို Broadcast List ထဲ ထည့်ပြီးပါပြီ။")


async def addadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        return

    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("အသုံးပြုပုံ: /addadmin USER_ID")
        return

    user_id = int(context.args[0])
    admins = get_admins()
    if user_id in admins:
        await update.message.reply_text("⚠️ ဒီ User က Admin ဖြစ်ပြီးသားပါ။")
        return
    if len(admins) >= MAX_ADMINS:
        await update.message.reply_text("❌ Admin အများဆုံး ၅ ယောက်ပဲ ခန့်လို့ရပါတယ်။")
        return

    con = db()
    con.execute("INSERT INTO admins(user_id) VALUES(?)", (user_id,))
    con.commit()
    con.close()
    await update.message.reply_text(f"✅ Admin ခန့်ပြီးပါပြီ။\nID: {user_id}")


async def removeadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        return

    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("အသုံးပြုပုံ: /removeadmin USER_ID")
        return

    user_id = int(context.args[0])
    if user_id == OWNER_ID:
        await update.message.reply_text("❌ Owner ကို Admin စာရင်းကနေ မဖြုတ်နိုင်ပါ။")
        return

    con = db()
    cur = con.execute("DELETE FROM admins WHERE user_id=?", (user_id,))
    con.commit()
    con.close()
    if cur.rowcount:
        await update.message.reply_text(f"✅ Admin ဖြုတ်ပြီးပါပြီ။\nID: {user_id}")
    else:
        await update.message.reply_text("❌ ဒီ ID က Admin စာရင်းထဲ မရှိပါ။")


async def admins_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    admins = get_admins()
    lines = [f"{i}. `{uid}`" + (" 👑 Owner" if uid == OWNER_ID else "") for i, uid in enumerate(admins, 1)]
    await update.message.reply_text(
        "👮 Admin List\n\n" + ("\n".join(lines) if lines else "မရှိသေးပါ။") + f"\n\nစုစုပေါင်း: {len(admins)}/{MAX_ADMINS}",
        parse_mode="Markdown"
    )


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    replied = update.message.reply_to_message
    if not replied:
        await update.message.reply_text("❌ Broadcast လုပ်မယ့် Message ကို Reply ထောက်ပြီး /broadcast ရိုက်ပါ။")
        return

    success = failed = 0
    for chat_id in get_chats():
        try:
            await context.bot.copy_message(
                chat_id=chat_id,
                from_chat_id=update.effective_chat.id,
                message_id=replied.message_id
            )
            success += 1
        except Exception as e:
            logging.warning("Broadcast failed for %s: %s", chat_id, e)
            failed += 1
    await update.message.reply_text(f"📢 Broadcast ပြီးပါပြီ\n\n📨 Sent: {success}\n❌ Failed: {failed}")


async def chats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    con = db()
    rows = con.execute("SELECT chat_type, COUNT(*) FROM chats GROUP BY chat_type").fetchall()
    con.close()
    counts = dict(rows)
    await update.message.reply_text(
        "📊 Broadcast Chats\n\n"
        f"👤 Private: {counts.get('private', 0)}\n"
        f"👥 Group: {counts.get('group', 0)}\n"
        f"👥 Supergroup: {counts.get('supergroup', 0)}"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat:
        return
    chat = update.effective_chat
    save_chat(chat)

    if chat.type == "private" and not is_admin(update.effective_user.id):
        for admin_id in get_admins():
            try:
                await context.bot.forward_message(
                    chat_id=admin_id,
                    from_chat_id=chat.id,
                    message_id=update.message.message_id
                )
            except Exception as e:
                logging.warning("Forward to admin %s failed: %s", admin_id, e)
        await update.message.reply_text("✅ မေးခွန်းကို Admin ဆီ ပို့ပြီးပါပြီ။")


def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN မရှိပါ။")
    if not OWNER_ID and not SEED_ADMIN_IDS:
        raise RuntimeError("ADMIN_ID သို့မဟုတ် ADMIN_IDS မရှိပါ။")

    init_db()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addadmin", addadmin))
    app.add_handler(CommandHandler("removeadmin", removeadmin))
    app.add_handler(CommandHandler("admins", admins_cmd))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("chats", chats_cmd))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))
    print("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
