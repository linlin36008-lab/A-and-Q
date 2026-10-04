import os
import sqlite3
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int((os.getenv("ADMIN_ID") or "0").strip())
SEED_ADMIN_IDS = []
DB = "chats.db"
MAX_ADMINS = 1
logging.basicConfig(level=logging.INFO)

def db():
    return sqlite3.connect(DB)

def init_db():
    con = db()
    con.execute("CREATE TABLE IF NOT EXISTS chats (chat_id INTEGER PRIMARY KEY, chat_type TEXT, title TEXT, username TEXT)")
    con.execute("CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY)")
    con.execute("CREATE TABLE IF NOT EXISTS reply_map (owner_message_id INTEGER PRIMARY KEY, user_chat_id INTEGER NOT NULL)")
    seed = []
    if OWNER_ID:
        seed.append(OWNER_ID)
    seed.extend(SEED_ADMIN_IDS)
    for uid in seed:
        con.execute("INSERT OR IGNORE INTO admins(user_id) VALUES(?)", (uid,))
    con.commit(); con.close()

def get_admins():
    con = db(); rows = con.execute("SELECT user_id FROM admins ORDER BY user_id").fetchall(); con.close()
    return [OWNER_ID] if OWNER_ID else []

def is_admin(uid): return uid in get_admins()
def is_owner(uid): return OWNER_ID != 0 and uid == OWNER_ID

def save_reply_map(owner_message_id, user_chat_id):
    con = db(); con.execute("INSERT OR REPLACE INTO reply_map(owner_message_id, user_chat_id) VALUES(?,?)", (owner_message_id, user_chat_id)); con.commit(); con.close()

def get_reply_user(owner_message_id):
    con = db(); row = con.execute("SELECT user_chat_id FROM reply_map WHERE owner_message_id=?", (owner_message_id,)).fetchone(); con.close()
    return row[0] if row else None

def save_chat(chat):
    title = chat.title or chat.first_name or ""
    username = chat.username or ""
    con = db()
    con.execute("INSERT OR REPLACE INTO chats(chat_id, chat_type, title, username) VALUES(?,?,?,?)", (chat.id, chat.type, title, username))
    con.commit(); con.close()

def get_chats():
    con = db(); rows = con.execute("SELECT chat_id FROM chats").fetchall(); con.close()
    return [OWNER_ID] if OWNER_ID else []

async def start(update, context):
    save_chat(update.effective_chat)
    if update.effective_chat.type == "private":
        if is_owner(update.effective_user.id):
            text = (
                "👋 Welcome Owner!\n\n"
                "📖 Bot အသုံးပြုနည်း\n\n"
                "📩 User ဆီက Message ရလာရင် — User message ကို Reply ပြန်ပြီး ဖြေပါ။\n"
                "📢 Broadcast — ပို့ချင်တဲ့ Message ကို Reply ထောက်ပြီး /broadcast ရိုက်ပါ။\n"
                "📊 /chats — မှတ်ထားတဲ့ Chat အရေအတွက်ကြည့်ရန်\n"
                "🆔 /myid — Telegram User ID ကြည့်ရန်\n"
                "❓ /adminhelp — Admin Commands အပြည့်အစုံကြည့်ရန်"
            )
        else:
            text = (
                "👋 Welcome!\n\n"
                "📖 အသုံးပြုနည်း\n\n"
                "💬 မေးချင်တာ၊ ပြောချင်တာရှိရင် ဒီ Bot ထဲကို တိုက်ရိုက်ပို့ပါ။\n"
                "📩 သင့် Message ကို Owner ဆီ ပို့ပေးပါမယ်။\n"
                "↩️ Owner ပြန်ဖြေတဲ့အခါ ဒီ Chat ထဲမှာ ပြန်ရရှိပါမယ်။\n\n"
                f"🆔 Your Telegram User ID: {update.effective_user.id}"
            )
        await update.message.reply_text(text)
    else:
        await update.message.reply_text(
            "✅ ဒီ Group ကို Broadcast List ထဲ ထည့်ပြီးပါပြီ။\n\n"
            "📢 Owner က /broadcast နဲ့ Message ပို့နိုင်ပါတယ်။"
        )

async def myid(update, context):
    if not update.effective_user or not update.message:
        return
    uid = update.effective_user.id
    await update.message.reply_text(f"🆔 Your Telegram User ID: {uid}\n\nဒီ ID ကို Owner ဆီပို့ပြီး Admin ခန့်ခိုင်းနိုင်ပါတယ်။\n\n📩 ပို့ရန်: @Novel220")

