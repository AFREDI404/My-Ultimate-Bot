# ================================================================= #
# ==             ULTIMATE TOOLKIT BOT - FINAL VERSION            == #
# ================================================================= #

# -- IMPORTS --
import os
import logging
import random
import requests
import qrcode
from io import BytesIO
from datetime import datetime
from telegram import Update, Bot, ParseMode, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater,
    CommandHandler,
    CallbackContext,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    Filters,
)
from googletrans import Translator
import yt_dlp
from gtts import gTTS
import phonenumbers
import whois

# -- BOT SETUP --
START_TIME = datetime.utcnow()
try:
    ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))
except (ValueError, TypeError):
    ADMIN_ID = 0

# In-memory storage (will reset on bot restart)
ALL_USER_IDS = set()
FEEDBACK_STATE = 0

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- HELPER & ADMIN FUNCTIONS ---
def get_uptime():
    delta = datetime.utcnow() - START_TIME
    days, rem = divmod(delta.total_seconds(), 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    return f"{int(days)}d, {int(hours)}h, {int(minutes)}m"

def restricted(func):
    """Decorator to restrict access to admin-only commands."""
    def wrapped(update, context, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id != ADMIN_ID:
            update.message.reply_text("Sorry, this is an admin-only command.")
            return
        return func(update, context, *args, **kwargs)
    return wrapped

# --- COMMAND HANDLERS ---

def start(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    ALL_USER_IDS.add(user.id) 
    
    keyboard = [
        [InlineKeyboardButton("🤖 All Commands", callback_data='help_main')],
        [InlineKeyboardButton("✍️ Give Feedback", callback_data='feedback_start')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_message = f"Hi {user.first_name}! 👋\n\nWelcome to the **Ultimate Toolkit Bot**! I am running 24/7 on a reliable server. Explore my features using the button below."
    update.message.reply_text(welcome_message, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

def help_command(update: Update, context: CallbackContext) -> None:
    keyboard = [
        [
            InlineKeyboardButton("💳 BIN Tools", callback_data='help_card'),
            InlineKeyboardButton("🌐 Network & Info", callback_data='help_info'),
        ],
        [
            InlineKeyboardButton("🛠️ Power Tools", callback_data='help_power'),
            InlineKeyboardButton("🤖 Admin & Bot", callback_data='help_bot'),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text('Please choose a category:', reply_markup=reply_markup)

def help_callback(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()
    category = query.data.split('_')[1]

    help_texts = {
        'card': "*💳 BIN Tools:*\n`/gen <BIN> [MM] [YY] [CVC]`\n`/bin <BIN>`\n`/check <card>`\n`/rand`",
        'info': "*🌐 Network, Device & Info Tools:*\n`/ip <ip>`\n`/phone <number>`\n`/whois <domain>`\n`/github <user>`\n`/imei <imei>`\n`/weather <city>`\n`/myinfo`",
        'power': "*🛠️ Power Tools:*\n`/tr <lang> <text>`\n`/yt <url>`\n`/qr <text>`\n`/short <url>`\n`/paste <text>`\n`/tts <lang> <text>`",
        'bot': "*🤖 Admin & Bot Management:*\n`/start`\n`/help`\n`/broadcast <msg>`\n`/feedback`\n`/ping`\n`/uptime`"
    }
    
    back_button = [[InlineKeyboardButton("⬅️ Back to menu", callback_data='help_main')]]
    reply_markup = InlineKeyboardMarkup(back_button)

    if category == 'main':
        keyboard = [
             [
                InlineKeyboardButton("💳 BIN Tools", callback_data='help_card'),
                InlineKeyboardButton("🌐 Network & Info", callback_data='help_info'),
            ],
            [
                InlineKeyboardButton("🛠️ Power Tools", callback_data='help_power'),
                InlineKeyboardButton("🤖 Admin & Bot", callback_data='help_bot'),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text(text='Please choose a category:', reply_markup=reply_markup)
    else:
        query.edit_message_text(text=help_texts.get(category, "Invalid category."), reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

# --- ADMIN & FEEDBACK ---
@restricted
def broadcast(update: Update, context: CallbackContext) -> None:
    if not context.args: update.message.reply_text("Usage: `/broadcast <message>`"); return
    msg_to_send = " ".join(context.args); message = update.message.reply_text(f"Broadcasting...")
    count = 0
    for user_id in ALL_USER_IDS:
        try:
            context.bot.send_message(chat_id=user_id, text=f"📢 *Admin Broadcast:*\n\n{msg_to_send}", parse_mode=ParseMode.MARKDOWN)
            count += 1
        except Exception: logger.warning(f"Could not send to user {user_id}")
    message.edit_text(f"Broadcast sent to {count} users.")
def feedback_start(update: Update, context: CallbackContext) -> int:
    if update.callback_query: update.callback_query.answer(); update.callback_query.message.reply_text("Please write your feedback. To cancel: /cancel.")
    else: update.message.reply_text("Please write your feedback. To cancel: /cancel.")
    return FEEDBACK_STATE
def get_feedback(update: Update, context: CallbackContext) -> int:
    user = update.effective_user; feedback = update.message.text
    context.bot.send_message(chat_id=ADMIN_ID, text=f"✍️ *New Feedback Received!*\n\n*From:* {user.first_name} (@{user.username})\n*ID:* `{user.id}`\n\n*Message:*\n{feedback}", parse_mode=ParseMode.MARKDOWN)
    update.message.reply_text("Thank you for your feedback!")
    return ConversationHandler.END
def cancel_feedback(update: Update, context: CallbackContext) -> int:
    update.message.reply_text("Feedback cancelled."); return ConversationHandler.END

# --- BIN TOOLS ---
def is_luhn_valid(card_number):
    try:
        n, s, is_second = len(card_number), 0, False
        for i in range(n - 1, -1, -1):
            d = int(card_number[i])
            if is_second: d *= 2
            s += d // 10; s += d % 10; is_second = not is_second
        return s % 10 == 0
    except: return False
def generate_card(bin_number, month=None, year=None, cvv=None):
    card_number = bin_number + ''.join(random.choices('0123456789', k=16 - len(bin_number)))
    for i in range(10):
        temp_card = card_number[:-1] + str(i)
        if is_luhn_valid(temp_card): card_number = temp_card; break
    exp_month = month if month and month.isdigit() else f"{random.randint(1, 12):02d}"
    exp_year = year if year and year.isdigit() else str(random.randint(25, 30))
    gen_cvv = cvv if cvv and cvv.isdigit() else f"{random.randint(100, 999):03d}"
    return f"{card_number}|{exp_month}|{exp_year}|{gen_cvv}"
def get_bin_info(bin_number):
    try:
        data = requests.get(f"https://lookup.binlist.net/{bin_number[:6]}").json()
        return (f"🔹 **Issuer:** {data.get('bank', {}).get('name', 'N/A')}\n"
                f"🔹 **Country:** {data.get('country', {}).get('name', 'N/A')}\n"
                f"🔹 **Type:** {data.get('type', 'N/A').capitalize()}\n"
                f"🔹 **Scheme:** {data.get('scheme', 'N/A').capitalize()}")
    except: return "🔹 BIN Information not found."
def gen_command(update: Update, context: CallbackContext) -> None:
    if not context.args or not context.args[0].isdigit() or len(context.args[0]) < 6:
        update.message.reply_text("❌ Usage: `/gen <BIN> [MM] [YY] [CVC]`"); return
    bin_num, m, y, c = context.args[0], context.args[1] if len(context.args) > 1 else None, context.args[2] if len(context.args) > 2 else None, context.args[3] if len(context.args) > 3 else None
    msg = update.message.reply_text("⏳ Generating cards...")
    cards = "\n".join([f"`{generate_card(bin_num, m, y, c)}`" for _ in range(10)])
    msg.edit_text(f"🔴 **Generated Cards:**\n{cards}\n\n{get_bin_info(bin_num)}", parse_mode=ParseMode.MARKDOWN)
def bin_command(update: Update, context: CallbackContext) -> None:
    if not context.args or not context.args[0].isdigit() or len(context.args[0]) < 6: update.message.reply_text("❌ Usage: `/bin <BIN>`"); return
    update.message.reply_text(get_bin_info(context.args[0]), parse_mode=ParseMode.MARKDOWN)
def check_command(update: Update, context: CallbackContext) -> None:
    if not context.args or not context.args[0].isdigit(): update.message.reply_text("❌ Usage: `/check <card_number>`"); return
    update.message.reply_text(f"✅ **Valid**" if is_luhn_valid(context.args[0]) else f"❌ **Invalid**", parse_mode=ParseMode.MARKDOWN)
def rand_command(update: Update, context: CallbackContext) -> None:
    bin = random.choice(["457382", "536418", "491267", "549618", "426285", "378282"])
    card = generate_card(bin)
    update.message.reply_text(f"🔴 **Generated Card:**\n`{card}`\n\n{get_bin_info(bin)}", parse_mode=ParseMode.MARKDOWN)

# --- NETWORK, DEVICE & INFO TOOLS ---
def ip_lookup(update: Update, context: CallbackContext) -> None:
    if not context.args: update.message.reply_text("Usage: `/ip <ip_address>`"); return
    ip = context.args[0]
    try:
        data = requests.get(f"http://ip-api.com/json/{ip}").json()
        if data['status'] == 'success':
            res = (f"🔍 **IP Information for `{ip}`**\n\n"
                   f"Country: `{data.get('country', 'N/A')}`\n"
                   f"Region: `{data.get('regionName', 'N/A')}`\n"
                   f"City: `{data.get('city', 'N/A')}`\n"
                   f"ZIP Code: `{data.get('zip', 'N/A')}`\n"
                   f"Coordinates: `{data.get('lat', 0)}, {data.get('lon', 0)}`\n"
                   f"ISP: `{data.get('isp', 'N/A')}`\n"
                   f"Organization: `{data.get('org', 'N/A')}`")
            update.message.reply_text(res, parse_mode=ParseMode.MARKDOWN)
        else: update.message.reply_text("Could not find info for this IP.")
    except: update.message.reply_text("An error occurred.")
def phone_lookup(update: Update, context: CallbackContext) -> None:
    if not context.args: update.message.reply_text("Usage: `/phone <phone_number_with_country_code>`"); return
    num = " ".join(context.args)
    try:
        p = phonenumbers.parse(num, None)
        if not phonenumbers.is_valid_number(p):
            update.message.reply_text("❌ Invalid phone number format."); return
        
        country = phonenumbers.region_code_for_number(p)
        carrier_name = phonenumbers.carrier.name_for_number(p, "en")
        timezone = phonenumbers.timezone.time_zones_for_number(p)
        
        res = (f"📱 **Phone Number Analysis: `{num}`**\n\n"
               f"✅ Status: `Valid`\n\n"
               f"--- Formatting ---\n"
               f"International: `{phonenumbers.format_number(p, phonenumbers.PhoneNumberFormat.INTERNATIONAL)}`\n"
               f"National: `{phonenumbers.format_number(p, phonenumbers.PhoneNumberFormat.NATIONAL)}`\n"
               f"E.164: `{phonenumbers.format_number(p, phonenumbers.PhoneNumberFormat.E164)}`\n\n"
               f"--- Details ---\n"
               f"Country: `{country}`\n"
               f"Carrier: `📶 {carrier_name or 'N/A'}`\n"
               f"Timezone(s): `🌏 {', '.join(timezone) or 'N/A'}`")
        update.message.reply_text(res, parse_mode=ParseMode.MARKDOWN)
    except Exception as e: update.message.reply_text(f"Could not parse number. Ensure it includes '+'.\nError: {e}")
def whois_lookup(update: Update, context: CallbackContext) -> None:
    if not context.args: update.message.reply_text("Usage: `/whois <domain>` (e.g., google.com)"); return
    domain = context.args[0]
    try:
        w = whois.whois(domain)
        res = (f"🌐 **Whois for `{domain}`**\n\n"
               f"Registrar: `{w.registrar}`\n"
               f"Creation Date: `{w.creation_date}`\n"
               f"Expiration Date: `{w.expiration_date}`\n"
               f"Name Servers: `\n- {'\n- '.join(w.name_servers)}`")
        update.message.reply_text(res, parse_mode=ParseMode.MARKDOWN)
    except: update.message.reply_text("Could not fetch Whois information.")
def github_lookup(update: Update, context: CallbackContext) -> None:
    if not context.args: update.message.reply_text("Usage: `/github <username>`"); return
    username = context.args[0]
    try:
        data = requests.get(f"https://api.github.com/users/{username}").json()
        if data.get("message") == "Not Found": update.message.reply_text("User not found."); return
        
        res = (f"👨‍💻 **GitHub User: {data.get('login')}**\n\n"
               f"**Name:** {data.get('name', 'N/A')}\n"
               f"**Bio:** {data.get('bio', 'N/A')}\n"
               f"**Followers:** {data.get('followers', 0)}\n"
               f"**Following:** {data.get('following', 0)}\n"
               f"**Public Repos:** {data.get('public_repos', 0)}\n"
               f"**Profile Link:** {data.get('html_url')}")
        context.bot.send_photo(chat_id=update.effective_chat.id, photo=data.get('avatar_url'), caption=res, parse_mode=ParseMode.MARKDOWN)
    except: update.message.reply_text("An error occurred.")
def imei_lookup(update: Update, context: CallbackContext) -> None:
    if not context.args or not context.args[0].isdigit(): update.message.reply_text("Usage: `/imei <imei_number>`"); return
    imei = context.args[0]
    update.message.reply_text("Sorry, a reliable free API for IMEI checking is not available at this moment to guarantee service. This feature is under development.")
def weather(update: Update, context: CallbackContext) -> None:
    api_key = os.environ.get("WEATHER_API_KEY")
    if not api_key: update.message.reply_text("Weather API key not configured."); return
    if not context.args: update.message.reply_text("Usage: `/weather <city>`"); return
    city = ' '.join(context.args); url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric"
    try:
        res = requests.get(url).json()
        if res["cod"] == 200:
            msg = (f"*Weather in {res['name']}, {res['sys']['country']}*\n"
                   f"Condition: *{res['weather'][0]['description'].capitalize()}*\n"
                   f"Temp: *{res['main']['temp']}°C* | Humidity: *{res['main']['humidity']}%*")
            update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
        else: update.message.reply_text(f"Could not find weather for '{city}'.")
    except: update.message.reply_text("Error fetching weather data.")

# --- POWER TOOLS ---
def tr(update: Update, context: CallbackContext) -> None:
    if not context.args or len(context.args) < 2: update.message.reply_text("Usage: `/tr <lang_code> <text>`\nEx: `/tr bn I am a bot`"); return
    lang = context.args[0]; text = " ".join(context.args[1:])
    try:
        translated = Translator().translate(text, dest=lang)
        update.message.reply_text(f"Translated to *{lang.upper()}*:\n\n`{translated.text}`", parse_mode=ParseMode.MARKDOWN)
    except: update.message.reply_text("Could not translate. Ensure language code is correct.")
def yt(update: Update, context: CallbackContext) -> None:
    if not context.args: update.message.reply_text("Usage: `/yt <youtube_url>`"); return
    url = context.args[0]; msg = update.message.reply_text("⏳ Fetching video info...")
    ydl_opts = {'quiet': True, 'skip_download': True, 'force_generic_extractor': True, 'noplaylist': True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title, duration = info.get('title', 'N/A'), str(timedelta(seconds=info.get('duration', 0)))
            links = []
            for f in info.get('formats', []):
                if f.get('filesize') and f.get('url'):
                    filesize_mb = round(f['filesize'] / 1048576, 2)
                    links.append(f"[{f.get('format_note', 'video/audio')} ({filesize_mb} MB)]({f.get('url')})")
            
            res_text = f"*{'🎥 ' + title}*\n*⏳ Duration: {duration}*\n\n*Download Links:*\n" + "\n".join(links[:7])
            msg.edit_text(res_text, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
    except: msg.edit_text("Could not process YouTube link. Ensure it is a valid video URL.")
def qr(update: Update, context: CallbackContext) -> None:
    if not context.args: update.message.reply_text("Usage: `/qr <text>`"); return
    text = ' '.join(context.args); img = qrcode.make(text); bio = BytesIO(); bio.name = 'qrcode.png'; img.save(bio, 'PNG'); bio.seek(0)
    update.message.reply_photo(photo=bio, caption=f"QR code for:\n`{text}`", parse_mode=ParseMode.MARKDOWN)
def short(update: Update, context: CallbackContext) -> None:
    if not context.args: update.message.reply_text("Usage: `/short <url>`"); return
    try: res = requests.get(f"http://tinyurl.com/api-create.php?url={context.args[0]}"); update.message.reply_text(f"Shortened URL: `{res.text}`", parse_mode=ParseMode.MARKDOWN)
    except Exception as e: update.message.reply_text(f"Error: {e}")
def paste(update: Update, context: CallbackContext) -> None:
    if not context.args: update.message.reply_text("Usage: `/paste <text>`"); return
    text = " ".join(context.args)
    try: res = requests.post("https://hastebin.com/documents", data=text.encode('utf-8')); update.message.reply_text(f"Pasted: https://hastebin.com/{res.json()['key']}")
    except: update.message.reply_text("Error creating paste.")
def tts(update: Update, context: CallbackContext) -> None:
    if not context.args or len(context.args) < 2: update.message.reply_text("Usage: `/tts <lang> <text>`\nEx: `/tts en Hello`"); return
    lang, text = context.args[0], " ".join(context.args[1:])
    try:
        tts = gTTS(text=text, lang=lang); audio_file = BytesIO(); tts.write_to_fp(audio_file); audio_file.name = 'voice.ogg'; audio_file.seek(0)
        update.message.reply_audio(audio=audio_file)
    except: update.message.reply_text("An error occurred. Check language code.")

# ================================================================= #
# ==                  MAIN LOGIC TO START THE BOT                == #
# ================================================================= #
def main():
    """Main function to setup and run the bot."""
    bot_token = os.environ.get("BOT_TOKEN")
    if not bot_token:
        logger.critical("FATAL: BOT_TOKEN environment variable not found!")
        return

    updater = Updater(bot_token, use_context=True)
    dp = updater.dispatcher

    # Add ConversationHandler for feedback
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('feedback', feedback_start), CallbackQueryHandler(feedback_start, pattern='^feedback_start$')],
        states={FEEDBACK_STATE: [MessageHandler(Filters.text & ~Filters.command, get_feedback)]},
        fallbacks=[CommandHandler('cancel', cancel_feedback)],
    )
    dp.add_handler(conv_handler)
    
    # Add other handlers
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help_command))
    dp.add_handler(CallbackQueryHandler(help_callback, pattern='^help_'))
    dp.add_handler(CallbackQueryHandler(notes_callback, pattern='^notes_show$'))
    dp.add_handler(CommandHandler("save", save_note))
    dp.add_handler(CommandHandler("notes", show_notes))
    dp.add_handler(CommandHandler("delete", delete_note))
    dp.add_handler(CommandHandler("broadcast", broadcast))

    # List of all commands and their functions
    command_list = {
        "gen": gen_command, "bin": bin_command, "check": check_command, "rand": rand_command,
        "ip": ip_lookup, "phone": phone_lookup, "whois": whois_lookup, "github": github_lookup, "imei": imei_lookup, "weather": weather, "myinfo": myinfo_command,
        "tr": tr, "yt": yt, "qr": qr, "short": short, "paste": paste, "tts": tts,
        "ping": ping, "uptime": uptime
    }

    for command, func in command_list.items():
        dp.add_handler(CommandHandler(command, func))

    logger.info("Starting Ultimate Bot polling on Render...")
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
