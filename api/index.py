import os
import openai
import requests
import datetime
import asyncio

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.ext import defaults
from telegram.ext import ApplicationBuilder

from dotenv import load_dotenv
load_dotenv()

# ENV VARS
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
EXA_API_KEY = os.getenv("EXA_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

# Init FastAPI
app = FastAPI()

@app.get("/", response_class=HTMLResponse)
async def root():
    return """
    <html>
        <head><title>Bot Status</title></head>
        <body style="text-align:center; margin-top:20%;">
            <h1>🤖 Telegram Bot is Running</h1>
            <p>Ask anything on Telegram and get summarized search results.</p>
            <p>Owner: <a href="https://t.me/waspros">@waspros</a></p>
        </body>
    </html>
    """

# ====== BOT SETUP ======

class SearchResult:
    def __init__(self, title: str, url: str, snippet: str):
        self.title = title
        self.url = url
        self.snippet = snippet

# In-memory cache
search_cache = {}

async def exa_search(query: str):
    if query in search_cache:
        return search_cache[query]
    url = "https://api.exa.ai/search"
    headers = {"Authorization": f"Bearer {EXA_API_KEY}"}
    params = {"q": query, "num_results": 5}
    response = requests.get(url, headers=headers, params=params)
    results = response.json().get("results", [])
    parsed = [SearchResult(r["title"], r["url"], r["text"]) for r in results]
    search_cache[query] = parsed
    return parsed

async def summarize(query: str, results):
    sources = "\n\n".join(f"{r.title}: {r.snippet[:400]}" for r in results)
    prompt = f"Summarize the following for: '{query}'\n\n{sources}"
    response = await openai.ChatCompletion.acreate(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "user", "content": prompt}
        ],
        max_tokens=800
    )
    return response.choices[0].message.content.strip()

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    await update.message.reply_text("🔍 Searching...")
    results = await asyncio.to_thread(lambda: asyncio.run(exa_search(query)))
    summary = await summarize(query, results)
    sources_text = "\n".join(f"• [{r.title}]({r.url})" for r in results)
    final_msg = f"*Summary:*\n{summary}\n\n*Sources:*\n{sources_text}"
    await update.message.reply_text(final_msg, parse_mode="Markdown", disable_web_page_preview=True)

# Run bot in background
def start_bot():
    app_bot = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    asyncio.create_task(app_bot.initialize())
    asyncio.create_task(app_bot.start())
    return app_bot

bot_app = start_bot()
