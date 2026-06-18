import os
import json
import re
import logging
import requests
from ics import Calendar
import discord
import asyncio

# ==================== CONFIGURATION ====================
LMS_ICAL_URL = "https://lms.telkomuniversity.ac.id/calendar/export_execute.php?userid=114137&authtoken=dadb63bd4bf93b0c37c4f5f4e9b2d28497072502&preset_what=all&preset_time=recentupcoming"
DISCORD_CHANNEL_ID = 1284155200658997279
DB_FILE = "known_tasks.json"

# Mengambil token dari GitHub Secrets, BUKAN dari hardcode
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# ==================== LOGGING SETUP ====================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("LMS_Action")

# ==================== UTILITIES ========================
def load_known_events():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                return set(json.load(f))
        except Exception as e:
            logger.error(f"Failed to read database: {e}")
            return set()
    return set()

def save_known_events(events_set):
    try:
        with open(DB_FILE, "w") as f:
            json.dump(list(events_set), f)
    except Exception as e:
        logger.error(f"Failed to save database: {e}")

def clean_html(raw_html):
    if not raw_html:
        return "Tidak ada deskripsi atau catatan tambahan."
    clean_text = re.sub(r'<br\s*/?>', '\n', raw_html)
    clean_text = re.sub(r'<[^>]+>', '', clean_text)
    clean_text = clean_text.replace('&nbsp;', ' ').strip()
    return clean_text[:300] + "..." if len(clean_text) > 300 else clean_text

# ==================== CORE BOT LOGIC ===================
class LMSActionClient(discord.Client):
    async def on_ready(self):
        logger.info(f"Logged in as: {self.user.name}")
        await self.process_lms()
        # Sangat Penting: Tutup koneksi agar GitHub Actions mengakhiri proses dengan status 'Success'
        await self.close()

    async def process_lms(self):
        known_events = load_known_events()
        channel = self.get_channel(DISCORD_CHANNEL_ID)
        
        if not channel:
            logger.error(f"Channel ID {DISCORD_CHANNEL_ID} not found.")
            return

        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1'
            }
            response = requests.get(LMS_ICAL_URL, headers=headers, timeout=30)
            
            if response.status_code != 200:
                logger.error(f"LMS server returned HTTP {response.status_code}")
                return

            calendar = Calendar(response.text)
            is_first_run = len(known_events) == 0

            for event in calendar.events:
                event_id = event.uid if event.uid else f"{event.name}-{event.begin}"
                
                if event_id not in known_events:
                    known_events.add(event_id)
                    
                    if not is_first_run:
                        deadline_local = event.begin.to('Asia/Jakarta')
                        formatted_deadline = deadline_local.strftime('%A, %d %B %Y | %H:%M WIB')
                        clean_description = clean_html(event.description)
                        
                        embed = discord.Embed(
                            title="TUGAS / AGENDA BARU",
                            url="https://lms.telkomuniversity.ac.id/",
                            color=0xED1C24
                        )
                        embed.add_field(name="Judul Aktivitas", value=f"**{event.name}**", inline=False)
                        embed.add_field(name="Tenggat Waktu", value=f"`{formatted_deadline}`", inline=False)
                        embed.add_field(name="Deskripsi", value=f"```\n{clean_description}\n```", inline=False)
                        embed.set_footer(text="Sistem Monitoring CeLOE LMS")
                        embed.timestamp = discord.utils.utcnow()
                        
                        await channel.send(embed=embed)
                        await asyncio.sleep(1) # Hindari rate limit Discord API

            save_known_events(known_events)
            logger.info("Process completed successfully.")

        except Exception as e:
            logger.error(f"Execution error: {e}")

if __name__ == "__main__":
    if not DISCORD_BOT_TOKEN:
        logger.error("Token Discord tidak ditemukan di Environment Variables!")
        exit(1)
        
    intents = discord.Intents.default()
    client = LMSActionClient(intents=intents)
    client.run(DISCORD_BOT_TOKEN)
