import asyncio
import sys
import os
import json
import time
import logging
from typing import Dict, List
from datetime import datetime

from event_detector import EventDetector

# Importar módulos de Fase 1
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'phase1')))
from monitor import load_channels, get_app_access_token, get_user_ids, get_active_streams

# Importar módulos de Fase 2
from stream_extractor import get_stream_url
from ffmpeg_analyzer import FFMpegAnalyzer

import aiohttp
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class StreamMonitor:
    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.channels = load_channels()
        self.analyzers: Dict[str, FFMpegAnalyzer] = {}
        self.stream_states: Dict[str, dict] = {}
        self.event_detector = EventDetector()
        
        # Crear carpeta de logs si no existe
        os.makedirs("logs", exist_ok=True)

    async def check_streams(self, session):
        """Verifica estado de los canales vía API de Twitch."""
        token = await get_app_access_token(session)
        user_ids_map = await get_user_ids(session, token, self.channels)
        active_streams = await get_active_streams(session, token, list(user_ids_map.values()))
        
        return {
            "user_ids": user_ids_map,
            "active_streams": active_streams
        }

    def start_stream_analysis(self, channel: str):
        """Inicia análisis ffmpeg para un canal."""
        if channel in self.analyzers:
            logger.info(f"{channel} ya está siendo analizado")
            return
        
        stream_url = get_stream_url(channel)
        if not stream_url:
            logger.error(f"No se pudo obtener URL para {channel}")
            return
        
        analyzer = FFMpegAnalyzer(stream_url)
        
        def metrics_callback(metrics):
            self._log_metrics(channel, metrics)
        
        analyzer.start_analysis(callback=metrics_callback, interval=5)
        self.analyzers[channel] = analyzer
        logger.info(f"Análisis iniciado para {channel}")

    def stop_stream_analysis(self, channel: str):
        """Detiene análisis para un canal."""
        if channel in self.analyzers:
            self.analyzers[channel].stop_analysis()
            del self.analyzers[channel]
            logger.info(f"Análisis detenido para {channel}")

    def _log_metrics(self, channel: str, metrics: dict):
        is_online = channel in self.analyzers
        event = self.event_detector.process_metrics(channel, metrics, is_online=is_online)

        if event:
            print(f"\n🚨 EVENTO: {event['type']} en {channel}: {event['message']}")

        self.stream_states[channel] = {
            "timestamp": datetime.now().isoformat(),
            "metrics": metrics
        }

        with open("logs/stream_metrics.json", "a", encoding="utf-8") as f:
            log_entry = {
                "channel": channel,
                "timestamp": datetime.now().isoformat(),
                **metrics
            }
            f.write(json.dumps(log_entry) + "\n")
            
    async def monitor_loop(self, interval: int = 10):
        """Loop principal de monitorización."""
        async with aiohttp.ClientSession() as session:
            while True:
                try:
                    # Verificar estado vía API
                    stream_data = await self.check_streams(session)
                    active_streams = stream_data["active_streams"]
                    
                    print("\n=== Estado de Canales ===")
                    for channel in self.channels:
                        if channel in active_streams:
                            print(f"✅ {channel}: ONLINE")
                            # Iniciar análisis si está online
                            if channel not in self.analyzers:
                                self.start_stream_analysis(channel)
                        else:
                            print(f"❌ {channel}: OFFLINE")
                            # Detener análisis si está offline
                            if channel in self.analyzers:
                                self.stop_stream_analysis(channel)
                    
                    # Mostrar métricas actuales
                    if self.stream_states:
                        print("\n=== Métricas Actuales ===")
                        for channel, state in self.stream_states.items():
                            metrics = state.get("metrics", {})
                            print(f"{channel}: bitrate={metrics.get('bitrate_kbps', 'N/A')} kbps, fps={metrics.get('fps', 'N/A')}")
                    
                    await asyncio.sleep(interval)
                    
                except Exception as e:
                    logger.error(f"Error en monitor loop: {e}")
                    await asyncio.sleep(interval)

async def main():
    load_dotenv()
    
    client_id = os.getenv("TWITCH_CLIENT_ID")
    client_secret = os.getenv("TWITCH_CLIENT_SECRET")
    
    if not client_id or not client_secret:
        raise SystemExit("Define TWITCH_CLIENT_ID y TWITCH_CLIENT_SECRET en .env")
    
    monitor = StreamMonitor(client_id, client_secret)
    await monitor.monitor_loop()

if __name__ == "__main__":
    asyncio.run(main())