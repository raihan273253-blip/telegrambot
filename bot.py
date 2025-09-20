import logging
import requests
import json
import time
import random
from telegram.ext import Application, ContextTypes
from telegram.error import TelegramError
import asyncio
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

TOKEN = "8449140264:AAHM-FjFPzEyXNFkcG_bJedUJ8WDFdlTFBo"
CHANNEL_ID = "-1003040829067"

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

def load_state():
    try:
        with open("/home/yourusername/mysite/last_prediction.json", "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"Failed to load last_prediction.json: {e}")
        return {"period": None, "prediction": None, "timestamp": 0}

def save_state(state):
    try:
        with open("/home/yourusername/mysite/last_prediction.json", "w") as f:
            json.dump(state, f, indent=4)
        logger.info(f"Latest signal state saved: {state}")
    except IOError as e:
        logger.error(f"Failed to save file: {e}")

async def fetch_game_result():
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retries))
    try:
        ts = int(time.time() * 1000)
        headers = {"Cache-Control": "no-cache"}
        response = session.get(f"https://draw.ar-lottery01.com/WinGo/WinGo_1M/GetHistoryIssuePage.json?ts={ts}", headers=headers, timeout=5)
        response.raise_for_status()
        data = response.json()
        game_list = data.get("data", {}).get("list", [])
        if game_list:
            last_result_number = game_list[0].get("number")
            last_period = game_list[0].get("issueNumber")
            timestamp = game_list[0].get("time", int(time.time()))
            try:
                result_int = int(last_result_number)
                if result_int in [5, 6, 7, 8, 9]:
                    result_size = "Big"
                elif result_int in [0, 1, 2, 3, 4]:
                    result_size = "Small"
                else:
                    result_size = "Unknown"
                    logger.warning(f"Unknown result number: {last_result_number}")
                return {"period": last_period, "result": result_size, "timestamp": timestamp}
            except (ValueError, TypeError) as e:
                logger.error(f"Failed to process result number: {e}")
                return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch data from API: {e}")
        return None
    except (TypeError, ValueError, IndexError) as e:
        logger.error(f"Failed to process API data: {e}")
        return None

def generate_new_signal():
    prediction_size = random.choice(["Big", "Small"])
    confidence = random.randint(80, 99)
    return {"prediction": prediction_size, "confidence": confidence}

async def send_message_with_retry(bot, chat_id, text, max_retries=3):
    for attempt in range(max_retries):
        try:
            await bot.send_message(chat_id=chat_id, text=text)
            logger.info(f"Message sent successfully: {text[:50]}...")
            return
        except TelegramError as e:
            logger.error(f"Failed to send message (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
            else:
                logger.error("Max attempts reached, failed to send message.")

async def check_and_send_signal(context: ContextTypes.DEFAULT_TYPE):
    last_state = load_state()
    latest_game = await fetch_game_result()
    if latest_game:
        last_timestamp = last_state.get("timestamp", 0)
        current_timestamp = latest_game.get("timestamp", int(time.time()))
        if last_timestamp >= current_timestamp:
            logger.info("No new game data available, skipping signal.")
            return
        if last_state.get("period") and latest_game.get("period"):
            try:
                if int(last_state["period"]) == int(latest_game["period"]):
                    if last_state["prediction"] == latest_game["result"]:
                        result_message = (
                            f"Period: {latest_game['period']}\n"
                            "♻️ Result:- 💣WIN💣\n\n"
                            "Congratulations everyone, our signal has turned profitable."
                        )
                        await send_message_with_retry(context.bot, CHANNEL_ID, result_message)
                    else:
                        result_message = (
                            f"Period: {latest_game['period']}\n"
                            "♻️ Result:- 🥲LOSS🥲\n\n"
                            "Everyone follow the steps."
                        )
                        await send_message_with_retry(context.bot, CHANNEL_ID, result_message)
            except (ValueError, TypeError) as e:
                logger.error(f"Failed to compare periods: {e}")
        try:
            next_period = int(latest_game["period"]) + 1
        except (ValueError, TypeError) as e:
            logger.error(f"Failed to calculate next period: {e}")
            return
        new_signal = generate_new_signal()
        signal_message = (
            f"🎯 RAIHAN CHANNEL AI PREDICTION\n\n"
            f"🎮 Game: WinGo 1M\n"
            f"⏰ Period: {next_period}\n"
            f"🔮 Prediction: {new_signal['prediction']}\n"
            f"📈 Confidence: {new_signal['confidence']}% (random)\n"
            "♻️ Result: Pending.....\n\n"
            "Everyone will trade in 1 minute with Wingo in 7 steps."
        )
        await send_message_with_retry(context.bot, CHANNEL_ID, signal_message)
        save_state({"period": next_period, "prediction": new_signal['prediction'], "timestamp": current_timestamp})
    else:
        logger.warning("No data received from API, skipping signal for this period.")

async def main():
    logger.info("Bot starting...")
    application = Application.builder().token(TOKEN).build()
    job_queue = application.job_queue
    job_queue.run_repeating(check_and_send_signal, interval=30, first=5)
    await application.run_polling()
    logger.info("Bot is running and ready to send signals.")

if __name__ == "__main__":
    asyncio.run(main())
