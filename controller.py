import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import serial
import serial.tools.list_ports
import threading

class PlotterController(tk.Tk):
    PROMPT = "> "

    def __init__(self):
        super().__init__()
        self.title("LPKF Protomat 91s/VS Controller")
        self.geometry("1200x800")
        self.serial_port = None
        self.serial_thread = None
        self.stop_thread = False
        self.emulation_mode = tk.BooleanVar(value=False)
        self.current_position = [0, 0, 0]  # [x, y, z] in µm für Emulation oder letzten bekannten Wert
        self.pen_down = False
        self.motor_enabled = False
        self.workspace_x = 200000  # 200mm in µm, Default
        self.workspace_y = 150000  # 150mm in µm, Default

        self.set_dark_mode()
        self.create_widgets()
        self.refresh_ports()
        self.update_plot()

    def set_dark_mode(self):
        # Set dark colors for the main window and widgets
        self.configure(bg="#222222")
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", background="#222222", foreground="#e0e0e0", fieldbackground="#222222")
        style.configure("TLabel", background="#222222", foreground="#e0e0e0")
        style.configure("TButton", background="#333333", foreground="#e0e0e0")
        style.configure("TFrame", background="#222222")
        style.configure("TLabelframe", background="#222222", foreground="#e0e0e0")
        style.configure("TLabelframe.Label", background="#222222", foreground="#e0e0e0")
        style.configure("TEntry", fieldbackground="#333333", foreground="#e0e0e0")
        style.configure("TCombobox", fieldbackground="#333333", foreground="#e0e0e0")
        style.map("TButton", background=[("active", "#444444")])

    def create_widgets(self):
        # Serial Port Frame
        port_frame = ttk.LabelFrame(self, text="Serial Port Settings")
        port_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(port_frame, text="Port:").grid(row=0, column=0, padx=5, pady=2)
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(port_frame, textvariable=self.port_var, width=15)
        self.port_combo.grid(row=0, column=1, padx=5, pady=2)
        ttk.Button(port_frame, text="Refresh", command=self.refresh_ports).grid(row=0, column=2, padx=5, pady=2)

        ttk.Label(port_frame, text="Baudrate:").grid(row=0, column=3, padx=5, pady=2)
        self.baud_var = tk.StringVar(value="9600")
        ttk.Entry(port_frame, textvariable=self.baud_var, width=8).grid(row=0, column=4, padx=5, pady=2)

        ttk.Label(port_frame, text="Data bits:").grid(row=0, column=5, padx=5, pady=2)
        self.databits_var = tk.StringVar(value="8")
        ttk.Entry(port_frame, textvariable=self.databits_var, width=3).grid(row=0, column=6, padx=5, pady=2)

        ttk.Label(port_frame, text="Parity:").grid(row=0, column=7, padx=5, pady=2)
        self.parity_var = tk.StringVar(value="None")
        self.parity_combo = ttk.Combobox(port_frame, textvariable=self.parity_var, values=["None", "Even", "Odd"], width=6)
        self.parity_combo.grid(row=0, column=8, padx=5, pady=2)

        ttk.Label(port_frame, text="Stop bits:").grid(row=0, column=9, padx=5, pady=2)
        self.stopbits_var = tk.StringVar(value="1")
        ttk.Entry(port_frame, textvariable=self.stopbits_var, width=3).grid(row=0, column=10, padx=5, pady=2)

        ttk.Label(port_frame, text="Flow:").grid(row=0, column=11, padx=5, pady=2)
        self.flow_var = tk.StringVar(value="RTS/CTS")
        self.flow_combo = ttk.Combobox(port_frame, textvariable=self.flow_var, values=["None", "RTS/CTS"], width=8)
        self.flow_combo.grid(row=0, column=12, padx=5, pady=2)

        # Ein Button für Connect/Disconnect
        self.connect_btn = ttk.Button(port_frame, text="Connect", command=self.toggle_connection)
        self.connect_btn.grid(row=0, column=13, padx=10, pady=2)

        # Emulation Mode Checkbox
        self.emu_check = ttk.Checkbutton(port_frame, text="Emulation Mode", variable=self.emulation_mode, command=self.on_emulation_toggle)
        self.emu_check.grid(row=0, column=14, padx=10, pady=2)

        # Terminal Frame
        terminal_frame = ttk.LabelFrame(self, text="Serial Terminal")
        terminal_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.terminal = tk.Text(terminal_frame, height=15, wrap="word", undo=False, autoseparators=False,
                                bg="#181818", fg="#e0e0e0", insertbackground="#e0e0e0", state="disabled")
        self.terminal.pack(fill="both", expand=True, padx=5, pady=(5,0))

        # XY-Move Frame unter Terminal
        move_frame = ttk.LabelFrame(terminal_frame, text="Relative Movement (PRx,y;)")
        move_frame.pack(fill="x", padx=5, pady=(5,0))

        ttk.Label(move_frame, text="Distance [mm]:").grid(row=0, column=1, padx=5, pady=2)
        self.move_dist_var = tk.IntVar(value=10)
        move_spin = ttk.Spinbox(move_frame, from_=1, to=1000, increment=1, textvariable=self.move_dist_var, width=5)
        move_spin.grid(row=0, column=2, padx=5, pady=2)

        # Kreuz-Layout für Richtungstasten
        def move(dx, dy):
            mm = self.move_dist_var.get()
            um = mm * 1000
            self.move_relative_checked(dx*um, dy*um)

        btn_up = ttk.Button(move_frame, text="↑", width=3, command=lambda: move(0, 1))
        btn_left = ttk.Button(move_frame, text="←", width=3, command=lambda: move(-1, 0))
        btn_right = ttk.Button(move_frame, text="→", width=3, command=lambda: move(1, 0))
        btn_down = ttk.Button(move_frame, text="↓", width=3, command=lambda: move(0, -1))

        btn_up.grid(row=1, column=1, pady=2)
        btn_left.grid(row=2, column=0, padx=2)
        btn_right.grid(row=2, column=2, padx=2)
        btn_down.grid(row=3, column=1, pady=2)

        # Absolute Movement Frame
        abs_frame = ttk.LabelFrame(move_frame, text="Absolute Movement (PAx,y;)")
        abs_frame.grid(row=0, column=3, rowspan=4, padx=20, pady=2, sticky="ns")

        ttk.Label(abs_frame, text="X [mm]:").grid(row=0, column=0, padx=2, pady=2)
        self.abs_x_var = tk.IntVar(value=0)
        abs_x_entry = ttk.Entry(abs_frame, textvariable=self.abs_x_var, width=6)
        abs_x_entry.grid(row=0, column=1, padx=2, pady=2)

        ttk.Label(abs_frame, text="Y [mm]:").grid(row=1, column=0, padx=2, pady=2)
        self.abs_y_var = tk.IntVar(value=0)
        abs_y_entry = ttk.Entry(abs_frame, textvariable=self.abs_y_var, width=6)
        abs_y_entry.grid(row=1, column=1, padx=2, pady=2)

        def move_abs_x():
            x_um = self.abs_x_var.get() * 1000
            y_um = self.current_position[1]
            self.move_absolute_checked(x_um, y_um)

        def move_abs_y():
            x_um = self.current_position[0]
            y_um = self.abs_y_var.get() * 1000
            self.move_absolute_checked(x_um, y_um)

        def move_abs_xy():
            x_um = self.abs_x_var.get() * 1000
            y_um = self.abs_y_var.get() * 1000
            self.move_absolute_checked(x_um, y_um)

        ttk.Button(abs_frame, text="Move X", command=move_abs_x).grid(row=2, column=0, padx=2, pady=2)
        ttk.Button(abs_frame, text="Move Y", command=move_abs_y).grid(row=2, column=1, padx=2, pady=2)
        ttk.Button(abs_frame, text="Move X & Y", command=move_abs_xy).grid(row=3, column=0, columnspan=2, padx=2, pady=2)

        # Workspace Limit Frame
        ws_frame = ttk.LabelFrame(move_frame, text="Workspace Limit [mm]")
        ws_frame.grid(row=4, column=0, columnspan=4, padx=2, pady=(10,2), sticky="ew")

        ttk.Label(ws_frame, text="Max X:").grid(row=0, column=0, padx=2, pady=2)
        self.ws_x_var = tk.IntVar(value=200)
        ws_x_entry = ttk.Entry(ws_frame, textvariable=self.ws_x_var, width=6)
        ws_x_entry.grid(row=0, column=1, padx=2, pady=2)

        ttk.Label(ws_frame, text="Max Y:").grid(row=0, column=2, padx=2, pady=2)
        self.ws_y_var = tk.IntVar(value=150)
        ws_y_entry = ttk.Entry(ws_frame, textvariable=self.ws_y_var, width=6)
        ws_y_entry.grid(row=0, column=3, padx=2, pady=2)

        def set_workspace():
            self.workspace_x = self.ws_x_var.get() * 1000
            self.workspace_y = self.ws_y_var.get() * 1000
            self.update_plot()
        ttk.Button(ws_frame, text="Set", command=set_workspace).grid(row=0, column=4, padx=5, pady=2)

        # Visualisierung
        vis_frame = ttk.LabelFrame(move_frame, text="Workspace Visualization")
        vis_frame.grid(row=0, column=4, rowspan=5, padx=20, pady=2, sticky="ns")
        self.canvas = tk.Canvas(vis_frame, width=200, height=150, bg="#181818", highlightthickness=1, highlightbackground="#444")
        self.canvas.grid(row=0, column=0, padx=5, pady=5)

        # Legende
        legend_frame = ttk.Frame(vis_frame)
        legend_frame.grid(row=0, column=1, padx=10, pady=5, sticky="nw")
        tk.Label(legend_frame, text="●", fg="#44ff44", bg="#222222", font=("Arial", 14)).grid(row=0, column=0, sticky="w")
        tk.Label(legend_frame, text="Pen Up", bg="#222222", fg="#e0e0e0").grid(row=0, column=1, sticky="w")
        tk.Label(legend_frame, text="●", fg="#ffaa00", bg="#222222", font=("Arial", 14)).grid(row=1, column=0, sticky="w")
        tk.Label(legend_frame, text="Pen Down", bg="#222222", fg="#e0e0e0").grid(row=1, column=1, sticky="w")
        tk.Label(legend_frame, text="●", fg="#ff4444", bg="#222222", font=("Arial", 14)).grid(row=2, column=0, sticky="w")
        tk.Label(legend_frame, text="Motor Enabled", bg="#222222", fg="#e0e0e0").grid(row=2, column=1, sticky="w")

        # Eingabezeile und Send-Button unter dem Terminal
        input_frame = ttk.Frame(terminal_frame)
        input_frame.pack(fill="x", padx=5, pady=(0,5))
        self.input_var = tk.StringVar()
        self.input_entry = ttk.Entry(input_frame, textvariable=self.input_var)
        self.input_entry.pack(side="left", fill="x", expand=True, padx=(0,5))
        self.input_entry.bind("<Return>", self.on_input_send)
        send_btn = ttk.Button(input_frame, text="Send", command=self.on_input_send)
        send_btn.pack(side="right")
        self.input_entry.focus_set()

        # Command Frame
        cmd_frame = ttk.LabelFrame(self, text="Commands")
        cmd_frame.pack(fill="x", padx=10, pady=5)

        ttk.Button(cmd_frame, text="Initialize (IN;)", command=lambda: self.send_command("IN;")).grid(row=0, column=0, padx=5, pady=2)
        ttk.Button(cmd_frame, text="Pen Up (PU;)", command=lambda: self.send_command("PU;")).grid(row=0, column=1, padx=5, pady=2)
        ttk.Button(cmd_frame, text="Pen Down (PD;)", command=lambda: self.send_command("PD;")).grid(row=0, column=2, padx=5, pady=2)
        ttk.Button(cmd_frame, text="Enable Motor (!EM1;)", command=lambda: self.send_command("!EM1;")).grid(row=0, column=3, padx=5, pady=2)
        ttk.Button(cmd_frame, text="Disable Motor (!EM0;)", command=lambda: self.send_command("!EM0;")).grid(row=0, column=4, padx=5, pady=2)
        ttk.Button(cmd_frame, text="Query Position (!ON0;)", command=lambda: self.send_command("!ON0;")).grid(row=0, column=5, padx=5, pady=2)

        # Command Flow Frame
        flow_frame = ttk.LabelFrame(self, text="Command Flow Example")
        flow_frame.pack(fill="x", padx=10, pady=5)

        self.flow_text = tk.Text(flow_frame, height=4, width=80, bg="#222222", fg="#e0e0e0", insertbackground="#e0e0e0")
        self.flow_text.insert("1.0", "!TS500;PD;PR5000,0;PR0,5000;PR-5000,0;PR0,-5000;PU;!TS0;")
        self.flow_text.pack(side="left", fill="x", expand=True, padx=5, pady=5)
        ttk.Button(flow_frame, text="Execute Flow", command=self.execute_flow).pack(side="left", padx=5, pady=5)

    def refresh_ports(self):
        ports = [port.device for port in serial.tools.list_ports.comports()]
        self.port_combo["values"] = ports
        if ports:
            self.port_combo.current(0)

    def toggle_connection(self):
        if self.emulation_mode.get():
            self.log_terminal("Emulation mode active. No serial connection needed.\n")
            return
        if self.serial_port and self.serial_port.is_open:
            self.disconnect_serial()
        else:
            self.connect_serial()

    def connect_serial(self):
        if self.emulation_mode.get():
            self.log_terminal("Emulation mode active. No serial connection needed.\n")
            return
        try:
            port = self.port_var.get()
            baud = int(self.baud_var.get())
            databits = int(self.databits_var.get())
            parity = {"None": serial.PARITY_NONE, "Even": serial.PARITY_EVEN, "Odd": serial.PARITY_ODD}[self.parity_var.get()]
            stopbits = float(self.stopbits_var.get())
            flow = self.flow_var.get()
            self.serial_port = serial.Serial(
                port=port,
                baudrate=baud,
                bytesize=databits,
                parity=parity,
                stopbits=stopbits,
                timeout=0.1,
                rtscts=(flow == "RTS/CTS"),
                dsrdtr=False,
                xonxoff=False
            )
            self.connect_btn.config(text="Disconnect")
            self.log_terminal(f"Connected to {port}\n")
            self.stop_thread = False
            self.serial_thread = threading.Thread(target=self.read_serial, daemon=True)
            self.serial_thread.start()
        except Exception as e:
            messagebox.showerror("Connection Error", str(e))

    def disconnect_serial(self):
        self.stop_thread = True
        if self.serial_port:
            self.serial_port.close()
            self.serial_port = None
        self.connect_btn.config(text="Connect")
        self.log_terminal("Disconnected\n")

    def on_emulation_toggle(self):
        if self.emulation_mode.get():
            self.disconnect_serial()
            self.connect_btn.config(state="disabled")
            self.log_terminal("Emulation mode enabled.\n")
        else:
            self.connect_btn.config(state="normal")
            self.log_terminal("Emulation mode disabled.\n")

    def read_serial(self):
        while not self.stop_thread and self.serial_port and self.serial_port.is_open:
            try:
                data = self.serial_port.readline()
                if data:
                    self.log_terminal(f"Received: {data.decode(errors='replace')}")
            except Exception:
                pass

    def send_command(self, cmd, update_position=False):
        if self.emulation_mode.get():
            self.log_terminal(f"Sent: {cmd}\n")
            # Emulation: Status-Tracking für Pen/Motor
            if cmd.strip().upper() == "PU;":
                self.pen_down = False
                self.update_plot()
            elif cmd.strip().upper() == "PD;":
                self.pen_down = True
                self.update_plot()
            elif cmd.strip().upper() == "!EM1;":
                self.motor_enabled = True
                self.update_plot()
            elif cmd.strip().upper() == "!EM0;":
                self.motor_enabled = False
                self.update_plot()
            # Emulation: Position berechnen, wenn PR-Befehl
            if cmd.startswith("PR"):
                try:
                    parts = cmd[2:].split(";")[0].split(",")
                    dx = int(parts[0])
                    dy = int(parts[1]) if len(parts) > 1 else 0
                    new_x = self.current_position[0] + dx
                    new_y = self.current_position[1] + dy
                    if new_x < 0 or new_y < 0 or new_x > self.workspace_x or new_y > self.workspace_y:
                        self.log_terminal("Emulation: Movement would go outside workspace! Command not executed.\n")
                    else:
                        self.current_position[0] = new_x
                        self.current_position[1] = new_y
                        self.log_terminal(f"Emulation: New position X={new_x} Y={new_y}\n")
                        self.update_plot()
                except Exception:
                    pass
            self.log_terminal("Received: Emulation, no communication\n")
            return
        if not self.serial_port or not self.serial_port.is_open:
            messagebox.showwarning("Not Connected", "Please connect to a serial port first or enable Emulation Mode.")
            return
        try:
            self.serial_port.write(cmd.encode())
            self.log_terminal(f"Sent: {cmd}\n")
            # Status-Tracking für Pen/Motor
            if cmd.strip().upper() == "PU;":
                self.pen_down = False
                self.update_plot()
            elif cmd.strip().upper() == "PD;":
                self.pen_down = True
                self.update_plot()
            elif cmd.strip().upper() == "!EM1;":
                self.motor_enabled = True
                self.update_plot()
            elif cmd.strip().upper() == "!EM0;":
                self.motor_enabled = False
                self.update_plot()
            if update_position:
                self.after(200, self.query_and_update_position)
        except Exception as e:
            messagebox.showerror("Send Error", str(e))

    def query_and_update_position(self):
        if self.emulation_mode.get():
            return
        if not self.serial_port or not self.serial_port.is_open:
            return
        try:
            self.serial_port.reset_input_buffer()
            self.serial_port.write(b"!ON0;\n")
            data = self.serial_port.readline().decode(errors="replace")
            if data.startswith("P"):
                try:
                    coords = data[1:].split("C")[0].split(",")
                    self.current_position = [int(coords[0]), int(coords[1]), int(coords[2])]
                    self.update_plot()
                except Exception:
                    pass
        except Exception:
            pass

    def move_relative_checked(self, dx, dy):
        if self.emulation_mode.get():
            new_x = self.current_position[0] + dx
            new_y = self.current_position[1] + dy
            if new_x < 0 or new_y < 0 or new_x > self.workspace_x or new_y > self.workspace_y:
                self.log_terminal("Emulation: Movement would go outside workspace! Command not executed.\n")
                return
            self.send_command(f"PR{dx},{dy};", update_position=True)
            self.current_position[0] = new_x
            self.current_position[1] = new_y
            self.update_plot()
            return
        self.query_and_update_position()
        new_x = self.current_position[0] + dx
        new_y = self.current_position[1] + dy
        if new_x < 0 or new_y < 0 or new_x > self.workspace_x or new_y > self.workspace_y:
            self.log_terminal("Movement would go outside workspace! Command not executed.\n")
            return
        self.send_command(f"PR{dx},{dy};", update_position=True)
        self.current_position[0] = new_x
        self.current_position[1] = new_y
        self.update_plot()

    def move_absolute_checked(self, x_um, y_um):
        # Prüfe Workspace
        if x_um < 0 or y_um < 0 or x_um > self.workspace_x or y_um > self.workspace_y:
            self.log_terminal("Target position outside workspace! Command not executed.\n")
            return
        dx = x_um - self.current_position[0]
        dy = y_um - self.current_position[1]
        if self.emulation_mode.get():
            self.send_command(f"PR{dx},{dy};", update_position=True)
            self.current_position[0] = x_um
            self.current_position[1] = y_um
            self.update_plot()
            return
        self.query_and_update_position()
        dx = x_um - self.current_position[0]
        dy = y_um - self.current_position[1]
        if self.current_position[0] + dx < 0 or self.current_position[1] + dy < 0 or self.current_position[0] + dx > self.workspace_x or self.current_position[1] + dy > self.workspace_y:
            self.log_terminal("Target position outside workspace! Command not executed.\n")
            return
        self.send_command(f"PR{dx},{dy};", update_position=True)
        self.current_position[0] += dx
        self.current_position[1] += dy
        self.update_plot()

    def on_input_send(self, event=None):
        cmd = self.input_var.get().strip()
        if cmd:
            if not cmd.endswith(";"):
                cmd += ";"
            self.send_command(cmd)
        self.input_var.set("")
        self.input_entry.focus_set()

    def log_terminal(self, text):
        self.terminal.config(state="normal")
        if not text.endswith("\n"):
            text += "\n"
        self.terminal.insert("end", text)
        self.terminal.see("end")
        self.terminal.config(state="disabled")

    def execute_flow(self):
        flow = self.flow_text.get("1.0", "end").strip()
        # Sende den gesamten Flow als einen Befehl
        if flow:
            # Stelle sicher, dass der letzte Befehl mit ; endet
            if not flow.endswith(";"):
                flow += ";"
            self.send_command(flow)

    def update_plot(self):
        # Zeichnet das Rechteck und die aktuelle Position
        self.canvas.delete("all")
        w = int(self.canvas["width"])
        h = int(self.canvas["height"])
        max_x = self.workspace_x
        max_y = self.workspace_y
        # Rechteck Workspace
        self.canvas.create_rectangle(10, 10, w-10, h-10, outline="#e0e0e0")
        # Marker für aktuelle Position
        if max_x > 0 and max_y > 0:
            px = 10 + (w-20) * self.current_position[0] / max_x
            py = 10 + (h-20) * (1 - self.current_position[1] / max_y)
            # Farbe je nach Status
            color = "#44ff44"  # Grün = Pen Up
            if self.motor_enabled:
                color = "#ff4444"  # Rot = Motor an
            elif self.pen_down:
                color = "#ffaa00"  # Orange = Pen Down
            self.canvas.create_oval(px-5, py-5, px+5, py+5, fill=color, outline=color)

    def on_closing(self):
        self.stop_thread = True
        self.disconnect_serial()  # Automatisch trennen beim Schließen
        self.destroy()

if __name__ == "__main__":
    app = PlotterController()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
