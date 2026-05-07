import subprocess
import logging
import time
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_stream_url(channel_name: str, quality: str = "best") -> Optional[str]:
    """
    Obtiene la URL del stream HLS de un canal de Twitch usando StreamLink.
    
    Args:
        channel_name: Nombre del canal (sin 'twitch.tv/')
        quality: Calidad deseada ('best', 'worst', '720p', etc.)
    
    Returns:
        URL del stream o None si falla
    """
    try:
        # Comando StreamLink para obtener la URL del stream
        cmd = [
            "streamlink",
            f"twitch.tv/{channel_name}",
            quality,
            "--stream-url"
        ]
        
        logger.info(f"Extrayendo stream para {channel_name}...")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10  # Timeout de 10 segundos
        )
        
        if result.returncode == 0 and result.stdout.strip():
            url = result.stdout.strip()
            logger.info(f"URL obtenida: {url}")
            return url
        else:
            logger.error(f"Error al extraer stream: {result.stderr}")
            return None
            
    except subprocess.TimeoutExpired:
        logger.error(f"Timeout al conectar a {channel_name}")
        return None
    except Exception as e:
        logger.error(f"Error inesperado: {e}")
        return None

def test_stream_extractor():
    """Función de prueba para verificar que funciona."""
    channel = "hitch"  # Canal de prueba (cambia por uno real)
    url = get_stream_url(channel)
    if url:
        print(f"✅ Stream URL para {channel}: {url}")
    else:
        print(f"❌ No se pudo obtener URL para {channel}")

if __name__ == "__main__":
    test_stream_extractor()