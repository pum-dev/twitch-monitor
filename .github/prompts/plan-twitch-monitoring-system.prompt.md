# Plan: Monitorización Avanzada de Streams Twitch

## TL;DR
Expandir desde la Fase 1 (API polling básico) a un sistema completo de detección de problemas de stream (drops, buffering, calidad, A/V sync) usando StreamLink + ffmpeg, un dashboard de escritorio con alertas, y finalmente un dashboard web. Enfoque incremental: primero análisis sin UI, luego UI de escritorio, finalmente web.

**Decisiones clave:**
- Prioridad de detección: Stream drops > Buffering > Calidad video > Desincronización A/V
- MVP sin base de datos (logs en archivo)
- Dashboard desktop primero (Tkinter), luego web (Flask/React)
- Usar StreamLink para extraer HLS, ffmpeg para análisis de stream real

---

## Fase 1: Monitorización Básica (EXISTENTE)
**Estado:** ✓ Completado  
**Archivos:** `phase1/monitor.py`, `phase1/channels.txt`  
**Capacidades:** 
- Autenticación OAuth en Twitch API
- Polling cada N segundos sobre estado online/offline
- Salida en consola

---

## Fase 2: Detección de Problemas de Stream (Core Metrics)
**Objetivo:** Agregar análisis real del stream usando StreamLink + ffmpeg para detectar drops, buffering, calidad y sincronización.

### Paso 1: Módulo de extracción de stream (StreamLink)
- Crear `phase2/stream_extractor.py`:
  - Función `get_stream_url(channel_name)` que obtiene la mejor calidad HLS vía StreamLink
  - Manejo de reintentos y timeouts
  - Logging de errores de conexión

### Paso 2: Módulo de análisis con ffmpeg (*depends on Paso 1*)
- Crear `phase2/ffmpeg_analyzer.py`:
  - Subprocess ffmpeg con `-stats` y `-loglevel verbose`
  - Parsear salida en tiempo real:
    - **Stream drops**: detección de frame loss, packets perdidos
    - **Buffering**: cambios bruscos en bitrate real vs esperado
    - **Calidad**: monitorear bitrate, FPS, resolución real entregados
    - **A/V sync**: parsear `sync=X` en logs ffmpeg
  - Retornar diccionario de métricas cada N segundos

### Paso 3: Módulo de monitor extendido (*parallel with Paso 2*)
- Crear `phase2/stream_monitor.py`:
  - Combinar Fase 1 (API de Twitch) + análisis ffmpeg
  - Para cada canal:
    - Primero verificar online/offline vía API
    - Si online, conectar ffmpeg + StreamLink para métricas detalladas
    - Si offline, registrar como "stream_drop"
  - Guardar estado en estructura local (dict + JSON)

### Paso 4: Sistema de detección de eventos (*depends on Paso 3*)
- Crear `phase2/event_detector.py`:
  - Máquina de estados por canal (offline → online, quality_degraded, buffering_detected, etc.)
  - Generar eventos cuando:
    - Transición offline → online (nuevamente en vivo)
    - Offline prolongado > threshold (ej. 5 min)
    - Bitrate cae > 30% vs promedio
    - Frame loss > 5%
    - Sincronización A/V > 500ms
  - Guardar eventos en `logs/stream_events.json` con timestamp

### Paso 5: Actualizar requirements.txt (*parallel with Paso 4*)
- Agregar: `streamlink`, `ffmpeg-python` (o usar subprocess directo)

---

## Fase 3: Dashboard de Escritorio (Tkinter)
**Objetivo:** UI local con visualización de estado en tiempo real y alertas.

### Paso 1: Interfaz principal (*depends on Fase 2 Paso 4*)
- Crear `phase3/dashboard.py` (Tkinter):
  - Ventana principal con tabla de canales
  - Columnas: Nombre | Estado (online/offline) | Bitrate | FPS | Última alerta
  - Actualización en tiempo real (cada 1-2 seg)

### Paso 2: Panel de alertas y eventos (*parallel*)
- Área de "Recent Events" mostrando últimas 10 alertas
- Color rojo para críticas (stream drop), naranja para degradación
- Logs en sidebar desplegable

### Paso 3: Reproducción embebida (*depends on Paso 1*)
- Integrar reproductor ffplay o VLC (vía python-vlc)
- Mostrar preview del stream seleccionado
- Datos de bitrate/FPS en overlay

### Paso 4: Control y configuración (*parallel*)
- Botones: Pausar/reanudar monitoreo, agregar/quitar canal
- Panel de configuración: thresholds de alertas, intervalos de polling

---

## Fase 4: Backend + API REST
**Objetivo:** Persistencia y exposición de datos para dashboard web.

### Paso 1: API REST con Flask (*depends on Fase 2 Paso 4*)
- Crear `phase4/api.py`:
  - Endpoint `GET /channels` → lista de canales con estado actual
  - Endpoint `GET /events` → histórico de últimas N alertas
  - Endpoint `GET /metrics/:channel` → métricas en tiempo real del canal
  - Endpoint `POST /alerts/config` → actualizar thresholds

### Paso 2: Persistencia mejorada (*depends on Paso 1*)
- Cambiar de logs JSON simples a SQLite (o PostgreSQL si escalable)
- Crear `phase4/db.py`:
  - Tabla `streams` (channel, last_status, last_check)
  - Tabla `events` (channel, type, severity, timestamp, details)
  - Tabla `metrics` (channel, timestamp, bitrate, fps, sync_offset)

### Paso 3: Servir archivos estáticos (*parallel*)
- Crear carpeta `phase4/static/` para dashboard web
- Configurar Flask para servirla

---

## Fase 5: Dashboard Web (React/Vue)
**Objetivo:** Interfaz moderna y accesible desde navegador.

