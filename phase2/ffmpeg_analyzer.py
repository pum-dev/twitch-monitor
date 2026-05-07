import subprocess
import re
import time
import threading
from typing import Dict, Optional, Callable
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FFMpegAnalyzer:
    def __init__(self, stream_url: str):
        self.stream_url = stream_url
        self.process: Optional[subprocess.Popen] = None
        self.metrics: Dict[str, float] = {}
        self.running = False
        self.callback: Optional[Callable[[Dict[str, float]], None]] = None

    def start_analysis(self, callback: Callable[[Dict[str, float]], None] = None, interval: int = 5):
        """
        Inicia el análisis del stream con ffmpeg.
        
        Args:
            callback: Función a llamar cada 'interval' segundos con métricas
            interval: Segundos entre actualizaciones de métricas
        """
        self.callback = callback
        self.running = True
        
        # Comando ffmpeg para analizar sin reproducir
        cmd = [
            "ffmpeg",
            "-i", self.stream_url,
            "-f", "null",  # No output file
            "-stats",  # Mostrar estadísticas
            "-loglevel", "verbose",
            "-"
        ]
        
        try:
            logger.info(f"Iniciando análisis de {self.stream_url}")
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Thread para leer stderr en tiempo real
            threading.Thread(target=self._read_output, daemon=True).start()
            
            # Thread para actualizar métricas periódicamente
            threading.Thread(target=self._update_metrics_loop, args=(interval,), daemon=True).start()
            
        except Exception as e:
            logger.error(f"Error al iniciar ffmpeg: {e}")
            self.running = False

    def stop_analysis(self):
        """Detiene el análisis."""
        self.running = False
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
        logger.info("Análisis detenido")

    def _read_output(self):
        """Lee la salida de stderr de ffmpeg en tiempo real."""
        if not self.process:
            return
            
        while self.running and self.process.poll() is None:
            line = self.process.stderr.readline()
            if line:
                self._parse_line(line.strip())

    def _parse_line(self, line: str):
        """Parsea una línea de log de ffmpeg para extraer métricas."""
        # Ejemplos de líneas a parsear:
        # "frame=  123 fps= 30 q=0.0 size=     256kB time=00:00:04.10 bitrate= 512.3kbits/s"
        # "sync=0.050" (para A/V sync)
        
        # Bitrate
        bitrate_match = re.search(r'bitrate=\s*([\d.]+)kbits/s', line)
        if bitrate_match:
            self.metrics['bitrate_kbps'] = float(bitrate_match.group(1))
        
        # FPS
        fps_match = re.search(r'fps=\s*([\d.]+)', line)
        if fps_match:
            self.metrics['fps'] = float(fps_match.group(1))
        
        # Frame number (para detectar drops)
        frame_match = re.search(r'frame=\s*(\d+)', line)
        if frame_match:
            self.metrics['frame'] = int(frame_match.group(1))
        
        # A/V sync offset
        sync_match = re.search(r'sync=\s*([\d.-]+)', line)
        if sync_match:
            self.metrics['av_sync_offset'] = float(sync_match.group(1))
        
        # Timestamp
        self.metrics['timestamp'] = time.time()

    def _update_metrics_loop(self, interval: int):
        """Loop para llamar al callback con métricas actualizadas."""
        while self.running:
            time.sleep(interval)
            if self.callback and self.metrics:
                self.callback(self.metrics.copy())

    def get_current_metrics(self) -> Dict[str, float]:
        """Retorna las métricas actuales."""
        return self.metrics.copy()

def test_ffmpeg_analyzer():
    """Función de prueba."""
    # Asume que tienes una URL de stream (de stream_extractor)
    # Cambia por una URL real obtenida de stream_extractor
    stream_url = "https://eus21.playlist.ttvnw.net/v1/playlist/CtYEdTWjVYD82CfkxxZEQIUI6k5-2rYLelt5yrv1oE_dT61s5U_MQ5lcg-iqOzK-yOOI93PLhBYRsVLxUkJzXFELMYeLPCe3LsMCC-Nf1wvEd7KilmM6b87gNP7rHKVFKB1hSaEpt-jPvN-wXkHYlJ-dRh0OJ9Mbj9hfwrKRztaueStFblDQgdSnqguCW35bdz9h0XzyeoUb5czY7wVTT7nIK3-4Saw1dTxpum_s1iOUHhfzAvDIvUGRKSSakSNAC5bXV0K_GaHa5U462S3n_mcQhqlxdxQS9z6KuqNZztLaXk5hIwJM8Flmld88VP-gFRQRmTg7mdrxggmyWFr0ym7sR2lsUUO5d-PN3YiWlpXA0vYnNofaoXwFmbddp63BY1nMQMmHuJONb3mTTdbuzU4UPS_TEPVmiOfxP8AJhDdZ-Lf1vy0kSGNwfCUt-UG0fTYnfaPFD7pMG9JY1CsV9Ko0xed9xIpVmSxQESJV8e0onbQLBTdVu5BTCe9UvZ84b5s8gO6btgAYC712cpUt5J7d3xmKFsldCdV9p_V-WYpXYWNAUU-PA9Sr7ThQdW-vsQwtl9RKGOFTOmhXmnNH4j5UUS4d4DvRSZKs4UulpNgAveOfMpsCVt5tKnJlg1QH0DS9qn6flSLUxMxWde6pi1oI5Rgf7zODJaTH-LnukDGbY8y7TFEbul12L38kWXF80gidbPi2Jm-UluNfYWxhBCX-5NV7ZiWJV9LXQUB3TXW3deWhRLZr7INMcuGdX4E1l_vICoUcZOAq6ElCBLx8x0mG93xlLYw1RBoMMo7GLkJYKCb0_MHaIAEqCWV1LXdlc3QtMjCIDw.m3u8"  # Reemplaza con URL real

    analyzer = FFMpegAnalyzer(stream_url)
    
    def print_metrics(metrics):
        print(f"Métricas: {metrics}")
    
    analyzer.start_analysis(callback=print_metrics, interval=5)
    
    # Ejecuta por 30 segundos para probar
    time.sleep(30)
    analyzer.stop_analysis()

if __name__ == "__main__":
    test_ffmpeg_analyzer()