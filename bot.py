import os
import sqlite3
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int((os.getenv("ADMIN_ID") or "0").strip())
SEED_ADMIN_IDS = [int(x.strip()) for x in (os.getenv("ADMIN_IDS") or "").split(",") if x.strip().isdigit()]
DB = "chats.db"
MAX_ADMINS = 5
logging.basicConfig(level=logging.INFO)

def db():
    return sqlite3.connect(DB)

def init_db():
    con = db()
    con.execute("CREATE TABLE IF NOT EXISTS chats (chat_id INTEGER PRIMARY KEY, chat_type TEXT, title TEXT, username TEXT)")
    con.execute("CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY)")
    seed = []
    if OWNER_ID:
        seed.append(OWNER_ID)
    seed.extend(SEED_ADMIN_IDS)
    for uid in seed:
        con.execute("INSERT OR IGNORE INTO admins(user_id) VALUES(?)", (uid,))
    con.commit(); con.close()

def get_admins():
    con = db(); rows = con.execute("SELECT user_id FROM admins ORDER BY user_id").fetchall(); con.close()
    return [r[0] for r in rows]

def is_admin(uid): return uid in get_admins()
def is_owner(uid): return OWNER_ID != 0 and uid == OWNER_ID

def save_chat(chat):
    title = chat.title or chat.first_name or ""
    username = chat.username or ""
    con = db()
    con.execute("INSERT OR REPLACE INTO chats(chat_id, chat_type, title, username) VALUES(?,?,?,?)", (chat.id, chat.type, title, username))
    con.commit(); con.close()

def get_chats():
    con = db(); rows = con.execute("SELECT chat_id FROM chats").fetchall(); con.close()
    return [r[0] for r in rows]

async def start(update, context):
    save_chat(update.effective_chat)
    if update.effective_chat.type == "private":
        await update.message.reply_text(f"👋 Welcome!\n\n🆔 Your Telegram User ID: {update.effective_user.id}\n\nမေးချင်တာရှိရင် ဒီမှာ ပို့ပါ။ Admin ဆီကို ပို့ပေးပါမယ်။")
    else:
        await update.message.reply_text("✅ ဒီ Group ကို Broadcast List ထဲ ထည့်ပြီးပါပြီ။")

async def myid(update, context):
    if not update.effective_user or not update.message:
        return
    uid = update.effective_user.id
    await update.message.reply_text(f"🆔 Your Telegram User ID: {uid}\n\nဒီ ID ကို Owner ဆီပို့ပြီး Admin ခန့်ခိုင်းနိုင်ပါတယ်။\n\n📩 ပို့ရန်: @Novel220")

async def addadmin(update, context):
    uid = update.effective_user.id
    if not is_owner(uid):
        await update.message.reply_text(f"❌ Owner only.\nYour ID: {uid}\nConfigured Owner ID: {OWNER_ID}")
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("အသုံးပြုပုံ: /addadmin USER_ID")
        return
    target = int(context.args[0]); admins = get_admins()
    if target in admins:
        await update.message.reply_text(f"⚠️ {target} က Admin ဖြစ်ပြီးသားပါ။")
        return
    if len(admins) >= MAX_ADMINS:
        await update.message.reply_text("❌ Admin အများဆုံး ၅ ယောက်ပဲ ခန့်လို့ရပါတယ်။")
        return
    con = db(); con.execute("INSERT INTO admins(user_id) VALUES(?)", (target,)); con.commit(); con.close()
    notified = True
    try:
        await context.bot.send_message(target, "🎉 သင့်အား Bot Admin အဖြစ် ခန့်အပ်လိုက်ပါပြီ။\n\nယခုမှစ၍ Admin လုပ်ဆောင်ချက်များကို အသုံးပြုနိုင်ပါပြီ။\n\n📖 Admin အသုံးပြုနည်း\n\n👮 /admins — Admin စာရင်းကြည့်ရန်\n📢 /broadcast — Reply ထားသော message ကို Broadcast ပို့ရန်\n📊 /chats — Bot မှတ်ထားသော Chat အရေအတွက်ကြည့်ရန်\n🆔 /myid — မိမိ Telegram ID ကြည့်ရန်\n\n⚠️ /addadmin နဲ့ /removeadmin ကို Owner ပဲ အသုံးပြုနိုင်ပါတယ်။")
    except Exception as e:
        notified = False
        logging.warning("Could not notify new admin %s: %s", target, e)
    note = "\n📩 Admin ကို အကြောင်းကြားပြီးပါပြီ။" if notified else "\n⚠️ Admin ကို Message မပို့နိုင်သေးပါ။ Bot ကို /start အရင်လုပ်ထားရပါမယ်။"
    await update.message.reply_text(f"✅ Admin ခန့်ပြီးပါပြီ။\nID: {target}\nAdmin: {len(admins)+1}/{MAX_ADMINS}{note}")

