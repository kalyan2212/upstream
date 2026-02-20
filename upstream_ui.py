"""
upstream_ui.py
==============
Tkinter-based UI for pushing customer records to the data-entry REST API.

Features:
  • Single-record form entry and submit
  • CSV batch upload (Browse → Preview → Push)
  • Live log panel with colour-coded results
  • Configurable API Base URL and API Key

Requirements:
    pip install requests
"""

import csv
import io
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

import requests

# ─── Default Configuration ────────────────────────────────────────────────────
DEFAULT_BASE_URL = "http://localhost:5000"
DEFAULT_API_KEY  = "upstream-app-key-001"

FIELDS = [
    ("first_name", "First Name *"),
    ("last_name",  "Last Name *"),
    ("road",       "Road / Street *"),
    ("city",       "City *"),
    ("state",      "State *"),
    ("zip",        "ZIP Code *"),
    ("country",    "Country *"),
    ("phone",      "Phone *"),
    ("dob",        "Date of Birth (MM/DD/YYYY) *"),
]

CSV_COLUMNS = [f[0] for f in FIELDS]


# ─── API helpers ──────────────────────────────────────────────────────────────

def push_customer(customer: dict, base_url: str, api_key: str) -> dict:
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": api_key,
    }
    response = requests.post(
        f"{base_url}/api/customers",
        json=customer,
        headers=headers,
        timeout=10,
    )
    if response.status_code == 201:
        return response.json()
    raise RuntimeError(f"HTTP {response.status_code}: {response.text}")


def push_batch(customers, base_url, api_key, log_cb, done_cb):
    """Run in a background thread; posts progress via log_cb."""
    ok = 0
    for i, customer in enumerate(customers, start=1):
        log_cb(f"[{i}/{len(customers)}] Pushing {customer.get('first_name','')} "
               f"{customer.get('last_name','')} …", "info")
        try:
            created = push_customer(customer, base_url, api_key)
            log_cb(f"  ✔ Created  id={created['id']}  "
                   f"{created['first_name']} {created['last_name']}", "ok")
            ok += 1
        except RuntimeError as exc:
            log_cb(f"  ✘ Failed: {exc}", "error")
    done_cb(ok, len(customers))


# ─── Main Application ─────────────────────────────────────────────────────────

class UpstreamApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Upstream Data Uploader")
        self.resizable(True, True)
        self.minsize(820, 620)
        self._configure_styles()
        self._build_ui()

    # ── Styles ──────────────────────────────────────────────────────────────

    def _configure_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TNotebook.Tab", padding=[14, 6], font=("Segoe UI", 10))
        style.configure("Header.TLabel",
                        font=("Segoe UI", 11, "bold"), foreground="#1a1a2e")
        style.configure("TButton",
                        font=("Segoe UI", 9), padding=[8, 4])
        style.configure("Accent.TButton",
                        font=("Segoe UI", 9, "bold"),
                        foreground="white",
                        background="#0078d4")
        style.map("Accent.TButton",
                  background=[("active", "#005fa3"), ("disabled", "#adb5bd")])
        style.configure("TEntry", padding=[4, 4])

    # ── Main UI ─────────────────────────────────────────────────────────────

    def _build_ui(self):
        # ── Top: config bar ────────────────────────────────────────────────
        cfg_frame = ttk.LabelFrame(self, text="API Configuration", padding=8)
        cfg_frame.pack(fill="x", padx=12, pady=(10, 4))

        ttk.Label(cfg_frame, text="Base URL:").grid(row=0, column=0, sticky="w", padx=(0, 4))
        self.var_url = tk.StringVar(value=DEFAULT_BASE_URL)
        ttk.Entry(cfg_frame, textvariable=self.var_url, width=36).grid(row=0, column=1, padx=(0, 16))

        ttk.Label(cfg_frame, text="API Key:").grid(row=0, column=2, sticky="w", padx=(0, 4))
        self.var_key = tk.StringVar(value=DEFAULT_API_KEY)
        ttk.Entry(cfg_frame, textvariable=self.var_key, width=30).grid(row=0, column=3, padx=(0, 8))

        # ── Tabs ───────────────────────────────────────────────────────────
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=12, pady=6)

        self._build_single_tab()
        self._build_csv_tab()

        # ── Bottom: log ────────────────────────────────────────────────────
        log_frame = ttk.LabelFrame(self, text="Activity Log", padding=6)
        log_frame.pack(fill="x", padx=12, pady=(0, 10))

        self.log = scrolledtext.ScrolledText(
            log_frame, height=9, state="disabled",
            font=("Consolas", 9), bg="#1e1e2e", fg="#cdd6f4",
            insertbackground="white", relief="flat"
        )
        self.log.pack(fill="both", expand=True)
        self.log.tag_config("ok",    foreground="#a6e3a1")
        self.log.tag_config("error", foreground="#f38ba8")
        self.log.tag_config("info",  foreground="#89b4fa")
        self.log.tag_config("warn",  foreground="#f9e2af")

        btn_clear = ttk.Button(log_frame, text="Clear Log", command=self._clear_log)
        btn_clear.pack(anchor="e", pady=(4, 0))

    # ── Single Record Tab ────────────────────────────────────────────────────

    def _build_single_tab(self):
        tab = ttk.Frame(self.notebook, padding=14)
        self.notebook.add(tab, text="  Single Record  ")

        ttk.Label(tab, text="Enter Customer Details", style="Header.TLabel") \
            .grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 10))

        self.entry_vars = {}
        for idx, (key, label) in enumerate(FIELDS):
            row, col = divmod(idx, 2)
            row += 1  # offset for header
            lbl_col = col * 2
            ent_col = col * 2 + 1

            ttk.Label(tab, text=label).grid(
                row=row, column=lbl_col, sticky="w", padx=(0, 6), pady=4)
            var = tk.StringVar()
            self.entry_vars[key] = var
            entry = ttk.Entry(tab, textvariable=var, width=28)
            entry.grid(row=row, column=ent_col, sticky="ew", padx=(0, 20), pady=4)

        tab.columnconfigure(1, weight=1)
        tab.columnconfigure(3, weight=1)

        btn_row = (len(FIELDS) + 1) // 2 + 2
        btn_frame = ttk.Frame(tab)
        btn_frame.grid(row=btn_row, column=0, columnspan=4, pady=(14, 0), sticky="e")

        ttk.Button(btn_frame, text="Clear Form", command=self._clear_form) \
            .pack(side="left", padx=(0, 8))
        ttk.Button(btn_frame, text="Submit Record", style="Accent.TButton",
                   command=self._submit_single).pack(side="left")

    # ── CSV Batch Tab ────────────────────────────────────────────────────────

    def _build_csv_tab(self):
        tab = ttk.Frame(self.notebook, padding=14)
        self.notebook.add(tab, text="  CSV Batch Upload  ")

        ttk.Label(tab, text="Upload CSV File", style="Header.TLabel") \
            .grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))

        # Expected columns hint
        hint = "Expected columns: " + ", ".join(CSV_COLUMNS)
        ttk.Label(tab, text=hint, foreground="#555", font=("Segoe UI", 8)) \
            .grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 10))

        # File picker row
        ttk.Label(tab, text="CSV File:").grid(row=2, column=0, sticky="w")
        self.var_csv_path = tk.StringVar()
        self.csv_path_entry = ttk.Entry(tab, textvariable=self.var_csv_path,
                                        state="readonly", width=52)
        self.csv_path_entry.grid(row=2, column=1, sticky="ew", padx=(6, 6))
        ttk.Button(tab, text="Browse…", command=self._browse_csv) \
            .grid(row=2, column=2, sticky="w")
        tab.columnconfigure(1, weight=1)

        # Preview area
        ttk.Label(tab, text="Preview (first 5 rows):") \
            .grid(row=3, column=0, columnspan=3, sticky="w", pady=(12, 4))

        preview_frame = ttk.Frame(tab)
        preview_frame.grid(row=4, column=0, columnspan=3, sticky="nsew")
        tab.rowconfigure(4, weight=1)

        self.tree = ttk.Treeview(preview_frame, show="headings", height=6)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(preview_frame, orient="horizontal",
                                  command=self.tree.xview)
        self.tree.configure(xscrollcommand=scrollbar.set)
        scrollbar.pack(side="bottom", fill="x")

        # Row count / actions
        self.var_row_count = tk.StringVar(value="No file loaded.")
        ttk.Label(tab, textvariable=self.var_row_count, foreground="#444") \
            .grid(row=5, column=0, columnspan=2, sticky="w", pady=(8, 0))

        self.btn_push_csv = ttk.Button(
            tab, text="Push All Records", style="Accent.TButton",
            command=self._push_csv, state="disabled")
        self.btn_push_csv.grid(row=5, column=2, sticky="e", pady=(8, 0))

        self._csv_data: list[dict] = []

    # ── Actions ──────────────────────────────────────────────────────────────

    def _clear_form(self):
        for var in self.entry_vars.values():
            var.set("")

    def _submit_single(self):
        customer = {key: var.get().strip() for key, var in self.entry_vars.items()}
        missing = [label for key, label in FIELDS if not customer.get(key)]
        if missing:
            messagebox.showwarning("Missing Fields",
                                   "Please fill in:\n" + "\n".join(missing))
            return

        self._log(f"Submitting {customer['first_name']} {customer['last_name']} …", "info")
        base_url = self.var_url.get().rstrip("/")
        api_key  = self.var_key.get().strip()

        def task():
            try:
                created = push_customer(customer, base_url, api_key)
                self._log(f"✔ Created  id={created['id']}  "
                          f"{created['first_name']} {created['last_name']}", "ok")
                self.after(0, lambda: messagebox.showinfo(
                    "Success",
                    f"Customer created!\nID: {created['id']}\n"
                    f"Name: {created['first_name']} {created['last_name']}"))
            except Exception as exc:
                self._log(f"✘ {exc}", "error")
                self.after(0, lambda: messagebox.showerror("Error", str(exc)))

        threading.Thread(target=task, daemon=True).start()

    def _browse_csv(self):
        path = filedialog.askopenfilename(
            title="Select CSV file",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if not path:
            return
        self.var_csv_path.set(path)
        self._load_csv(path)

    def _load_csv(self, path: str):
        try:
            with open(path, newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
        except Exception as exc:
            messagebox.showerror("CSV Error", f"Could not read file:\n{exc}")
            return

        if not rows:
            messagebox.showwarning("Empty File", "The CSV file contains no data rows.")
            return

        # Validate columns
        missing_cols = [c for c in CSV_COLUMNS if c not in rows[0]]
        if missing_cols:
            messagebox.showwarning(
                "Missing Columns",
                "CSV is missing required columns:\n" + ", ".join(missing_cols))

        self._csv_data = [{col: row.get(col, "").strip() for col in CSV_COLUMNS}
                          for row in rows]
        self._populate_preview(self._csv_data)
        total = len(self._csv_data)
        self.var_row_count.set(f"{total} record{'s' if total!=1 else ''} loaded.")
        self.btn_push_csv["state"] = "normal"
        self._log(f"Loaded {total} records from: {path}", "info")

    def _populate_preview(self, data: list[dict]):
        self.tree.delete(*self.tree.get_children())
        cols = CSV_COLUMNS
        self.tree["columns"] = cols
        for col in cols:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=110, minwidth=80, stretch=False)
        for row in data[:5]:
            self.tree.insert("", "end", values=[row.get(c, "") for c in cols])

    def _push_csv(self):
        if not self._csv_data:
            return
        base_url = self.var_url.get().rstrip("/")
        api_key  = self.var_key.get().strip()

        self.btn_push_csv["state"] = "disabled"
        self._log(f"─── Starting batch push of {len(self._csv_data)} records ───", "warn")

        def done(ok, total):
            self._log(
                f"─── Batch complete: {ok}/{total} records pushed successfully ───",
                "ok" if ok == total else "warn")
            self.after(0, lambda: (
                messagebox.showinfo(
                    "Batch Complete",
                    f"{ok} of {total} records pushed successfully."),
                self.btn_push_csv.__setitem__("state", "normal")
            ))

        threading.Thread(
            target=push_batch,
            args=(self._csv_data, base_url, api_key, self._log, done),
            daemon=True
        ).start()

    # ── Log helpers ──────────────────────────────────────────────────────────

    def _log(self, message: str, tag: str = "info"):
        """Thread-safe log append."""
        def _append():
            self.log["state"] = "normal"
            self.log.insert("end", message + "\n", tag)
            self.log.see("end")
            self.log["state"] = "disabled"
        self.after(0, _append)

    def _clear_log(self):
        self.log["state"] = "normal"
        self.log.delete("1.0", "end")
        self.log["state"] = "disabled"


# ─── Entry point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = UpstreamApp()
    app.mainloop()
