import asyncio
import os
from typing import List, Dict, Optional

import aiohttp
from dotenv import load_dotenv

load_dotenv()

TWITCH_CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
TWITCH_CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")
TWITCH_CHANNELS = os.getenv("TWITCH_CHANNELS", "")
CHANNELS_FILE = os.path.join(os.path.dirname(__file__), "channels.txt")

TOKEN_URL = "https://id.twitch.tv/oauth2/token"
STREAMS_URL = "https://api.twitch.tv/helix/streams"
USERS_URL = "https://api.twitch.tv/helix/users"

async def get_app_access_token(session: aiohttp.ClientSession) -> str:
    payload = {
        "client_id": TWITCH_CLIENT_ID,
        "client_secret": TWITCH_CLIENT_SECRET,
        "grant_type": "client_credentials",
    }
    async with session.post(TOKEN_URL, params=payload) as resp:
        resp.raise_for_status()
        data = await resp.json()
        return data["access_token"]

async def get_user_ids(session: aiohttp.ClientSession, token: str, channels: List[str]) -> Dict[str, str]:
    headers = {
        "Client-ID": TWITCH_CLIENT_ID,
        "Authorization": f"Bearer {token}",
    }
    params = []
    for channel in channels:
        params.append(("login", channel.strip()))

    async with session.get(USERS_URL, headers=headers, params=params) as resp:
        resp.raise_for_status()
        data = await resp.json()

    return {user["login"].lower(): user["id"] for user in data.get("data", [])}

async def get_active_streams(session: aiohttp.ClientSession, token: str, user_ids: List[str]) -> Dict[str, dict]:
    if not user_ids:
        return {}

    headers = {
        "Client-ID": TWITCH_CLIENT_ID,
        "Authorization": f"Bearer {token}",
    }
    params = []
    for user_id in user_ids:
        params.append(("user_id", user_id))

    async with session.get(STREAMS_URL, headers=headers, params=params) as resp:
        resp.raise_for_status()
        data = await resp.json()

    return {stream["user_name"].lower(): stream for stream in data.get("data", [])}

def load_channels() -> List[str]:
    if TWITCH_CHANNELS:
        return [name.strip().lower() for name in TWITCH_CHANNELS.split(",") if name.strip()]

    if os.path.exists(CHANNELS_FILE):
        with open(CHANNELS_FILE, "r", encoding="utf-8") as f:
            return [line.strip().lower() for line in f if line.strip() and not line.startswith("#")]

    return []

async def main() -> None:
    if not TWITCH_CLIENT_ID or not TWITCH_CLIENT_SECRET:
        raise SystemExit("Por favor define TWITCH_CLIENT_ID y TWITCH_CLIENT_SECRET en el archivo .env")

    channels = load_channels()
    if not channels:
        raise SystemExit("No se han encontrado canales. Define TWITCH_CHANNELS o usa phase1/channels.txt")

    async with aiohttp.ClientSession() as session:
        token = await get_app_access_token(session)
        user_ids_map = await get_user_ids(session, token, channels)

        if not user_ids_map:
            print("No se pudieron obtener los IDs de usuario para los canales indicados.")
            return

        active_streams = await get_active_streams(session, token, list(user_ids_map.values()))

        print("Estado de canales Twitch:\n")
        for channel in channels:
            status = "offline"
            details = None
            if channel in user_ids_map:
                if channel in active_streams:
                    status = "online"
                    details = active_streams[channel]
            else:
                status = "sin usuario"

            print(f"- {channel}: {status}")
            if details:
                print(f"    Título: {details.get('title', 'N/A')}")
                print(f"    Juego: {details.get('game_name', 'N/A')}")
                print(f"    Viewers: {details.get('viewer_count', 'N/A')}")

if __name__ == "__main__":
    asyncio.run(main())