async def removeadmin(update, context):
    if not is_owner(update.effective_user.id):
        await update.message.reply_text("❌ ဒီ command ကို Owner ပဲ သုံးနိုင်ပါတယ်။")
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("အသုံးပြုပုံ: /removeadmin USER_ID"); return
    target=int(context.args[0])
    if target == OWNER_ID:
        await update.message.reply_text("❌ Owner ကို မဖြုတ်နိုင်ပါ။"); return
    con=db(); cur=con.execute("DELETE FROM admins WHERE user_id=?",(target,)); con.commit(); con.close()
    if cur.rowcount:
        notified = True
        try:
            await context.bot.send_message(target, "ℹ️ သင့်အား Bot Admin အဖြစ်မှ ဖြုတ်လိုက်ပါပြီ။")
        except Exception as e:
            notified = False
            logging.warning("Could not notify removed admin %s: %s", target, e)
        note = "\n📩 Admin ဖြုတ်ကြောင်း အကြောင်းကြားပြီးပါပြီ။" if notified else "\n⚠️ Admin ကို Message မပို့နိုင်ပါ။ Bot ကို /start အရင်လုပ်ထားဖို့လိုပါတယ်။"
        await update.message.reply_text(f"✅ Admin ဖြုတ်ပြီးပါပြီ။{note}")
    else:
        await update.message.reply_text("❌ ဒီ ID က Admin စာရင်းထဲ မရှိပါ။")

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

async def admins_cmd(update, context):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin only."); return
    admins=get_admins(); lines=[]
    for i,uid in enumerate(admins,1): lines.append(f"{i}. {uid}" + (" 👑 Owner" if uid==OWNER_ID else ""))
    await update.message.reply_text("👮 Admin List\n\n" + "\n".join(lines) + f"\n\nစုစုပေါင်း: {len(admins)}/{MAX_ADMINS}")

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

async def handle_message(update, context):
    if not update.message or not update.effective_chat: return
    save_chat(update.effective_chat)
    if update.effective_chat.type == "private" and not is_admin(update.effective_user.id):
        for aid in get_admins():
            try: await context.bot.forward_message(aid, update.effective_chat.id, update.message.message_id)
            except Exception as e: logging.warning("Forward to admin %s failed: %s",aid,e)
        await update.message.reply_text("✅ မေးခွန်းကို Admin ဆီ ပို့ပြီးပါပြီ။")

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
    app.add_handler(CommandHandler("addadmin",addadmin))
    app.add_handler(CommandHandler("removeadmin",removeadmin))
    app.add_handler(CommandHandler("admins",admins_cmd))
    app.add_handler(CommandHandler("adminhelp",adminhelp))
    app.add_handler(CommandHandler("broadcast",broadcast))
    app.add_handler(CommandHandler("chats",chats_cmd))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND,handle_message))
    print(f"Bot is running... Owner={OWNER_ID} Admins={get_admins()}")
    app.run_polling()

if __name__ == "__main__": main()
