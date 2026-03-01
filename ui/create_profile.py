"""
Create / Edit Profile dialog for IS Claim Automation.

Sections:
  1. Login Credentials (username, password)
  2. Claim Settings (financial year, claim type, claim status, submission type)

Uses ttk Combobox dropdowns with values from portal constants.
"""

import tkinter as tk
from tkinter import ttk, messagebox

from profile_manager import save_profile, load_profile, profile_exists
from utils.constants import (
    FINANCIAL_YEARS,
    CLAIM_TYPES,
    CLAIM_STATUSES,
    SUBMISSION_TYPES,
)


class CreateProfileWindow(tk.Toplevel):
    """Profile creation/editing dialog for IS Claim Automation."""

    def __init__(self, parent, profile_name=None, on_save_callback=None):
        super().__init__(parent)
        self.title("Edit Profile" if profile_name else "Create Profile")
        self.geometry("520x520")
        self.resizable(False, True)
        self.on_save_callback = on_save_callback

        # Make modal
        self.transient(parent)
        self.grab_set()

        # Center on parent
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 520) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 520) // 2
        self.geometry(f"+{x}+{y}")

        # Scrollable frame
        canvas = tk.Canvas(self)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.scroll_frame = ttk.Frame(canvas, padding=20)

        self.scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self._canvas = canvas
        self._mw_binding = canvas.bind_all(
            "<MouseWheel>",
            lambda e: canvas.yview_scroll(-1 * (e.delta // 120), "units")
        )
        self.bind("<Destroy>", self._on_destroy)

        self._widgets = {}
        self._editing = profile_name
        self._build_form()

        if profile_name:
            self._load_existing(profile_name)

    def _on_destroy(self, event):
        if event.widget is self:
            try:
                self._canvas.unbind_all("<MouseWheel>")
            except Exception:
                pass

    def _build_form(self):
        frame = self.scroll_frame

        # ═══════════════════════════════════════
        # Profile Name
        # ═══════════════════════════════════════
        ttk.Label(frame, text="Profile Name", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 2))
        name_entry = ttk.Entry(frame, width=40, font=("Segoe UI", 10))
        name_entry.pack(fill="x", pady=(0, 15))
        self._widgets["profile_name"] = name_entry

        if self._editing:
            name_entry.insert(0, self._editing)
            name_entry.configure(state="disabled")

        # ═══════════════════════════════════════
        # Section 1: Login Credentials
        # ═══════════════════════════════════════
        self._section_header(frame, "Section 1: Login Credentials")
        self._add_entry(frame, "Username", "username")
        self._add_entry(frame, "Password", "password", show="*")

        # ═══════════════════════════════════════
        # Section 2: Claim Settings
        # ═══════════════════════════════════════
        self._section_header(frame, "Section 2: Claim Settings")
        self._add_combobox(frame, "Financial Year", "financial_year", FINANCIAL_YEARS)
        self._add_combobox(frame, "Claim Type", "claim_type", CLAIM_TYPES)
        self._add_combobox(frame, "Claim Status", "claim_status", CLAIM_STATUSES)
        self._add_combobox(frame, "IS Submission Type", "submission_type", SUBMISSION_TYPES)

        # ═══════════════════════════════════════
        # Buttons
        # ═══════════════════════════════════════
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill="x", pady=20)
        ttk.Button(btn_frame, text="Save Profile", command=self._save).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side="left", padx=5)

    def _section_header(self, parent, text):
        sep = ttk.Separator(parent, orient="horizontal")
        sep.pack(fill="x", pady=(15, 5))
        ttk.Label(parent, text=text, font=("Segoe UI", 11, "bold"),
                  foreground="#1a5276").pack(anchor="w", pady=(0, 10))

    def _add_entry(self, parent, label, key, show=None):
        ttk.Label(parent, text=label, font=("Segoe UI", 9)).pack(anchor="w", pady=(5, 0))
        entry = ttk.Entry(parent, width=40, font=("Segoe UI", 10), show=show or "")
        entry.pack(fill="x", pady=(0, 5))
        self._widgets[key] = entry

    def _add_combobox(self, parent, label, key, values):
        ttk.Label(parent, text=label, font=("Segoe UI", 9)).pack(anchor="w", pady=(5, 0))
        combo = ttk.Combobox(parent, values=values, width=38, font=("Segoe UI", 10), state="normal")
        combo.pack(fill="x", pady=(0, 5))
        self._widgets[key] = combo

    def _load_existing(self, profile_name):
        try:
            data = load_profile(profile_name)
            field_map = {
                "username": "username",
                "password": "password",
                "financial_year": "financial_year",
                "claim_type": "claim_type",
                "claim_status": "claim_status",
                "submission_type": "submission_type",
            }
            for data_key, widget_key in field_map.items():
                value = data.get(data_key, "")
                widget = self._widgets.get(widget_key)
                if widget and value:
                    if isinstance(widget, ttk.Combobox):
                        widget.set(value)
                    else:
                        widget.delete(0, "end")
                        widget.insert(0, value)
        except Exception as e:
            messagebox.showerror("Error", f"Could not load profile: {e}", parent=self)

    def _get_value(self, key):
        widget = self._widgets.get(key)
        if not widget:
            return ""
        return widget.get().strip()

    def _save(self):
        profile_name = self._get_value("profile_name")
        if not profile_name:
            messagebox.showerror("Error", "Profile Name is required", parent=self)
            return

        username = self._get_value("username")
        password = self._get_value("password")

        if not username:
            messagebox.showerror("Error", "Username is required", parent=self)
            return
        if not password:
            messagebox.showerror("Error", "Password is required", parent=self)
            return

        if not self._editing and profile_exists(profile_name):
            messagebox.showerror("Error", f"Profile '{profile_name}' already exists", parent=self)
            return

        data = {
            "username": username,
            "password": password,
            "financial_year": self._get_value("financial_year"),
            "claim_type": self._get_value("claim_type"),
            "claim_status": self._get_value("claim_status"),
            "submission_type": self._get_value("submission_type"),
        }

        try:
            save_profile(profile_name, data)
            messagebox.showinfo("Success", f"Profile '{profile_name}' saved!", parent=self)
            if self.on_save_callback:
                self.on_save_callback(profile_name)
            self.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Could not save profile: {e}", parent=self)
