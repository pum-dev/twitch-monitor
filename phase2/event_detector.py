import json
import logging
from typing import Dict, List, Optional
from datetime import datetime
from enum import Enum

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class StreamState(Enum):
    """Estados posibles de un stream."""
    OFFLINE = "offline"
    ONLINE = "online"
    DEGRADED = "degraded"  # Calidad baja
    BUFFERING = "buffering"  # Bitrate inestable
    SYNC_ISSUE = "sync_issue"  # Desincronización A/V
    FRAME_LOSS = "frame_loss"  # Pérdida de frames

class AlertSeverity(Enum):
    """Severidad de alertas."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

class EventDetector:
    """
    Detecta eventos críticos en streams basado en máquina de estados.
    """
    
    def __init__(self, events_log_path: str = "logs/stream_events.json"):
        self.events_log_path = events_log_path
        self.channel_states: Dict[str, StreamState] = {}
        self.channel_metrics_history: Dict[str, List[dict]] = {}
        self.last_frame_count: Dict[str, int] = {}
        
        # Umbrales configurables
        self.thresholds = {
            "bitrate_drop_percent": 30,  # 30% caída = alerta
            "frame_loss_percent": 5,  # >5% frame loss = alerta
            "av_sync_offset_ms": 500,  # >500ms desincronización = alerta
            "low_bitrate_kbps": 2000,  # < 2000 kbps = calidad baja
            "low_fps": 24,  # < 24 fps = problema
            "offline_duration_sec": 300,  # 5 min offline = alerta
        }

    def process_metrics(self, channel: str, metrics: dict, is_online: bool) -> Optional[dict]:
        """
        Procesa métricas de un canal y detecta eventos.
        
        Args:
            channel: Nombre del canal
            metrics: Dict con bitrate_kbps, fps, av_sync_offset, etc.
            is_online: Si el canal está online según API de Twitch
        
        Returns:
            Evento generado (si hay) o None
        """
        event = None
        
        # Inicializar historial si no existe
        if channel not in self.channel_metrics_history:
            self.channel_metrics_history[channel] = []
        if channel not in self.channel_states:
            self.channel_states[channel] = StreamState.OFFLINE
        
        # --- DETECCIÓN: Stream offline/online ---
        current_state = self.channel_states[channel]
        
        if is_online and current_state == StreamState.OFFLINE:
            event = self._create_event(
                channel, 
                "stream_online", 
                AlertSeverity.INFO,
                "Stream vuelto online"
            )
            self.channel_states[channel] = StreamState.ONLINE
            self.channel_metrics_history[channel] = []  # Reset historial
            self.last_frame_count[channel] = metrics.get('frame', 0)
        
        elif not is_online and current_state != StreamState.OFFLINE:
            event = self._create_event(
                channel,
                "stream_offline",
                AlertSeverity.CRITICAL,
                "Stream caído"
            )
            self.channel_states[channel] = StreamState.OFFLINE
            # Detener análisis aquí (llamada externa)
        
        # Si está offline, no analizar más métricas
        if not is_online:
            if event:
                self._save_event(event)
            return event
        
        # --- Agregar a historial ---
        self.channel_metrics_history[channel].append({
            "timestamp": datetime.now().isoformat(),
            **metrics
        })
        
        # Mantener solo últimas 20 muestras
        if len(self.channel_metrics_history[channel]) > 20:
            self.channel_metrics_history[channel].pop(0)
        
        # --- DETECCIÓN: Frame loss (drop de frames) ---
        frame_loss = self._detect_frame_loss(channel, metrics)
        if frame_loss and frame_loss > self.thresholds["frame_loss_percent"]:
            event = self._create_event(
                channel,
                "frame_loss_detected",
                AlertSeverity.CRITICAL,
                f"Pérdida de frames: {frame_loss:.1f}%"
            )
            self.channel_states[channel] = StreamState.FRAME_LOSS
        
        # --- DETECCIÓN: Desincronización A/V ---
        av_sync = metrics.get('av_sync_offset', 0)
        if abs(av_sync) > self.thresholds["av_sync_offset_ms"] / 1000:
            event = self._create_event(
                channel,
                "av_sync_issue",
                AlertSeverity.WARNING,
                f"Desincronización A/V: {av_sync:.3f}s"
            )
            self.channel_states[channel] = StreamState.SYNC_ISSUE
        
        # --- DETECCIÓN: Bitrate degradado (buffering) ---
        bitrate_drop = self._detect_bitrate_drop(channel, metrics)
        if bitrate_drop and bitrate_drop > self.thresholds["bitrate_drop_percent"]:
            event = self._create_event(
                channel,
                "bitrate_drop",
                AlertSeverity.WARNING,
                f"Caída de bitrate: {bitrate_drop:.1f}%"
            )
            self.channel_states[channel] = StreamState.BUFFERING
        
        # --- DETECCIÓN: Calidad baja ---
        bitrate = metrics.get('bitrate_kbps', 0)
        fps = metrics.get('fps', 0)
        if bitrate < self.thresholds["low_bitrate_kbps"] and fps < self.thresholds["low_fps"]:
            event = self._create_event(
                channel,
                "quality_degraded",
                AlertSeverity.WARNING,
                f"Calidad baja: {bitrate:.0f} kbps @ {fps:.0f} fps"
            )
            self.channel_states[channel] = StreamState.DEGRADED
        
        # Si la métrica mejoró, volver a ONLINE
        if (event is None and 
            current_state != StreamState.ONLINE and 
            bitrate > self.thresholds["low_bitrate_kbps"] and
            fps > self.thresholds["low_fps"] and
            frame_loss is None):
            self.channel_states[channel] = StreamState.ONLINE
        
        # Registrar evento si hay
        if event:
            self._save_event(event)
        
        return event

    def _detect_frame_loss(self, channel: str, metrics: dict) -> Optional[float]:
        """Detecta pérdida de frames."""
        if channel not in self.last_frame_count:
            self.last_frame_count[channel] = metrics.get('frame', 0)
            return None
        
        current_frame = metrics.get('frame', 0)
        expected_fps = metrics.get('fps', 30)
        
        if current_frame == self.last_frame_count[channel]:
            # No hay avance de frames = pérdida
            return 100.0
        
        self.last_frame_count[channel] = current_frame
        return None  # Sin pérdida detectada

    def _detect_bitrate_drop(self, channel: str, metrics: dict) -> Optional[float]:
        """Detecta caída de bitrate comparando con promedio reciente."""
        if len(self.channel_metrics_history[channel]) < 5:
            return None
        
        history = self.channel_metrics_history[channel]
        current_bitrate = metrics.get('bitrate_kbps', 0)
        avg_bitrate = sum(m.get('bitrate_kbps', 0) for m in history[:-1]) / len(history[:-1])
        
        if avg_bitrate == 0:
            return None
        
        drop_percent = ((avg_bitrate - current_bitrate) / avg_bitrate) * 100
        return drop_percent if drop_percent > 0 else None

    def _create_event(self, channel: str, event_type: str, severity: AlertSeverity, message: str) -> dict:
        """Crea un evento con timestamp."""
        return {
            "timestamp": datetime.now().isoformat(),
            "channel": channel,
            "type": event_type,
            "severity": severity.value,
            "message": message
        }

    def _save_event(self, event: dict):
        """Guarda evento en archivo JSON."""
        try:
            with open(self.events_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(event) + "\n")
            logger.info(f"Evento guardado: {event['channel']} - {event['type']}")
        except Exception as e:
            logger.error(f"Error guardando evento: {e}")

    def get_current_state(self, channel: str) -> StreamState:
        """Retorna estado actual del canal."""
        return self.channel_states.get(channel, StreamState.OFFLINE)

    def update_thresholds(self, new_thresholds: dict):
        """Actualiza umbrales dinámicamente."""
        self.thresholds.update(new_thresholds)
        logger.info(f"Umbrales actualizados: {self.thresholds}")