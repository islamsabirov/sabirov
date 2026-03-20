import os

BOT_TOKEN   = os.environ.get("BOT_TOKEN", "")
ADMIN_IDS   = list(map(int, os.environ.get("ADMIN_IDS", "5907118746").split(",")))
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")
PORT        = int(os.environ.get("PORT", 10000))
MOVIE_CH    = os.environ.get("MOVIE_CH", "")