async def adminhelp(update, context):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin only.")
        return
    await update.message.reply_text(
        "📖 Bot Admin အသုံးပြုနည်း\n\n"
        "👮 /admins — Admin စာရင်းကြည့်ရန်\n"
        "📢 /broadcast — Reply ထားသော message ကို Broadcast ပို့ရန်\n"
        "📊 /chats — Bot မှတ်ထားသော Chat အရေအတွက်ကြည့်ရန်\n"
        "🆔 /myid — မိမိ Telegram ID ကြည့်ရန်\n\n"
        "⚠️ /addadmin USER_ID — Owner only\n"
        "⚠️ /removeadmin USER_ID — Owner only"
    )

async def broadcast(update, context):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin only."); return
    replied=update.message.reply_to_message
    if not replied:
        await update.message.reply_text("❌ Broadcast လုပ်မယ့် Message ကို Reply ထောက်ပြီး /broadcast ရိုက်ပါ။"); return
    success=failed=0
    for chat_id in get_chats():
        try:
            await context.bot.copy_message(chat_id, update.effective_chat.id, replied.message_id); success+=1
        except Exception as e: logging.warning("Broadcast failed %s: %s",chat_id,e); failed+=1
    await update.message.reply_text(f"📢 Broadcast ပြီးပါပြီ\n📨 Sent: {success}\n❌ Failed: {failed}")

async def chats_cmd(update, context):
    if not is_admin(update.effective_user.id): await update.message.reply_text("❌ Admin only."); return
    con=db(); rows=con.execute("SELECT chat_type,COUNT(*) FROM chats GROUP BY chat_type").fetchall(); con.close(); c=dict(rows)
    await update.message.reply_text(f"📊 Broadcast Chats\n\n👤 Private: {c.get('private',0)}\n👥 Group: {c.get('group',0)}\n👥 Supergroup: {c.get('supergroup',0)}")

async def owner_reply(update, context):
    """Owner replies to a user by using Telegram's Reply button on the forwarded user message."""
    if not update.message or not update.effective_chat or not update.effective_user:
        return
    if update.effective_chat.type != "private" or not is_owner(update.effective_user.id):
        return
    replied = update.message.reply_to_message
    if not replied:
        return
    user_id = get_reply_user(replied.message_id)
    if not user_id:
        return
    try:
        # Copy the owner's reply to the original user. Works for text, photos, videos,
        # documents, stickers, voice, audio, etc.
        await context.bot.copy_message(
            chat_id=user_id,
            from_chat_id=update.effective_chat.id,
            message_id=update.message.message_id,
        )
        await update.message.reply_text("✅ User ဆီ ပြန်ပို့ပြီးပါပြီ။", quote=True)
    except Exception as e:
        logging.warning("Reply to user %s failed: %s", user_id, e)
        await update.message.reply_text("❌ User ဆီ ပြန်ပို့မရပါ။ User က bot ကို /start လုပ်ထားရပါမယ်။", quote=True)

async def handle_message(update, context):
    if not update.message or not update.effective_chat: return
    save_chat(update.effective_chat)
    if update.effective_chat.type == "private" and not is_admin(update.effective_user.id):
        for aid in get_admins():
            try:
                sent = await context.bot.forward_message(aid, update.effective_chat.id, update.message.message_id)
                # Save the exact Owner-side message ID so Owner can simply Reply to it.
                save_reply_map(sent.message_id, update.effective_chat.id)
            except Exception as e:
                logging.warning("Forward to admin %s failed: %s",aid,e)
        await update.message.reply_text("✅ မေးခွန်းကို Owner ဆီ ပို့ပြီးပါပြီ။")

def main():
    if not TOKEN: raise RuntimeError("BOT_TOKEN မရှိပါ။")
    if not OWNER_ID and not SEED_ADMIN_IDS: raise RuntimeError("ADMIN_ID သို့မဟုတ် ADMIN_IDS မရှိပါ။")
    init_db()
    app=Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler(["myid", "id"],myid))
    # Fallback: also catch /myid or /myid@BotUsername as plain text.
    app.add_handler(MessageHandler(filters.Regex(r"^/myid(?:@\w+)?(?:\s*)$") , myid))
    app.add_handler(MessageHandler(filters.Regex(r"^/id(?:@\w+)?(?:\s*)$") , myid))
    app.add_handler(CommandHandler("adminhelp",adminhelp))
    app.add_handler(CommandHandler("broadcast",broadcast))
    # Owner can reply directly to any forwarded user message.
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, owner_reply), group=0)
    app.add_handler(CommandHandler("chats",chats_cmd))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND,handle_message), group=1)
    print(f"Bot is running... Owner={OWNER_ID} Admins={get_admins()}")
    app.run_polling()

if __name__ == "__main__": main()
