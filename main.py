import sys
import random
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QStackedWidget, QListWidget,
    QProgressBar, QDoubleSpinBox, QFormLayout, QComboBox, QTableWidget,
    QTableWidgetItem, QTextEdit, QLineEdit, QHeaderView, QGroupBox
)
from PySide6.QtCore import Qt, QTimer, QRectF
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont


class BeamSawVisualizer(QWidget):
    """2D Kinematic Canvas representing machine bed, workpiece, and axes."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 220)
        self.panel_width = 2400.0   # mm
        self.panel_length = 1200.0  # mm
        self.pusher_x = 1800.0      # X axis mm
        self.saw_y = 0.0            # Y axis mm
        self.is_cutting = False

    def update_telemetry(self, pusher_x, saw_y, cutting):
        self.pusher_x = pusher_x
        self.saw_y = saw_y
        self.is_cutting = cutting
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        painter.fillRect(0, 0, w, h, QColor(25, 25, 35))

        margin = 30
        scale_x = (w - 2 * margin) / 3000.0
        scale_y = (h - 2 * margin) / 1500.0

        # Draw Wood Panel
        board_w = self.panel_width * scale_x
        board_h = self.panel_length * scale_y
        board_x = margin
        board_y = margin + (1500 - self.panel_length) * scale_y / 2

        painter.setBrush(QBrush(QColor(160, 110, 60)))
        painter.setPen(QPen(QColor(210, 150, 90), 2))
        painter.drawRect(QRectF(board_x, board_y, board_w, board_h))

        # Rear Pusher (X-Axis)
        pusher_px = margin + (self.pusher_x * scale_x)
        painter.setPen(QPen(QColor(0, 210, 255), 3))
        painter.setBrush(QBrush(QColor(0, 150, 200, 100)))
        painter.drawRect(QRectF(pusher_px - 8, board_y - 10, 16, board_h + 20))

        # Saw Carriage (Y-Axis)
        saw_py = board_y + (self.saw_y * scale_y)
        blade_color = QColor(255, 60, 60) if self.is_cutting else QColor(255, 180, 0)
        painter.setPen(QPen(blade_color, 4, Qt.PenStyle.DashLine if not self.is_cutting else Qt.PenStyle.SolidLine))
        painter.drawLine(pusher_px, board_y, pusher_px, board_y + board_h)

        # Saw Blade
        painter.setBrush(QBrush(blade_color))
        painter.drawEllipse(QRectF(pusher_px - 10, saw_py - 10, 20, 20))

        # Overlay text
        painter.setPen(QPen(QColor(200, 200, 200)))
        painter.setFont(QFont("Segoe UI", 9))
        painter.drawText(margin, h - 8, f"Pusher X: {self.pusher_x:.1f} mm | Saw Carriage Y: {self.saw_y:.1f} mm")


class MetricCard(QFrame):
    """Reusable telemetry card widget."""
    def __init__(self, title, unit, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame {
                background-color: #252536; border-radius: 8px;
                border: 1px solid #383850; padding: 8px;
            }
        """)
        layout = QVBoxLayout(self)
        self.lbl_title = QLabel(title)
        self.lbl_title.setStyleSheet("color: #8a8aa3; font-size: 11px; font-weight: bold;")
        self.lbl_val = QLabel(f"0.0 {unit}")
        self.lbl_val.setStyleSheet("color: #00d2ff; font-size: 18px; font-weight: bold;")
        layout.addWidget(self.lbl_title)
        layout.addWidget(self.lbl_val)

    def set_value(self, val_str):
        self.lbl_val.setText(val_str)


