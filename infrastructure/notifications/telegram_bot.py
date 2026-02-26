import asyncio
import aiohttp
from typing import Optional
from config.settings import TelegramConfig
from utils.logger import get_logger

logger = get_logger(__name__)

class TelegramBot:
    """Telegram Bot for Push Notifications and Remote Control."""
    
    def __init__(self, config: TelegramConfig):
        self.config = config
        self.base_url = f"https://api.telegram.org/bot{self.config.bot_token}"
        self.is_listening = False
        self.last_update_id = 0
        self.stop_callback = None

    async def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """Send a message to the configured chat."""
        if not self.config.enable_notifications or not self.config.bot_token or not self.config.chat_id:
            return False

        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "chat_id": self.config.chat_id,
                    "text": text,
                    "parse_mode": parse_mode
                }
                async with session.post(f"{self.base_url}/sendMessage", json=payload) as response:
                    if response.status == 200:
                        return True
                    else:
                        resp_text = await response.text()
                        logger.error(f"❌ Telegram API Error: {response.status} - {resp_text}")
                        return False
        except Exception as e:
            logger.error(f"❌ Failed to send Telegram message: {e}")
            return False

    def register_stop_callback(self, callback):
        """Register a callback function when /stop is received."""
        self.stop_callback = callback

    async def start_listening(self):
        """Start polling for commands like /stop."""
        if not self.config.enable_notifications or not self.config.bot_token:
            return

        self.is_listening = True
        logger.info("📡 Telegram Bot is listening for commands...")
        
        while self.is_listening:
            try:
                async with aiohttp.ClientSession() as session:
                    params = {"offset": self.last_update_id + 1, "timeout": 30}
                    async with session.get(f"{self.base_url}/getUpdates", params=params, timeout=35) as response:
                        if response.status == 200:
                            data = await response.json()
                            if data.get("ok"):
                                for update in data.get("result", []):
                                    self.last_update_id = update["update_id"]
                                    await self._process_update(update)
            except asyncio.CancelledError:
                self.is_listening = False
                break
            except Exception as e:
                logger.debug(f"⚠️ Telegram polling error (non-fatal): {e}")
                await asyncio.sleep(5) # backoff

    async def _process_update(self, update: dict):
        """Process incoming messages."""
        message = update.get("message", {})
        text = message.get("text", "")
        
        if text.startswith("/stop"):
            logger.warning("🛑 Received /stop command from Telegram!")
            if self.stop_callback:
                await self.send_message("🛑 Received KILL SWITCH command. Shutting down Bot safely...")
                self.stop_callback()

    async def close(self):
        """Stop listening."""
        self.is_listening = False
