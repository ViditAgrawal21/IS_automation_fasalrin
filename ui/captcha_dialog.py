"""
Captcha dialog — thread-safe popup for manual captcha entry.
Displays captcha image if available, otherwise asks for manual input.
Communicates between worker thread (automation) and main thread (UI).
"""

import os
import queue
import tkinter as tk
from tkinter import ttk

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


class CaptchaDialog(tk.Toplevel):
    """Modal dialog for captcha entry."""

    def __init__(self, parent, image_path=None):
        super().__init__(parent)
        self.title("Captcha Required")
        self.geometry("450x320")
        self.resizable(False, False)
        self.result = ""

        self.transient(parent)
        self.grab_set()

        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 450) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 320) // 2
        self.geometry(f"+{x}+{y}")

        frame = ttk.Frame(self, padding=20)
        frame.pack(fill="both", expand=True)

        ttk.Label(
            frame, text="Enter Captcha",
            font=("Segoe UI", 14, "bold")
        ).pack(pady=(0, 10))

        if image_path and os.path.exists(image_path) and HAS_PIL:
            try:
                img = Image.open(image_path)
                img.thumbnail((380, 120))
                self._photo = ImageTk.PhotoImage(img)
                img_label = ttk.Label(frame, image=self._photo)
                img_label.pack(pady=10)
            except Exception:
                ttk.Label(
                    frame,
                    text="Please check the browser window for the captcha image",
                    foreground="gray", wraplength=380
                ).pack(pady=10)
        else:
            ttk.Label(
                frame,
                text="Please check the browser window for the captcha image",
                foreground="gray", wraplength=380
            ).pack(pady=10)

        ttk.Label(frame, text="Captcha text:").pack(anchor="w")
        self.entry = ttk.Entry(frame, font=("Consolas", 16), width=25)
        self.entry.pack(pady=5, fill="x")
        self.entry.focus_set()

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(pady=15)

        ttk.Button(btn_frame, text="Submit", command=self._submit).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self._cancel).pack(side="left", padx=5)

        self.entry.bind("<Return>", lambda e: self._submit())
        self.protocol("WM_DELETE_WINDOW", self._cancel)

    def _submit(self):
        self.result = self.entry.get().strip()
        self.destroy()

    def _cancel(self):
        self.result = ""
        self.destroy()


class CaptchaHandler:
    """
    Thread-safe captcha handler that bridges the worker thread and the UI thread.
    """

    def __init__(self, root):
        self.root = root
        self._request_queue = queue.Queue()
        self._response_queue = queue.Queue()
        self._poll()

    def _poll(self):
        try:
            image_path = self._request_queue.get_nowait()
            dialog = CaptchaDialog(self.root, image_path)
            self.root.wait_window(dialog)
            self._response_queue.put(dialog.result or "")
        except queue.Empty:
            pass
        except Exception:
            self._response_queue.put("")
        self.root.after(200, self._poll)

    def request_captcha(self, image_path=None) -> str:
        """
        Request captcha input from the user.
        Called from the WORKER THREAD. Blocks until the user submits.
        """
        self._request_queue.put(image_path)
        return self._response_queue.get()
