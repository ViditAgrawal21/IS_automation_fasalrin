"""
Main Dashboard — the primary UI window for the IS Claim Automation system.

Features:
  - Profile selection with Create / Edit / Delete
  - Excel file upload
  - Mode selection (Single / Multi)
  - Start row entry
  - Start / Stop automation controls
  - Live log viewer with auto-scroll
  - Thread-safe captcha dialog integration
  - Two-phase stop (graceful → FORCE STOP)
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os

from profile_manager import list_profiles, load_profile, delete_profile
from controller import run, force_kill_browser
from ui.create_profile import CreateProfileWindow
from ui.captcha_dialog import CaptchaHandler


class ISClaimAutomationApp:
    """Main application window for IS Claim Automation."""

    def __init__(self, root):
        self.root = root
        self.root.title("Fasal Rin — IS Claim Automation")
        self.root.geometry("950x720")
        self.root.minsize(800, 600)

        # State
        self.excel_path = None
        self.stop_event = threading.Event()
        self.worker_thread = None
        self.is_running = False
        self.browser_ref = {}
        self._stop_requested = False

        # Captcha handler
        self.captcha_handler = CaptchaHandler(self.root)

        # Style
        style = ttk.Style()
        style.configure("Title.TLabel", font=("Segoe UI", 16, "bold"))
        style.configure("Section.TLabel", font=("Segoe UI", 10, "bold"))

        self._build_ui()

    def _build_ui(self):
        root = self.root

        # ═══════════════════════════════════════
        # Title Bar
        # ═══════════════════════════════════════
        title_frame = ttk.Frame(root, padding=(20, 10))
        title_frame.pack(fill="x")

        ttk.Label(
            title_frame, text="IS Claim Automation",
            style="Title.TLabel"
        ).pack(side="left")

        ttk.Label(
            title_frame, text="v1.0",
            font=("Segoe UI", 9), foreground="gray"
        ).pack(side="left", padx=10, anchor="s")

        # ═══════════════════════════════════════
        # Main Content Frame
        # ═══════════════════════════════════════
        content = ttk.Frame(root, padding=(20, 5, 20, 10))
        content.pack(fill="both", expand=True)

        # ── Row 1: Profile Selection ──
        profile_frame = ttk.LabelFrame(content, text="Profile", padding=10)
        profile_frame.pack(fill="x", pady=5)

        profile_row = ttk.Frame(profile_frame)
        profile_row.pack(fill="x")

        ttk.Label(profile_row, text="Select Profile:").pack(side="left", padx=(0, 10))

        self.profile_var = tk.StringVar()
        self.profile_dropdown = ttk.Combobox(
            profile_row,
            textvariable=self.profile_var,
            values=list_profiles(),
            width=25,
            state="readonly"
        )
        self.profile_dropdown.pack(side="left", padx=5)
        self.profile_dropdown.bind("<<ComboboxSelected>>", self._on_profile_selected)

        ttk.Button(profile_row, text="Create", command=self._create_profile, width=8).pack(side="left", padx=3)
        ttk.Button(profile_row, text="Edit", command=self._edit_profile, width=8).pack(side="left", padx=3)
        ttk.Button(profile_row, text="Delete", command=self._delete_profile, width=8).pack(side="left", padx=3)
        ttk.Button(profile_row, text="Refresh", command=self._refresh_profiles, width=8).pack(side="left", padx=3)

        # Profile info label
        self.profile_info = ttk.Label(profile_frame, text="No profile selected", foreground="gray")
        self.profile_info.pack(anchor="w", pady=(5, 0))

        # ── Row 2: Excel Upload ──
        excel_frame = ttk.LabelFrame(content, text="Excel File", padding=10)
        excel_frame.pack(fill="x", pady=5)

        excel_row = ttk.Frame(excel_frame)
        excel_row.pack(fill="x")

        ttk.Button(excel_row, text="Browse...", command=self._upload_excel).pack(side="left", padx=(0, 10))
        self.excel_label = ttk.Label(excel_row, text="No file selected", foreground="gray")
        self.excel_label.pack(side="left", fill="x", expand=True)

        # ── Row 3: Execution Settings ──
        settings_frame = ttk.LabelFrame(content, text="Execution Settings", padding=10)
        settings_frame.pack(fill="x", pady=5)

        settings_row = ttk.Frame(settings_frame)
        settings_row.pack(fill="x")

        # Mode
        ttk.Label(settings_row, text="Mode:").pack(side="left", padx=(0, 5))
        self.mode_var = tk.StringVar(value="single")
        ttk.Radiobutton(settings_row, text="Single", variable=self.mode_var, value="single").pack(side="left", padx=5)
        ttk.Radiobutton(settings_row, text="Multi (Batch)", variable=self.mode_var, value="multi").pack(side="left", padx=5)

        ttk.Separator(settings_row, orient="vertical").pack(side="left", fill="y", padx=15)

        # Start Row
        ttk.Label(settings_row, text="Start Row:").pack(side="left", padx=(0, 5))
        self.start_row_var = tk.StringVar(value="2")
        start_entry = ttk.Entry(settings_row, textvariable=self.start_row_var, width=6, font=("Segoe UI", 10))
        start_entry.pack(side="left", padx=5)
        ttk.Label(settings_row, text="(2 = first data row)", foreground="gray").pack(side="left", padx=5)

        # ── Row 4: Control Buttons ──
        btn_frame = ttk.Frame(content)
        btn_frame.pack(fill="x", pady=10)

        self.start_btn = tk.Button(
            btn_frame, text="▶  START AUTOMATION", bg="#27ae60", fg="white",
            font=("Segoe UI", 11, "bold"), padx=20, pady=8,
            command=self._start_automation, cursor="hand2",
            activebackground="#219a52"
        )
        self.start_btn.pack(side="left", padx=5)

        self.stop_btn = tk.Button(
            btn_frame, text="■  STOP", bg="#c0392b", fg="white",
            font=("Segoe UI", 11, "bold"), padx=20, pady=8,
            command=self._stop_automation, state="disabled", cursor="hand2",
            activebackground="#a93226"
        )
        self.stop_btn.pack(side="left", padx=5)

        self.status_label = ttk.Label(btn_frame, text="Ready", foreground="green",
                                       font=("Segoe UI", 10))
        self.status_label.pack(side="left", padx=20)

        # ── Row 5: Live Logs ──
        log_frame = ttk.LabelFrame(content, text="Live Logs", padding=5)
        log_frame.pack(fill="both", expand=True, pady=5)

        log_container = ttk.Frame(log_frame)
        log_container.pack(fill="both", expand=True)

        self.log_text = tk.Text(
            log_container, height=15, bg="#1e1e1e", fg="#d4d4d4",
            font=("Consolas", 9), insertbackground="white",
            selectbackground="#264f78", wrap="word", state="disabled"
        )
        log_scrollbar = ttk.Scrollbar(log_container, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scrollbar.set)

        self.log_text.pack(side="left", fill="both", expand=True)
        log_scrollbar.pack(side="right", fill="y")

        log_btn_frame = ttk.Frame(log_frame)
        log_btn_frame.pack(fill="x", pady=(5, 0))
        ttk.Button(log_btn_frame, text="Clear Logs", command=self._clear_logs).pack(side="right")

        # Tag colors
        self.log_text.tag_configure("error", foreground="#e74c3c")
        self.log_text.tag_configure("success", foreground="#2ecc71")
        self.log_text.tag_configure("warning", foreground="#f39c12")
        self.log_text.tag_configure("info", foreground="#d4d4d4")
        self.log_text.tag_configure("header", foreground="#3498db", font=("Consolas", 9, "bold"))

    # ═══════════════════════════════════════════════════════════════
    # Profile Management
    # ═══════════════════════════════════════════════════════════════

    def _refresh_profiles(self):
        profiles = list_profiles()
        self.profile_dropdown.configure(values=profiles)
        if self.profile_var.get() not in profiles:
            self.profile_var.set("")
            self.profile_info.configure(text="No profile selected", foreground="gray")

    def _on_profile_selected(self, event=None):
        name = self.profile_var.get()
        if not name:
            return
        try:
            data = load_profile(name)
            info_parts = []
            if data.get("financial_year"):
                info_parts.append(f"FY: {data['financial_year']}")
            if data.get("claim_type"):
                info_parts.append(f"Type: {data['claim_type']}")
            if data.get("claim_status"):
                info_parts.append(f"Status: {data['claim_status']}")
            if data.get("submission_type"):
                info_parts.append(f"Submission: {data['submission_type']}")

            self.profile_info.configure(
                text=" | ".join(info_parts) if info_parts else "Profile loaded",
                foreground="#2c3e50"
            )
        except Exception:
            self.profile_info.configure(text="Could not load profile info", foreground="red")

    def _create_profile(self):
        CreateProfileWindow(self.root, on_save_callback=self._on_profile_saved)

    def _edit_profile(self):
        name = self.profile_var.get()
        if not name:
            messagebox.showwarning("Warning", "Select a profile to edit")
            return
        CreateProfileWindow(self.root, profile_name=name, on_save_callback=self._on_profile_saved)

    def _delete_profile(self):
        name = self.profile_var.get()
        if not name:
            messagebox.showwarning("Warning", "Select a profile to delete")
            return
        if messagebox.askyesno("Confirm Delete", f"Delete profile '{name}'?"):
            delete_profile(name)
            self._refresh_profiles()
            self.profile_info.configure(text="Profile deleted", foreground="gray")

    def _on_profile_saved(self, profile_name):
        self._refresh_profiles()
        self.profile_var.set(profile_name)
        self._on_profile_selected()

    # ═══════════════════════════════════════════════════════════════
    # Excel Upload
    # ═══════════════════════════════════════════════════════════════

    def _upload_excel(self):
        path = filedialog.askopenfilename(
            title="Select Excel File",
            filetypes=[("Excel Files", "*.xlsx *.xls"), ("All Files", "*.*")]
        )
        if path:
            self.excel_path = path
            basename = os.path.basename(path)
            self.excel_label.configure(text=f"  {basename}", foreground="#2c3e50")

    # ═══════════════════════════════════════════════════════════════
    # Automation Control
    # ═══════════════════════════════════════════════════════════════

    def _start_automation(self):
        profile_name = self.profile_var.get()
        if not profile_name:
            messagebox.showerror("Error", "Please select a profile")
            return

        if not self.excel_path:
            messagebox.showerror("Error", "Please upload an Excel file")
            return

        if not os.path.exists(self.excel_path):
            messagebox.showerror("Error", "Excel file not found")
            return

        try:
            start_row = int(self.start_row_var.get())
            if start_row < 2:
                messagebox.showerror("Error", "Start row must be 2 or greater")
                return
        except ValueError:
            messagebox.showerror("Error", "Start row must be a valid number")
            return

        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.status_label.configure(text="Running...", foreground="#3498db")
        self.is_running = True
        self._stop_requested = False
        self.stop_event.clear()
        self.browser_ref.clear()

        self.worker_thread = threading.Thread(
            target=self._run_automation,
            args=(profile_name, start_row),
            daemon=True
        )
        self.worker_thread.start()
        self._monitor_thread()

    def _run_automation(self, profile_name: str, start_row: int):
        try:
            profile = load_profile(profile_name)
            run(
                profile=profile,
                profile_name=profile_name,
                excel_path=self.excel_path,
                mode=self.mode_var.get(),
                start_row=start_row,
                stop_event=self.stop_event,
                log_callback=self._log_message,
                captcha_callback=self.captcha_handler.request_captcha,
                browser_ref=self.browser_ref,
            )
        except Exception as e:
            self._log_message(f"FATAL ERROR: {str(e)}")

    def _monitor_thread(self):
        if self.worker_thread and self.worker_thread.is_alive():
            self.root.after(500, self._monitor_thread)
        else:
            self._on_automation_finished()

    def _do_force_kill(self):
        try:
            force_kill_browser(self.browser_ref)
            self._log_message("[FORCE STOP] Browser process killed.")
        except Exception as e:
            self._log_message(f"[FORCE STOP] Error during kill: {e}")

        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=5)

        self.root.after(0, self._force_reset_ui)

    def _force_reset_ui(self):
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled", text="■  STOP", bg="#c0392b")
        self.is_running = False
        self._stop_requested = False
        self.browser_ref.clear()
        self.status_label.configure(text="Stopped (force)", foreground="#e67e22")

    def _on_automation_finished(self):
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled", text="■  STOP", bg="#c0392b")
        self.is_running = False
        self._stop_requested = False
        self.browser_ref.clear()

        if self.stop_event.is_set():
            self.status_label.configure(text="Stopped", foreground="#e67e22")
        else:
            self.status_label.configure(text="Completed", foreground="#27ae60")

    def _stop_automation(self):
        if not self._stop_requested:
            self._stop_requested = True
            self.stop_event.set()
            self.status_label.configure(text="Stopping...", foreground="#e67e22")
            self.stop_btn.configure(text="■  FORCE STOP", bg="#8e44ad")
            self._log_message("[STOP] Graceful stop requested — click FORCE STOP to kill immediately.")
        else:
            self._log_message("[FORCE STOP] Killing browser process immediately...")
            self.status_label.configure(text="Force stopping...", foreground="#c0392b")
            threading.Thread(target=self._do_force_kill, daemon=True).start()

    # ═══════════════════════════════════════════════════════════════
    # Logging
    # ═══════════════════════════════════════════════════════════════

    def _log_message(self, message: str):
        def _insert():
            self.log_text.configure(state="normal")

            tag = "info"
            msg_upper = message.upper()
            if "ERROR" in msg_upper or "FATAL" in msg_upper:
                tag = "error"
            elif "COMPLETED" in msg_upper or "SUCCESS" in msg_upper:
                tag = "success"
            elif "WARNING" in msg_upper:
                tag = "warning"
            elif "═" in message or "Processing Row" in message:
                tag = "header"

            self.log_text.insert(tk.END, message + "\n", tag)
            self.log_text.see(tk.END)
            self.log_text.configure(state="disabled")

        self.root.after(0, _insert)

    def _clear_logs(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state="disabled")


def launch():
    """Entry point to launch the IS Claim Automation application."""
    root = tk.Tk()
    app = ISClaimAutomationApp(root)
    root.mainloop()
