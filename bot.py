#!/usr/bin/python3.8

import atexit
import os
import logging
import subprocess
import sys

from dotenv import load_dotenv
load_dotenv()

from helpers import Server
from telegram import ReplyKeyboardMarkup
from telegram import ReplyKeyboardRemove
from telegram.ext import ConversationHandler
from telegram.ext import CommandHandler
from telegram.ext import Filters
from telegram.ext import MessageHandler
from telegram.ext import Updater

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# -------- file descriptor ----------
#
# Locks the script while running
# atexit will delete the file on exit or crash 
# if the process gets killed, file will also be removed
#
# -----------------------------------

def clean_pid(pidfile):
    os.unlink(pidfile)

pid = str(os.getpid())
pidfile = "/tmp/wakky.lock"

if os.path.isfile(pidfile):
    with open(pidfile, 'r') as f:
        try:
            os.kill(int(f.readline()), 0)
        except OSError:
            logging.info(f"Process was killed, deleting {pidfile}")
            clean_pid(pidfile)
        else:
            logging.info(f"{pidfile} already exists, exiting")
            sys.exit()

with open(pidfile, 'w') as f:
    f.write(pid)

atexit.register(clean_pid, pidfile)

# wakky bot

updater = Updater(token=os.getenv("WAKKY_TELEGRAM_API_KEY"), use_context=True)
allowed_used_ids = set([int(allowed_id) for allowed_id in os.getenv('ALLOWED_USER_IDS').split(',') if allowed_id != ''])

def start(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text="Bruh")

def get_list_of_bots(update, context):
    user_data = context.user_data
    message = update.message
    wait_message = message.reply_text('Wait, we are getting your bot list from the server.')
    bot_list = Server.get_tasks_list(os.getenv('SERVER_USERNAME'))

    logging.info(f"Bot list: { bot_list }")

    if bot_list:
        keyboard = [[bot.command.split('/')[-2]] for bot in bot_list if 'Bot' in bot.command ]
        user_data['bots'] = { bot.command.split('/')[-2]: bot for bot in bot_list if 'Bot' in bot.command }

        if len(keyboard) > 0:
            context.bot.delete_message(chat_id=wait_message['chat']['id'], message_id=wait_message['message_id'])
            message.reply_text('Select a bot from the list', reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True))
            return Server.SELECT_TASK

        message.reply_text("There are no bots running")
        return ConversationHandler.END

def select_bot(update, context):
    user_data = context.user_data
    message = update.message
    bot_id  = user_data['bots'].get(message.text).id

    if not bot_id:
        message.reply_text("Something wrong sent")
        return ConversationHandler.END

    user_data['selected_bot_id']   = bot_id
    user_data['selected_bot_name'] = message.text

    logging.info(f"Selected bot: { bot_id }")
    
    keyboard = [["Restart", "Upload"], ["Cancel"]]
    message.reply_text('Select an option', reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True))
    
    return Server.SELECT_OPT

def restart_bot(update, context):
    user_data = context.user_data
    message   = update.message
    bot_id    = user_data['selected_bot_id']
    bot_name = user_data['selected_bot_name']

    # Resets the bot -> returns True on success else None 
    is_task_restarted = Server.restart_task(os.getenv('SERVER_USERNAME'), bot_id)

    logging.info(f"Selected option: { message.text }")

    if is_task_restarted:
        message.reply_text(f"[{bot_id}] {bot_name} restarted.", reply_markup=ReplyKeyboardRemove())

        del user_data['bots']
        del user_data['selected_bot_id']
        del user_data['selected_bot_name']
    else:
        message.reply_text(f"Something went wrong when trying to restart {bot_name}.", reply_markup=ReplyKeyboardRemove())

    return ConversationHandler.END

def upload_bot(update, context):
    user_data = context.user_data
    message = update.message
    command = user_data['bots'].get(user_data['selected_bot_name']).command
    botwd = command[command.find("/"):].rsplit("/",1)[0]

    logging.info(f"Selected option: { message.text }")
    logging.info(f"Current repository directory: { botwd }")

    if botwd:
        process = subprocess.run(["git", "pull"], cwd=botwd, stdout=-1)
        output = process.stdout.decode('utf-8').replace("\n", '')
        logging.info(output)
        message.reply_text(output, reply_markup=ReplyKeyboardRemove())
    else:
        message.reply_text("There's not a repository set for this bot", reply_markup=ReplyKeyboardRemove())

    del user_data['bots']
    del user_data['selected_bot_id']
    del user_data['selected_bot_name']

    return ConversationHandler.END

def cancel(update, context):
    user_data = context.user_data
    message = update.message

    logging.info(f"Selected option: { message.text }")

    message.reply_text("OK", reply_markup=ReplyKeyboardRemove())

    if 'bots' in user_data:
        del user_data['bots']
    if 'selected_bot_id' in user_data:
        del user_data['selected_bot_id']
    if 'selected_bot_name' in user_data:
        del user_data['selected_bot_name']

    return ConversationHandler.END

def not_allowed(update, context):
    update.message.reply_text("User not allowed", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

updater.dispatcher.add_handler(CommandHandler('start', start))

updater.dispatcher.add_handler(ConversationHandler(
    entry_points=[CommandHandler('bots', get_list_of_bots, Filters.user(allowed_used_ids))],

    states={
        Server.SELECT_TASK: [
            MessageHandler(Filters.text, select_bot)
        ],
        Server.SELECT_OPT: [
            MessageHandler(Filters.regex('^Restart$'), restart_bot),
            MessageHandler(Filters.regex('^Upload$'), upload_bot)
        ]
    },

    fallbacks=[MessageHandler(Filters.regex('^Cancel$'), cancel)]
))

updater.dispatcher.add_handler(MessageHandler(Filters.text, not_allowed))

updater.start_polling()
updater.idle()
    