"""
Tkinter-based display system for rover basestation.
Replaces pygame display with cross-platform GUI.
"""

import tkinter as tk
from tkinter import ttk, font
from typing import Dict, Any
import threading
import time
from .CommandCodes import CONSTANTS


class TkinterDisplay:
    """
    Tkinter-based display for rover basestation with simulation mode warning.
    """

    def __init__(self):
        """
        Initialize the tkinter display system.
        """

        self.root = tk.Tk()
        self.root.title("SPEX Rover Basestation Control")
        self.root.geometry("800x600")

        # Controller data
        self.controllers = {}
        self.controller_values = {}

        # Mode flags
        self.creep_mode = False
        self.reverse_mode = False
        self.simulation_mode = CONSTANTS.SIMULATION_MODE

        # Telemetry data
        self.telemetry_data = {}

        self._setup_ui()
        self._setup_styles()

        # Start UI update thread
        self.running = True
        self.update_thread = threading.Thread(target=self._update_loop, daemon=True)
        self.update_thread.start()

    def _setup_styles(self):
        """
        Setup custom styles for the UI.
        """

        self.style = ttk.Style()

        # Configure warning style for simulation mode
        self.style.configure(
            "Warning.TFrame",
            background="red",
            relief="raised",
            borderwidth=3
        )

        self.style.configure(
            "Warning.TLabel",
            background="red",
            foreground="white",
            font=("Arial", 16, "bold")
        )

        # Status indicators
        self.style.configure(
            "Status.TLabel",
            font=("Arial", 12, "bold")
        )

    def _setup_ui(self):
        """
        Setup the main UI layout.
        """

        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky="nsew")

        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)

        # Simulation mode warning (if enabled)
        if self.simulation_mode:
            self._create_warning_banner(main_frame)

        # Status section
        self._create_status_section(main_frame)

        # Controller section
        self._create_controller_section(main_frame)

        # Telemetry section
        self._create_telemetry_section(main_frame)

    def _create_warning_banner(self, parent):
        """
        Create the big red warning banner for simulation mode.
        """

        warning_frame = ttk.Frame(parent, style="Warning.TFrame", padding="20")
        warning_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 20))

        warning_text = "⚠️ SIMULATION MODE ACTIVE ⚠️\nNO ROVER COMMUNICATION\nCHANGE CONSTANTS.SIMULATION_MODE TO FALSE FOR REAL OPERATION"
        warning_label = ttk.Label(
            warning_frame,
            text=warning_text,
            style="Warning.TLabel",
            justify=tk.CENTER
        )
        warning_label.grid(row=0, column=0)

        # Make warning frame expand
        warning_frame.columnconfigure(0, weight=1)
        parent.columnconfigure(0, weight=1)

    def _create_status_section(self, parent):
        """
        Create the status indicators section.
        """

        row_offset = 1 if self.simulation_mode else 0

        status_frame = ttk.LabelFrame(parent, text="System Status", padding="10")
        status_frame.grid(row=row_offset, column=0, sticky="new", padx=(0, 10))

        # Communication status
        self.comm_status_label = ttk.Label(status_frame, text="Communication: Disconnected", style="Status.TLabel")
        self.comm_status_label.grid(row=0, column=0, sticky=tk.W, pady=2)

        # Mode indicators
        self.creep_status_label = ttk.Label(status_frame, text="Creep Mode: OFF")
        self.creep_status_label.grid(row=1, column=0, sticky=tk.W, pady=2)

        self.reverse_status_label = ttk.Label(status_frame, text="Reverse Mode: OFF")
        self.reverse_status_label.grid(row=2, column=0, sticky=tk.W, pady=2)

        # Update counter
        self.update_counter_label = ttk.Label(status_frame, text="Updates Sent: 0")
        self.update_counter_label.grid(row=3, column=0, sticky=tk.W, pady=2)

    def _create_controller_section(self, parent):
        """
        Create the controller information section.
        """

        row_offset = 1 if self.simulation_mode else 0

        controller_frame = ttk.LabelFrame(parent, text="Controller Status", padding="10")
        controller_frame.grid(row=row_offset, column=1, sticky="nsew")
        controller_frame.columnconfigure(0, weight=1)

        # Controller list with scrollbar
        list_frame = ttk.Frame(controller_frame)
        list_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
        list_frame.columnconfigure(0, weight=1)

        self.controller_text = tk.Text(list_frame, height=15, width=50, wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.controller_text.yview)
        self.controller_text.configure(yscrollcommand=scrollbar.set)

        self.controller_text.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        list_frame.rowconfigure(0, weight=1)
        controller_frame.rowconfigure(0, weight=1)

    def _create_telemetry_section(self, parent):
        """
        Create the telemetry display section.
        """

        row_offset = 2 if self.simulation_mode else 1

        telemetry_frame = ttk.LabelFrame(parent, text="Telemetry Data", padding="10")
        telemetry_frame.grid(row=row_offset, column=0, columnspan=2, sticky="nsew", pady=(10, 0))
        telemetry_frame.columnconfigure(0, weight=1)

        # Telemetry display with scrollbar
        tel_frame = ttk.Frame(telemetry_frame)
        tel_frame.grid(row=0, column=0, sticky="nsew")
        tel_frame.columnconfigure(0, weight=1)

        self.telemetry_text = tk.Text(tel_frame, height=8, wrap=tk.WORD)
        tel_scrollbar = ttk.Scrollbar(tel_frame, orient=tk.VERTICAL, command=self.telemetry_text.yview)
        self.telemetry_text.configure(yscrollcommand=tel_scrollbar.set)

        self.telemetry_text.grid(row=0, column=0, sticky="nsew")
        tel_scrollbar.grid(row=0, column=1, sticky="ns")

        tel_frame.rowconfigure(0, weight=1)
        telemetry_frame.rowconfigure(0, weight=1)
        parent.rowconfigure(row_offset, weight=1)

    def update_controller_display(self, controller_id: int, controller_data: Dict[str, Any]):
        """
        Update controller display with new data.

        Args:
            controller_id: ID of the controller
            controller_data: Dictionary containing controller information
        """

        self.controllers[controller_id] = controller_data

    def update_controller_values(self, values: Dict[str, Any]):
        """
        Update controller values display.

        Args:
            values: Dictionary of current controller values
        """

        self.controller_values = values

    def update_modes(self, creep: bool = False, reverse: bool = False):
        """
        Update mode indicators.

        Args:
            creep: Whether creep mode is active
            reverse: Whether reverse mode is active
        """

        self.creep_mode = creep
        self.reverse_mode = reverse

    def update_telemetry(self, telemetry: Dict[str, Any]):
        """
        Update telemetry data display.

        Args:
            telemetry: Dictionary containing telemetry data
        """

        self.telemetry_data.update(telemetry)

    def update_communication_status(self, connected: bool, message_count: int = 0):
        """
        Update communication status display.

        Args:
            connected: Whether communication is active
            message_count: Number of messages sent
        """

        if hasattr(self, 'comm_status_label'):
            status = "Connected" if connected else "Disconnected"
            if self.simulation_mode:
                status += " (SIMULATION)"
            self.comm_status_label.config(text=f"Communication: {status}")

        if hasattr(self, 'update_counter_label'):
            self.update_counter_label.config(text=f"Updates Sent: {message_count}")

    def _update_display_content(self):
        """
        Update all display content. Called from update loop.
        """

        # Update status labels
        if hasattr(self, 'creep_status_label'):
            creep_text = "ON" if self.creep_mode else "OFF"
            self.creep_status_label.config(text=f"Creep Mode: {creep_text}")

        if hasattr(self, 'reverse_status_label'):
            reverse_text = "ON" if self.reverse_mode else "OFF"
            self.reverse_status_label.config(text=f"Reverse Mode: {reverse_text}")

        # Update controller display
        self._update_controller_text()

        # Update telemetry display
        self._update_telemetry_text()

    def _update_controller_text(self):
        """
        Update the controller text display.
        """

        if not hasattr(self, 'controller_text'):
            return

        self.controller_text.delete(1.0, tk.END)

        if not self.controllers:
            self.controller_text.insert(tk.END, "No controllers connected\n")
            return

        for controller_id, data in self.controllers.items():
            self._insert_controller_info(controller_id, data)

    def _insert_controller_info(self, controller_id: int, data: Dict[str, Any]):
        """
        Helper method to insert individual controller information.
        """

        self.controller_text.insert(tk.END, f"Controller {controller_id}:\n")
        self.controller_text.insert(tk.END, f"  Name: {data.get('name', 'Unknown')}\n")
        self.controller_text.insert(tk.END, f"  GUID: {data.get('guid', 'Unknown')}\n")

        if self.controller_values:
            self._insert_controller_values()

        self.controller_text.insert(tk.END, "\n")

    def _insert_controller_values(self):
        """
        Helper method to insert controller values.
        """

        self.controller_text.insert(tk.END, "  Current Values:\n")
        for key, value in self.controller_values.items():
            if isinstance(value, bytes):
                value = int.from_bytes(value, 'big')
            self.controller_text.insert(tk.END, f"    {key}: {value}\n")

    def _update_telemetry_text(self):
        """
        Update the telemetry text display.
        """

        if hasattr(self, 'telemetry_text'):
            self.telemetry_text.delete(1.0, tk.END)

            if not self.telemetry_data:
                self.telemetry_text.insert(tk.END, "No telemetry data available\n")
                return

            self.telemetry_text.insert(tk.END, f"Telemetry Data (Updated: {time.strftime('%H:%M:%S')}):\n\n")
            for key, value in self.telemetry_data.items():
                self.telemetry_text.insert(tk.END, f"{key}: {value}\n")

    def _update_loop(self):
        """
        Main update loop for the display (runs in separate thread).
        """

        while self.running:
            try:
                # Schedule update on main thread
                self.root.after_idle(self._update_display_content)
                time.sleep(0.1)  # Update every 100ms
            except Exception as e:
                print(f"Display update error: {e}")
                break

    def run(self):
        """
        Start the tkinter main loop.
        """

        try:
            self.root.mainloop()
        finally:
            self.running = False

    def quit(self):
        """
        Quit the display system.
        """

        self.running = False
        if self.root:
            self.root.quit()
