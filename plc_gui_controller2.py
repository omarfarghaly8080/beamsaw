"""
Beam Saw PLC Controller - Snap7 S7 Communication
------------------------------------------------
Connects to a Siemens S7-1200 CPU via Snap7 (TCP Port 102).

Each command button/typed command sends a PULSE: write True, hold briefly,
then auto-write False. This mimics a real push-button press, so the PLC's
own Set/Reset (S/R) ladder logic is what actually latches/unlatches the
output -- not the PC staying connected.

Ladder logic required in Main (OB1):
    Network 1: DB1.DBX0.0 (NO contact) -> S coil -> Q0.0
    Network 2: DB1.DBX0.1 (NO contact) -> R coil -> Q0.0
"""

import tkinter as tk
from tkinter import scrolledtext
import snap7
from snap7.util import set_bool
import threading
import queue
import time

# ---------------- CONFIGURATION ----------------
PLC_IP = "192.168.0.1"   # S7-1200 IP Address
RACK = 0                 # Always 0 for S7-1200
SLOT = 1                 # Always 1 for S7-1200 CPU

DB_NUMBER = 1            # DB_Saw is DB1

# Offsets inside DB_Saw (Byte, Bit)
TAG_OFFSETS = {
    "start_cut":   (0, 0),  # DB1.DBX0.0
    "stop":        (0, 1),  # DB1.DBX0.1
    "estop_reset": (0, 2),  # DB1.DBX0.2
}

PULSE_HOLD_SECONDS = 0.2  # how long the bit stays True before auto-reset
# -----------------------------------------------


class Snap7PLC:
    """Handles S7 Protocol communication with Siemens S7-1200."""
    def __init__(self):
        self.client = snap7.client.Client()
        self.connected = False

    def connect(self, ip, rack=0, slot=1):
        self.client.connect(ip, rack, slot)
        self.connected = self.client.get_connected()

    def disconnect(self):
        if self.connected:
            try:
                self.client.disconnect()
            except Exception:
                pass
        self.connected = False

    def write_bool(self, db_number, byte_index, bit_index, value: bool):
        if not self.connected:
            raise ConnectionError("Not connected to PLC.")

        # 1. Read current byte state from PLC memory
        data = self.client.db_read(db_number, byte_index, 1)

        # 2. Modify specific bit in byte array
        set_bool(data, 0, bit_index, value)

        # 3. Write modified byte back to PLC
        self.client.db_write(db_number, byte_index, data)