### Paso 1: Setup frontend (*depends on Fase 4 Paso 1*)
- Crear `phase5/frontend/`:
  - React app con Vite/CRA
  - Conexión a API de Fase 4
  - Fetch cada 2 seg desde `/channels` y `/events`

### Paso 2: Componentes principales
- **StreamList**: Tabla con estado de cada canal, click para detalles
- **StreamDetail**: Gráfica de bitrate/FPS en tiempo real (Chart.js)
- **AlertPanel**: Feed en vivo de eventos
- **SettingsPanel**: Ajuste de umbrales (POST a `/alerts/config`)

### Paso 3: Visualización y UX
- Colores por severidad (rojo=crítico, naranja=warning)
- Gráficas de histórico (últimas 24h)
- Notificaciones del navegador si stream cae

---

## Archivos clave a crear/modificar

### Estructura final:
```
twitch-monitor/
├── phase1/              ✓ (existente)
│   ├── monitor.py
│   └── channels.txt
├── phase2/              ✓ (análisis de stream)
│   ├── stream_extractor.py
│   ├── ffmpeg_analyzer.py
│   ├── stream_monitor.py
│   ├── event_detector.py
│   └── utils.py (helpers comunes)
├── phase3/              ✓ (dashboard desktop)
│   ├── dashboard.py
│   ├── ui/
│   │   ├── main_window.py
│   │   ├── alerts_panel.py
│   │   └── player_widget.py
├── phase4/              ← Crear (API + persistencia)
│   ├── api.py
│   ├── db.py
│   ├── models.py
├── phase5/              ← Crear (dashboard web)
│   ├── frontend/ (React app)
│   └── static/ (built assets)
├── logs/                ✓ (eventos JSON)
├── requirements.txt     ← Actualizar (StreamLink, ffmpeg-python, flask, etc.)
├── .env.example
└── README.md
```

### Archivos críticos por fase:
- **Fase 2**: `phase2/ffmpeg_analyzer.py` (corazón del análisis) ✓
- **Fase 3**: `phase3/dashboard.py` (UI threading + update loop) ✓
- **Fase 4**: `phase4/db.py` (schema y queries)
- **Fase 5**: `phase5/frontend/src/App.jsx` (conexión a API)

---

## Verificación de implementación

### Fase 2: ✅ COMPLETADA
- ✅ Ejecutar `python phase2/stream_monitor.py` → conecta a stream en vivo y muestra bitrate/FPS en consola
- ✅ Genera eventos en `logs/stream_events.json` cuando detecta problemas
- ✅ ffmpeg funciona y parsea métricas correctamente

### Fase 3: ✅ EN PROGRESO (DASHBOARD FUNCIONAL)
- ✅ Lanzar `python phase3/dashboard.py` → ventana Tkinter abre con tabla de canales
- ✅ Estado actualiza en tiempo real (cada 2 seg)
- ⚠️ Eventos muestran si hay contenido en stream_events.json
- ⚪ Click en canal reproduce preview (pendiente)
- ⚪ Panel de colores según severidad (pendiente)

### Fase 4: ← SIGUIENTE
- ⚪ `python phase4/api.py` → servidor Flask en puerto 5000
- ⚪ `curl http://localhost:5000/channels` → devuelve JSON con estado
- ⚪ Base de datos SQLite con histórico

### Fase 5: ← POSTERIOR
- ⚪ `npm run dev` en `phase5/frontend/` → React app en localhost:3000
- ⚪ Tabla de canales renderiza desde API
- ⚪ Gráficas de bitrate/FPS con histórico

---

## Decisiones y exclusiones

**Incluido:**
- Detección de stream drops vía análisis ffmpeg (frame loss, packet loss)
- Buffering detectado por varianza en bitrate real-time
- Calidad de video via bitrate/FPS
- Sincronización A/V via logs de ffmpeg
- Dashboard de escritorio con eventos
- Escalable a web posterior

**Excluido (Fase 0 o futura):**
- Machine Learning para predicción de drops
- Integración EventSub de Twitch (notificaciones push nativas)
- Escalado horizontal/cluster (MVP local)
- Soporte para múltiples usuarios/bases de datos remota
- Análisis de contenido (OCR, detección de escenas)

**Asunciones:**
- ffmpeg instalado en sistema ✓
- Python 3.9+ ✓
- Twitch API access tokens actualizados y válidos ✓
- StreamLink instalado ✓

---

## Próximas consideraciones

1. **Thresholds adaptativos**: En Fase 4, ¿agregar calibración automática de thresholds? (ej. bitrate promedio varía por hora del día)
2. **Integración EventSub**: En Fase 4, ¿agregar WebSocket de Twitch para alertas nativas + análisis ffmpeg combinado?
3. **Análisis de calidad avanzado**: En Fase 5, ¿detectar cambios de resolución/codec en la mitad de un stream?
4. **Reproductor embebido**: Integrar ffplay o VLC en dashboard para previsualización
5. **Controles dinámicos**: Botones para pausar/reanudar monitoreo y agregar/quitar canales en tiempo real

---

## Métricas Futuras (Fases 4/5)

**Métricas actuales (Fase 2):** bitrate_kbps, fps, frame, av_sync_offset, timestamp ✓

**Métricas a agregar en Fase 4/5:**
- Resolución real (width x height)
- GOP size (tamaño de keyframe)
- Packet loss detectado
- Duración del buffer acumulado
- Análisis de escenas/cambios de contenido
- Detección de freezes (frames consecutivos idénticos)
- Codec detectado (H.264, VP9, etc.)
- Varianza de bitrate (para buffering más preciso)

**Nota:** Usar para mejorar dashboard y alertas más granulares.