class BeamSawHMI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CNC Beam Saw Control System - Full HMI Suite")
        self.resize(1150, 750)

        # User Role Access Matrix Mapping
        self.access_rights = {
            "Operator": [0, 1, 3],                         # Operation, Job Setup, Simulation
            "Designer": [0, 1, 2, 3],                      # + Cut Design
            "Maintenance Engineer": [0, 1, 2, 3, 4, 5, 6], # + Diagnostics, Warnings, Calibration
            "Super User": [0, 1, 2, 3, 4, 5, 6, 7]         # All Panels
        }
        self.current_role = "Super User"

        self.apply_styles()

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Top Header Bar (User switching & System Status)
        top_bar = QFrame()
        top_bar.setStyleSheet("background-color: #12121c; border-bottom: 1px solid #2a2a3d; padding: 6px;")
        top_layout = QHBoxLayout(top_bar)
        
        lbl_brand = QLabel("<b>BEAM SAW CONTROL SYSTEM</b> | S7-1200 PLC")
        lbl_brand.setStyleSheet("color: #00d2ff; font-size: 14px;")
        top_layout.addWidget(lbl_brand)
        top_layout.addStretch()

        top_layout.addWidget(QLabel("Logged User Role:"))
        self.combo_role = QComboBox()
        self.combo_role.addItems(["Operator", "Designer", "Maintenance Engineer", "Super User"])
        self.combo_role.setCurrentText("Super User")
        self.combo_role.currentTextChanged.connect(self.on_role_changed)
        top_layout.addWidget(self.combo_role)

        main_layout.addWidget(top_bar)

        # Content Area
        body_layout = QHBoxLayout()
        body_layout.setContentsMargins(0, 0, 0, 0)

        # Navigation Sidebar
        self.sidebar = QListWidget()
        self.sidebar.setFixedWidth(210)
        self.sidebar.addItems([
            "01. Operation",
            "02. Job Setup",
            "03. Cut Design (CAD)",
            "04. 3D Simulation",
            "05. Diagnostics",
            "06. Warnings / Alarms",
            "07. Calibration",
            "08. Settings & Users"
        ])
        body_layout.addWidget(self.sidebar)

        # Stacked Pages
        self.pages = QStackedWidget()
        body_layout.addWidget(self.pages)
        main_layout.addLayout(body_layout)

        # Build All 8 Panels
        self.build_operation_panel()
        self.build_job_setup_panel()
        self.build_cut_design_panel()
        self.build_simulation_panel()
        self.build_diagnostics_panel()
        self.build_warnings_panel()
        self.build_calibration_panel()
        self.build_settings_panel()

        self.sidebar.currentRowChanged.connect(self.change_panel)

        # Simulation Timer
        self.sim_timer = QTimer(self)
        self.sim_timer.timeout.connect(self.simulate_plc_cycle)
        self.sim_pusher_x = 2400.0
        self.sim_saw_y = 0.0
        self.sim_cutting = False

    def apply_styles(self):
        self.setStyleSheet("""
            QMainWindow, QWidget { background-color: #1a1a26; color: #e0e0e0; font-family: 'Segoe UI', sans-serif; }
            QLabel { color: #e0e0e0; }
            QPushButton {
                background-color: #007acc; color: white; border: none;
                padding: 8px 14px; border-radius: 4px; font-weight: bold;
            }
            QPushButton:hover { background-color: #0098ff; }
            QPushButton#btn_danger { background-color: #e63946; }
            QPushButton#btn_danger:hover { background-color: #ff4d5d; }
            QListWidget {
                background-color: #12121c; border: none; color: #a0a0b8;
                font-size: 13px; font-weight: bold;
            }
            QListWidget::item { padding: 14px 10px; }
            QListWidget::item:selected {
                background-color: #202030; color: #00d2ff; border-left: 4px solid #00d2ff;
            }
            QListWidget::item:disabled { color: #404050; }
            QLineEdit, QDoubleSpinBox, QComboBox, QTextEdit {
                background-color: #252536; border: 1px solid #383850;
                color: #ffffff; padding: 6px; border-radius: 4px;
            }
            QTableWidget {
                background-color: #202030; gridline-color: #303045;
                border: 1px solid #383850; border-radius: 4px;
            }
            QHeaderView::section { background-color: #181824; color: #00d2ff; padding: 6px; border: none; }
            QGroupBox { border: 1px solid #383850; border-radius: 6px; margin-top: 10px; padding-top: 10px; font-weight: bold; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; color: #00d2ff; }
        """)

    def on_role_changed(self, role):
        self.current_role = role
        allowed_panels = self.access_rights[role]

        for i in range(self.sidebar.count()):
            item = self.sidebar.item(i)
            if i in allowed_panels:
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            else:
                item.setFlags(Qt.NoItemFlags)

        if self.sidebar.currentRow() not in allowed_panels:
            self.sidebar.setCurrentRow(0)

    def change_panel(self, index):
        if index in self.access_rights[self.current_role]:
            self.pages.setCurrentIndex(index)

    # ---------------- 01. OPERATION PANEL ----------------
    def build_operation_panel(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        header = QHBoxLayout()
        header.addWidget(QLabel("<h2>LIVE MACHINE OPERATION</h2>"))
        header.addStretch()
        self.lbl_status = QLabel("SYSTEM READY")
        self.lbl_status.setStyleSheet("background-color: #1b4332; color: #52b788; padding: 6px 12px; border-radius: 12px; font-weight: bold;")
        header.addWidget(self.lbl_status)
        layout.addLayout(header)

        cards = QHBoxLayout()
        self.card_pusher = MetricCard("REAR PUSHER (X)", "mm")
        self.card_carriage = MetricCard("SAW CARRIAGE (Y)", "mm")
        self.card_spindle = MetricCard("SPINDLE SPEED", "RPM")
        self.card_current = MetricCard("VFD CURRENT", "A")
        for c in [self.card_pusher, self.card_carriage, self.card_spindle, self.card_current]:
            cards.addWidget(c)
        layout.addLayout(cards)

        self.visualizer = BeamSawVisualizer()
        layout.addWidget(self.visualizer, stretch=1)

        controls = QHBoxLayout()
        btn_start = QPushButton("START CUTTING CYCLE")
        btn_start.clicked.connect(self.start_cycle)
        btn_pause = QPushButton("PAUSE")
        btn_pause.setStyleSheet("background-color: #d97706;")
        btn_estop = QPushButton("EMERGENCY STOP")
        btn_estop.setObjectName("btn_danger")
        btn_estop.clicked.connect(self.trigger_estop)

        controls.addWidget(btn_start)
        controls.addWidget(btn_pause)
        controls.addWidget(btn_estop)
        layout.addLayout(controls)

        self.pages.addWidget(page)

    # ---------------- 02. JOB SETUP PANEL ----------------
    def build_job_setup_panel(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("<h2>JOB SETUP & STOCK DEFINITION</h2>"))

        group = QGroupBox("Raw Wood Beam / Board Parameters")
        form = QFormLayout(group)

        self.spin_length = QDoubleSpinBox()
        self.spin_length.setRange(100, 4000)
        self.spin_length.setValue(2400)
        
        self.spin_width = QDoubleSpinBox()
        self.spin_width.setRange(100, 2000)
        self.spin_width.setValue(1200)

        self.spin_thick = QDoubleSpinBox()
        self.spin_thick.setValue(18)

        self.combo_mat = QComboBox()
        self.combo_mat.addItems(["MDF Board", "Particle Board", "Plywood", "Melamine Laminated"])

        form.addRow("Beam Length X (mm):", self.spin_length)
        form.addRow("Beam Width Y (mm):", self.spin_width)
        form.addRow("Thickness (mm):", self.spin_thick)
        form.addRow("Material Type:", self.combo_mat)

        layout.addWidget(group)

        btn_load = QPushButton("Load Workpiece to PLC Memory")
        btn_load.clicked.connect(self.update_stock_dims)
        layout.addWidget(btn_load)
        layout.addStretch()

        self.pages.addWidget(page)

    def update_stock_dims(self):
        self.visualizer.panel_width = self.spin_length.value()
        self.visualizer.panel_length = self.spin_width.value()
        self.visualizer.update()
        self.lbl_status.setText("NEW STOCK LOADED")

    # ---------------- 03. CUT DESIGN PANEL ----------------
    def build_cut_design_panel(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("<h2>CAD PARSER & G-CODE GENERATOR</h2>"))

        top_btns = QHBoxLayout()
        btn_import = QPushButton("Import DXF File")
        btn_draw = QPushButton("Manual Cut Layout Tool")
        top_btns.addWidget(btn_import)
        top_btns.addWidget(btn_draw)
        layout.addLayout(top_btns)

        group = QGroupBox("Generated G-Code Output (PLC Toolpath)")
        gcode_layout = QVBoxLayout(group)
        self.txt_gcode = QTextEdit()
        self.txt_gcode.setText(
            "G21 ; Millimeter units\n"
            "G90 ; Absolute positioning\n"
            "M03 S4500 ; Start Scoring & Main Spindles\n"
            "G00 X1800.0 ; Index Rear Pusher\n"
            "M10 ; Pressure Beam Clamp DOWN\n"
            "G01 Y1200.0 F3000 ; Saw Carriage Cut Pass\n"
            "M11 ; Pressure Beam UNCLAMP\n"
            "G00 Y0.0 ; Rapid Carriage Return\n"
            "M05 ; Spindle Stop"
        )
        gcode_layout.addWidget(self.txt_gcode)
        layout.addWidget(group)

        self.pages.addWidget(page)

    # ---------------- 04. SIMULATION PANEL ----------------
    def build_simulation_panel(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("<h2>3D DIGITAL TWIN & MOTION SIMULATION</h2>"))
        
        sim_box = QFrame()
        sim_box.setStyleSheet("background-color: #101018; border: 1px solid #00d2ff; border-radius: 6px;")
        sim_layout = QVBoxLayout(sim_box)
        sim_layout.addWidget(QLabel("<h3 style='color:#00d2ff; align:center;'>PLCSIM Virtual Twin Active</h3>"))
        sim_layout.addWidget(BeamSawVisualizer())
        layout.addWidget(sim_box, stretch=1)

        self.pages.addWidget(page)

    # ---------------- 05. DIAGNOSTICS PANEL ----------------
    def build_diagnostics_panel(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("<h2>IIoT DIAGNOSTICS & HARDWARE STATUS</h2>"))

        tbl = QTableWidget(5, 3)
        tbl.setHorizontalHeaderLabels(["Telemetry Sensor", "Measured Value", "Status"])
        tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        diag_data = [
            ("Main Spindle Vibration (FFT)", "1.2 mm/s", "NORMAL"),
            ("Main Motor Current Draw", "14.2 A", "NORMAL"),
            ("Pneumatic Pressure Decay", "6.2 Bar", "OPTIMAL"),
            ("Scoring Blade Arbor Temp", "42 °C", "NORMAL"),
            ("Safety Curtain Interlock", "Closed Circuit", "HEALTHY")
        ]

        for row, (name, val, stat) in enumerate(diag_data):
            tbl.setItem(row, 0, QTableWidgetItem(name))
            tbl.setItem(row, 1, QTableWidgetItem(val))
            item_stat = QTableWidgetItem(stat)
            item_stat.setForeground(QColor("#52b788"))
            tbl.setItem(row, 2, item_stat)

        layout.addWidget(tbl)
        self.pages.addWidget(page)

    # ---------------- 06. WARNINGS PANEL ----------------
    def build_warnings_panel(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("<h2>ALARM LOG & SYSTEM FAULTS</h2>"))

        tbl = QTableWidget(3, 3)
        tbl.setHorizontalHeaderLabels(["Timestamp", "Alarm Message", "Severity"])
        tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        alarms = [
            ("10:14:02", "Pneumatic Pressure Drop Below 5.5 Bar", "WARNING"),
            ("09:30:15", "Safety Light Curtain Tripped", "CRITICAL"),
            ("08:00:00", "System Cold Boot Initialization", "INFO")
        ]

        for row, (ts, msg, sev) in enumerate(alarms):
            tbl.setItem(row, 0, QTableWidgetItem(ts))
            tbl.setItem(row, 1, QTableWidgetItem(msg))
            tbl.setItem(row, 2, QTableWidgetItem(sev))

        layout.addWidget(tbl)
        btn_reset = QPushButton("Acknowledge & Reset Alarms")
        btn_reset.setStyleSheet("background-color: #d97706;")
        layout.addWidget(btn_reset)

        self.pages.addWidget(page)

    # ---------------- 07. CALIBRATION PANEL ----------------
    def build_calibration_panel(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("<h2>MACHINE CALIBRATION & HOMING ROUTINE</h2>"))

        group = QGroupBox("Axis Referencing")
        glayout = QVBoxLayout(group)
        btn_home_x = QPushButton("Execute X-Axis Pusher Homing")
        btn_home_y = QPushButton("Execute Y-Axis Carriage Homing")
        glayout.addWidget(btn_home_x)
        glayout.addWidget(btn_home_y)
        layout.addWidget(group)

        group_offsets = QGroupBox("Tool Offset & Kerf Tuning")
        form = QFormLayout(group_offsets)
        form.addRow("Main Blade Kerf Thickness (mm):", QDoubleSpinBox())
        form.addRow("Pusher Mechanical Offset (mm):", QDoubleSpinBox())
        layout.addWidget(group_offsets)

        layout.addStretch()
        self.pages.addWidget(page)

    # ---------------- 08. SETTINGS PANEL ----------------
    def build_settings_panel(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("<h2>USER MANAGEMENT & NETWORK SETTINGS</h2>"))

        form = QFormLayout()
        form.addRow("Siemens S7-1200 IP Address:", QLineEdit("192.168.0.1"))
        form.addRow("OPC UA Port:", QLineEdit("4840"))
        layout.addLayout(form)

        layout.addStretch()
        self.pages.addWidget(page)

    # ---------------- CONTROL ACTIONS & SIMULATION ----------------
    def start_cycle(self):
        self.sim_cutting = True
        self.sim_pusher_x = 1800.0
        self.sim_saw_y = 0.0
        self.lbl_status.setText("EXECUTING CUT")
        self.lbl_status.setStyleSheet("background-color: #5c3d00; color: #ffb703; padding: 6px 12px; border-radius: 12px; font-weight: bold;")
        self.sim_timer.start(30)

    def trigger_estop(self):
        self.sim_timer.stop()
        self.sim_cutting = False
        self.lbl_status.setText("E-STOP ACTIVATED")
        self.lbl_status.setStyleSheet("background-color: #4a0e17; color: #ff4d6d; padding: 6px 12px; border-radius: 12px; font-weight: bold;")
        self.card_spindle.set_value("0 RPM")
        self.card_current.set_value("0.0 A")

    def simulate_plc_cycle(self):
        if self.sim_saw_y < self.visualizer.panel_length:
            self.sim_saw_y += 15.0
            spindle_rpm = 4500 + random.randint(-40, 40)
            vfd_amps = 14.2 + random.uniform(-0.3, 0.5)
        else:
            self.sim_timer.stop()
            self.sim_cutting = False
            self.lbl_status.setText("CYCLE COMPLETED")
            self.lbl_status.setStyleSheet("background-color: #1b4332; color: #52b788; padding: 6px 12px; border-radius: 12px; font-weight: bold;")
            spindle_rpm = 0
            vfd_amps = 0.0

        self.card_pusher.set_value(f"{self.sim_pusher_x:.1f} mm")
        self.card_carriage.set_value(f"{self.sim_saw_y:.1f} mm")
        self.card_spindle.set_value(f"{spindle_rpm} RPM")
        self.card_current.set_value(f"{vfd_amps:.1f} A")

        self.visualizer.update_telemetry(self.sim_pusher_x, self.sim_saw_y, self.sim_cutting)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = BeamSawHMI()
    window.show()
    sys.exit(app.exec())