class App:
    """Tkinter Graphical User Interface for Beam Saw operations."""
    def __init__(self, root):
        self.root = root
        self.root.title("Beam Saw Controller (Snap7 S7 Comm)")
        self.plc = Snap7PLC()
        self.ui_queue = queue.Queue()

        # --- Connection Bar ---
        conn_frame = tk.Frame(root)
        conn_frame.pack(padx=10, pady=10, fill="x")

        tk.Label(conn_frame, text="PLC IP:").grid(row=0, column=0, sticky="w")
        self.ip_entry = tk.Entry(conn_frame, width=15)
        self.ip_entry.insert(0, PLC_IP)
        self.ip_entry.grid(row=0, column=1, padx=5)

        self.connect_btn = tk.Button(conn_frame, text="Connect", command=self.connect)
        self.connect_btn.grid(row=0, column=2, padx=5)

        self.disconnect_btn = tk.Button(conn_frame, text="Disconnect", command=self.disconnect)
        self.disconnect_btn.grid(row=0, column=3, padx=5)

        self.status_label = tk.Label(conn_frame, text="Status: Disconnected", fg="red", font=("Arial", 10, "bold"))
        self.status_label.grid(row=0, column=4, padx=10)

        # --- Quick Action Buttons ---
        btn_frame = tk.Frame(root)
        btn_frame.pack(padx=10, pady=5, fill="x")

        tk.Button(btn_frame, text="Start Cut", width=12, bg="#e1f5fe",
                  command=lambda: self.send_command("start_cut")).grid(row=0, column=0, padx=5)
        tk.Button(btn_frame, text="Stop", width=12, bg="#ffebee",
                  command=lambda: self.send_command("stop")).grid(row=0, column=1, padx=5)
        tk.Button(btn_frame, text="Reset E-Stop", width=12, bg="#f3e5f5",
                  command=lambda: self.send_command("estop_reset")).grid(row=0, column=2, padx=5)

        # --- Command Line Entry ---
        type_frame = tk.Frame(root)
        type_frame.pack(padx=10, pady=5, fill="x")

        tk.Label(type_frame, text="Command Entry:").pack(side="left")
        self.cmd_entry = tk.Entry(type_frame, width=30)
        self.cmd_entry.pack(side="left", padx=5)
        self.cmd_entry.bind("<Return>", self.handle_typed_command)
        tk.Button(type_frame, text="Send", command=self.handle_typed_command).pack(side="left")

        # --- Activity Log ---
        self.log = scrolledtext.ScrolledText(root, width=65, height=15, state="disabled")
        self.log.pack(padx=10, pady=10)

        self.log_msg("Snap7 Ready. Click Connect.")
        self.root.after(100, self.process_queue)

    def process_queue(self):
        try:
            while True:
                func = self.ui_queue.get_nowait()
                func()
        except queue.Empty:
            pass
        self.root.after(100, self.process_queue)

    def log_msg(self, msg):
        def _update():
            self.log.config(state="normal")
            self.log.insert(tk.END, msg + "\n")
            self.log.see(tk.END)
            self.log.config(state="disabled")
        self.ui_queue.put(_update)

    def set_status(self, text, color):
        def _update():
            self.status_label.config(text=text, fg=color)
        self.ui_queue.put(_update)

    def connect(self):
        ip = self.ip_entry.get().strip()

        def worker():
            try:
                self.log_msg(f"Connecting via Snap7 to {ip} (Rack {RACK}, Slot {SLOT})...")
                self.plc.connect(ip, RACK, SLOT)
                self.set_status("Status: Connected", "green")
                self.log_msg(f"Connected to S7-1200 at {ip}!")
            except Exception as e:
                self.set_status("Status: Disconnected", "red")
                self.log_msg(f"Connection failed: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def disconnect(self):
        def worker():
            self.plc.disconnect()
            self.set_status("Status: Disconnected", "red")
            self.log_msg("Disconnected from PLC.")

        threading.Thread(target=worker, daemon=True).start()

    def send_command(self, key):
        """Pulses the given tag: writes True, holds briefly, then writes False.
        This mimics a momentary push-button -- the PLC's own S/R logic is
        what actually keeps the output latched afterward."""
        if key not in TAG_OFFSETS:
            self.log_msg(f"Unknown tag: '{key}'")
            return

        byte_idx, bit_idx = TAG_OFFSETS[key]

        def worker():
            try:
                self.plc.write_bool(DB_NUMBER, byte_idx, bit_idx, True)
                self.log_msg(f"SUCCESS -> Pulsed DB{DB_NUMBER}.DBX{byte_idx}.{bit_idx} ({key}) = True")

                time.sleep(PULSE_HOLD_SECONDS)

                self.plc.write_bool(DB_NUMBER, byte_idx, bit_idx, False)
                self.log_msg(f"SUCCESS -> Released DB{DB_NUMBER}.DBX{byte_idx}.{bit_idx} ({key}) = False")
            except Exception as e:
                self.log_msg(f"WRITE FAILED for '{key}': {e}")

        threading.Thread(target=worker, daemon=True).start()

    def handle_typed_command(self, event=None):
        text = self.cmd_entry.get().strip().lower()
        self.cmd_entry.delete(0, tk.END)
        if not text:
            return

        mapping = {
            "start": "start_cut",
            "cut": "start_cut",
            "stop": "stop",
            "reset": "estop_reset",
        }

        if text in mapping:
            self.send_command(mapping[text])
        else:
            self.log_msg(f"Unrecognized command: '{text}'")


if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()