import os
import sys
import asyncio
import threading
import logging
from datetime import datetime
from tkinter import Tk, Frame, BOTH, X, LEFT, W
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

from dotenv import load_dotenv

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT_DIR, "phase2"))
sys.path.insert(0, os.path.join(ROOT_DIR, "phase1"))

from stream_monitor import StreamMonitor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DashboardApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Twitch Monitor Dashboard")
        self.root.geometry("980x640")

        self.load_configuration()
        self.monitor = StreamMonitor(self.client_id, self.client_secret)
        self.channels = self.monitor.channels
        self.tree_items = {}

        self.create_widgets()
        self.start_monitor_thread()
        self.update_loop()

    def load_configuration(self):
        load_dotenv(os.path.join(ROOT_DIR, ".env"))
        self.client_id = os.getenv("TWITCH_CLIENT_ID")
        self.client_secret = os.getenv("TWITCH_CLIENT_SECRET")
        if not self.client_id or not self.client_secret:
            raise SystemExit("Define TWITCH_CLIENT_ID y TWITCH_CLIENT_SECRET en .env")

    def create_widgets(self):
        self.main_frame = Frame(self.root)
        self.main_frame.pack(fill=BOTH, expand=True, padx=10, pady=10)

        self.table_frame = Frame(self.main_frame)
        self.table_frame.pack(fill=BOTH, expand=True)

        self.tree = ttk.Treeview(
            self.table_frame,
            columns=("channel", "status", "bitrate", "fps", "last_update"),
            show="headings",
            height=12,
        )
        self.tree.heading("channel", text="Canal")
        self.tree.heading("status", text="Estado")
        self.tree.heading("bitrate", text="Bitrate (kbps)")
        self.tree.heading("fps", text="FPS")
        self.tree.heading("last_update", text="Última actualización")

        self.tree.column("channel", width=180)
        self.tree.column("status", width=120)
        self.tree.column("bitrate", width=120)
        self.tree.column("fps", width=120)
        self.tree.column("last_update", width=280)

        self.tree.pack(fill=BOTH, expand=True, side=LEFT)

        for channel in self.channels:
            self.tree_items[channel] = self.tree.insert(
                "", "end", values=(channel, "OFFLINE", "N/A", "N/A", "N/A")
            )

        self.event_frame = Frame(self.main_frame)
        self.event_frame.pack(fill=BOTH, expand=True, pady=(10, 0))

        self.event_label = ttk.Label(self.event_frame, text="Últimos eventos")
        self.event_label.pack(anchor=W)

        self.event_text = ScrolledText(self.event_frame, height=14)
        self.event_text.pack(fill=BOTH, expand=True)
        self.event_text.configure(state="disabled")

        self.control_frame = Frame(self.root)
        self.control_frame.pack(fill=X, padx=10, pady=(0, 10))

        self.status_label = ttk.Label(self.control_frame, text="Iniciando monitor...")
        self.status_label.pack(side=LEFT)

    def start_monitor_thread(self):
        thread = threading.Thread(target=self.run_monitor_loop, daemon=True)
        thread.start()

    def run_monitor_loop(self):
        asyncio.run(self.monitor.monitor_loop(interval=10))

    def update_loop(self):
        self.refresh_table()
        self.refresh_events()
        self.root.after(2000, self.update_loop)

    def refresh_table(self):
        for channel in self.channels:
            item = self.tree_items[channel]
            state = self.monitor.stream_states.get(channel, {})
            metrics = state.get("metrics", {})
            status = "ONLINE" if channel in self.monitor.analyzers else "OFFLINE"
            bitrate = metrics.get("bitrate_kbps", "N/A")
            fps = metrics.get("fps", "N/A")
            last_update = state.get("timestamp", "N/A")
            self.tree.item(item, values=(channel, status, bitrate, fps, last_update))

        self.status_label.config(
            text=f"Monitoreando {len(self.channels)} canales · Analizando {len(self.monitor.analyzers)}"
        )

    def refresh_events(self):
    events_file = os.path.join(ROOT_DIR, "logs", "stream_events.json")
    print(f"Buscando archivo: {events_file}")  # Debug
    if not os.path.exists(events_file):
        print("Archivo no existe")  # Debug
        return

    try:
        with open(events_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        print(f"Líneas leídas: {len(lines)}")  # Debug
    except Exception as e:
        logger.error(f"No se pudo leer stream_events.json: {e}")
        return

    last_events = [line.strip() for line in lines[-20:]]
    print(f"Últimos eventos: {last_events}")  # Debug
    self.event_text.configure(state="normal")
    self.event_text.delete("1.0", "end")
    for entry in last_events:
        self.event_text.insert("end", entry + "\n")
    self.event_text.configure(state="disabled")
    print("Eventos insertados en UI")  # Debug


def main():
    root = Tk()
    DashboardApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()