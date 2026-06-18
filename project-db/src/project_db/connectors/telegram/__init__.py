"""Telegram bot connector (pyTelegramBotAPI / telebot, synchronous).

One-shot long polling (``getUpdates`` with an offset cursor) to match the Gmail
poller's pull-when-ready model -- no always-on server, no public webhook needed.
"""
