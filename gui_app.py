from __future__ import annotations

import argparse
import json
import logging
import random
import sys
import traceback
from collections import Counter
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from logging.handlers import RotatingFileHandler
from shutil import copyfile
from pathlib import Path
from typing import Any
import tkinter as tk
from tkinter import messagebox, ttk

from print_receipt import build_printer, print_receipt


TWOPLACES = Decimal("0.01")
DEFAULT_CATEGORY_COLORS = {
    "bibite": "#0ea5e9",
    "cibo": "#facc15",
}
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
    BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", BASE_DIR))
else:
    BASE_DIR = Path(__file__).resolve().parent
    BUNDLE_DIR = BASE_DIR

MENU_FILE = BASE_DIR / "menu_config.json"
DEFAULT_MENU_FILE = BUNDLE_DIR / "menu_config.json"
HISTORY_DIR = BASE_DIR / "storico"
LEGACY_SALES_FILE = BASE_DIR / "sales_data.json"
SALES_FILE = HISTORY_DIR / "sales_data.json"
LOG_DIR = BASE_DIR / "logs"
RECEIPTS_DIR = HISTORY_DIR / "receipts"
ICON_ICO_FILE = BASE_DIR / "img" / "icona.ico"
ICON_PNG_FILE = BASE_DIR / "img" / "icona.png"


def resolve_button_color(raw_color: Any, fallback: str) -> str:
    color = str(raw_color or "").strip()
    if len(color) == 7 and color.startswith("#"):
        return color
    return fallback


def pick_text_color(background: str) -> str:
    red = int(background[1:3], 16)
    green = int(background[3:5], 16)
    blue = int(background[5:7], 16)
    luminance = (0.299 * red) + (0.587 * green) + (0.114 * blue)
    return "#1f2937" if luminance >= 186 else "#ffffff"


def decimalize(value: Any) -> Decimal:
    return Decimal(str(value)).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def format_price(value: Decimal, currency_symbol: str = "EUR ", show_currency: bool = True) -> str:
    amount = f"{value:.2f}"
    return f"{currency_symbol}{amount}" if show_currency else amount


def ensure_runtime_files() -> None:
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    if not MENU_FILE.exists() and DEFAULT_MENU_FILE.exists():
        copyfile(DEFAULT_MENU_FILE, MENU_FILE)


def ensure_storage_file() -> None:
    ensure_runtime_files()

    if LEGACY_SALES_FILE.exists() and not SALES_FILE.exists():
        SALES_FILE.write_text(LEGACY_SALES_FILE.read_text(encoding="utf-8"), encoding="utf-8")

    if SALES_FILE.exists():
        return

    SALES_FILE.write_text(
        json.dumps(
            {
                "last_sale_id": 0,
                "sales": [],
                "item_counters": {},
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def apply_window_icon(root: tk.Tk) -> None:
    if ICON_ICO_FILE.exists():
        try:
            root.iconbitmap(default=str(ICON_ICO_FILE))
            return
        except Exception:
            pass

    if ICON_PNG_FILE.exists():
        try:
            icon_image = tk.PhotoImage(file=str(ICON_PNG_FILE))
            root.iconphoto(True, icon_image)
            root._icon_image = icon_image  # type: ignore[attr-defined]
        except Exception:
            pass


def report_startup_error(exc: BaseException) -> None:
    try:
        ensure_runtime_files()
        timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        details = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        with (LOG_DIR / "startup-error.log").open("a", encoding="utf-8") as handle:
            handle.write(f"[{timestamp}]\n{details}\n")
    except Exception:
        pass

    error_text = str(exc).strip() or exc.__class__.__name__
    try:
        temp_root = tk.Tk()
        temp_root.withdraw()
        messagebox.showerror(
            "Errore avvio",
            f"SanBenedettoPOS non e riuscito ad avviarsi.\n\n{error_text}\n\nDettagli salvati in logs\\startup-error.log",
            parent=temp_root,
        )
        temp_root.destroy()
    except Exception:
        pass


def configure_logging() -> logging.Logger:
    logger = logging.getLogger("sanbenedettopos.gui")
    logger.setLevel(logging.INFO)

    if logger.handlers:
        return logger

    handler = RotatingFileHandler(
        LOG_DIR / "movements.log",
        maxBytes=100_000,
        backupCount=5,
        encoding="utf-8",
    )
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False
    return logger


class PosApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("SanBenedettoPOS")
        self.root.geometry("1360x820")
        apply_window_icon(self.root)

        ensure_storage_file()
        self.logger = configure_logging()
        self.menu_config = self.load_menu_config()
        self.sales_data = self.load_sales_data()
        self.current_order: list[dict[str, Any]] = []
        self.price_config = self.menu_config.get("price_display", {})

        self.total_var = tk.StringVar(value=self.format_amount(Decimal("0.00")))
        self.status_var = tk.StringVar(value="Pronto")
        self.history_filter_var = tk.StringVar(value=datetime.now().strftime("%d/%m/%Y"))
        self.daily_total_var = tk.StringVar(value=self.format_amount(Decimal("0.00")))

        self.configure_styles()
        self.build_layout()
        self.refresh_order_view()
        self.refresh_counters_view()
        self.refresh_history_view()
        self.logger.info("APPLICATION_STARTED")

    def load_menu_config(self) -> dict[str, Any]:
        if not MENU_FILE.exists():
            raise SystemExit(
                "File menu_config.json non trovato. Crea il file di configurazione del menu prima di avviare la GUI."
            )

        config = json.loads(MENU_FILE.read_text(encoding="utf-8"))
        menu = config.get("menu")
        if not isinstance(menu, dict) or not menu:
            raise SystemExit("Il file menu_config.json deve contenere la sezione 'menu'.")
        config.setdefault("price_display", {"currency_symbol": "", "show_currency": False})
        config.setdefault("receipt", {})
        config.setdefault("printer", {"enabled": False})
        for category_name, items in menu.items():
            fallback_color = DEFAULT_CATEGORY_COLORS.get(category_name, "#2563eb")
            for item in items:
                item["color"] = resolve_button_color(item.get("color"), fallback_color)
        return config

    def load_sales_data(self) -> dict[str, Any]:
        data = json.loads(SALES_FILE.read_text(encoding="utf-8"))
        data.setdefault("last_sale_id", 0)
        data.setdefault("sales", [])
        data.setdefault("item_counters", {})
        return data

    def save_sales_data(self) -> None:
        SALES_FILE.write_text(
            json.dumps(self.sales_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def configure_styles(self) -> None:
        self.root.configure(bg="#eef3f7")
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Root.TFrame", background="#eef3f7")
        style.configure("Panel.TFrame", background="#f7fafc")
        style.configure("Panel.TLabelframe", background="#f7fafc", borderwidth=0)
        style.configure("Panel.TLabelframe.Label", background="#f7fafc", foreground="#17324d", font=("Segoe UI Semibold", 11))
        style.configure("MenuTitle.TLabel", background="#f7fafc", foreground="#17324d", font=("Segoe UI Semibold", 11))
        style.configure("Shortcut.TLabel", background="#eef3f7", foreground="#5b6b7a", font=("Segoe UI", 9))
        style.configure("Total.TLabel", background="#f7fafc", foreground="#17324d", font=("Segoe UI Semibold", 14))
        style.configure("Primary.TButton", font=("Segoe UI Semibold", 11), padding=(12, 14), background="#16a34a", foreground="#ffffff", borderwidth=0)
        style.configure("Secondary.TButton", font=("Segoe UI", 10), padding=(10, 10), background="#2563eb", foreground="#ffffff", borderwidth=0)
        style.configure("Treeview", rowheight=30, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", font=("Segoe UI Semibold", 10))
        style.map("Primary.TButton", background=[("active", "#15803d")], foreground=[("active", "#ffffff")])
        style.map("Secondary.TButton", background=[("active", "#1d4ed8")], foreground=[("active", "#ffffff")])

    def format_amount(self, value: Decimal) -> str:
        return format_price(
            value,
            currency_symbol=self.price_config.get("currency_symbol", "EUR "),
            show_currency=self.price_config.get("show_currency", True),
        )

    def build_layout(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        main_frame = ttk.Frame(self.root, padding=16, style="Root.TFrame")
        main_frame.grid(sticky="nsew")
        main_frame.columnconfigure(0, weight=7)
        main_frame.columnconfigure(1, weight=3)
        main_frame.columnconfigure(2, weight=3)
        main_frame.rowconfigure(0, weight=1)

        menu_frame = ttk.LabelFrame(main_frame, text="Selezione rapida", style="Panel.TLabelframe")
        menu_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        menu_frame.columnconfigure(0, weight=1)
        menu_frame.rowconfigure(0, weight=1)

        order_frame = ttk.LabelFrame(main_frame, text="Ordine corrente", style="Panel.TLabelframe")
        order_frame.grid(row=0, column=1, sticky="nsew", padx=(0, 10))
        order_frame.columnconfigure(0, weight=1)
        order_frame.rowconfigure(0, weight=1)

        stats_frame = ttk.LabelFrame(main_frame, text="Storico e contatori", style="Panel.TLabelframe")
        stats_frame.grid(row=0, column=2, sticky="nsew")
        stats_frame.columnconfigure(0, weight=1)
        stats_frame.rowconfigure(0, weight=1)

        menu_container = ttk.Frame(menu_frame, padding=10, style="Panel.TFrame")
        menu_container.grid(row=0, column=0, sticky="nsew")
        menu_container.columnconfigure(0, weight=1)
        menu_container.rowconfigure(0, weight=1)
        menu_container.rowconfigure(1, weight=1)

        self.build_menu_section(menu_container, 0, "Bevande", self.menu_config["menu"].get("bibite", []), DEFAULT_CATEGORY_COLORS["bibite"])
        self.build_menu_section(menu_container, 1, "Cibo", self.menu_config["menu"].get("cibo", []), DEFAULT_CATEGORY_COLORS["cibo"])

        self.order_tree = ttk.Treeview(
            order_frame,
            columns=("qty", "name", "price", "total"),
            show="headings",
            height=16,
        )
        self.order_tree.heading("qty", text="Qta")
        self.order_tree.heading("name", text="Articolo")
        self.order_tree.heading("price", text="Prezzo")
        self.order_tree.heading("total", text="Totale")
        self.order_tree.column("qty", width=48, anchor="center")
        self.order_tree.column("name", width=130)
        self.order_tree.column("price", width=75, anchor="e")
        self.order_tree.column("total", width=85, anchor="e")
        self.order_tree.grid(row=0, column=0, sticky="nsew", padx=10, pady=(10, 0))

        order_controls = ttk.Frame(order_frame, padding=(10, 12), style="Panel.TFrame")
        order_controls.grid(row=1, column=0, sticky="ew")
        order_controls.columnconfigure(1, weight=1)
        order_controls.columnconfigure(0, weight=1)
        order_controls.columnconfigure(1, weight=1)

        ttk.Button(order_controls, text="Elimina selezionato", command=self.delete_selected_item, style="Secondary.TButton").grid(
            row=0, column=1, sticky="ew", padx=6
        )
        ttk.Button(order_controls, text="Svuota ordine", command=self.clear_order, style="Secondary.TButton").grid(
            row=0, column=0, sticky="ew", padx=(0, 6)
        )
        ttk.Button(order_controls, text="Conferma e stampa", command=self.finalize_sale, style="Primary.TButton").grid(
            row=1, column=0, columnspan=2, sticky="ew", padx=0, pady=(10, 0)
        )

        total_frame = ttk.Frame(order_frame, padding=(10, 0, 10, 12), style="Panel.TFrame")
        total_frame.grid(row=2, column=0, sticky="ew")
        total_frame.columnconfigure(0, weight=1)
        ttk.Label(total_frame, text="Totale ordine:", style="Total.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(total_frame, textvariable=self.total_var, style="Total.TLabel").grid(row=0, column=1, sticky="e")
        ttk.Label(total_frame, textvariable=self.status_var, foreground="#1f4e79", background="#f7fafc").grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 0))

        stats_notebook = ttk.Notebook(stats_frame)
        stats_notebook.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        counters_tab = ttk.Frame(stats_notebook, padding=4)
        counters_tab.columnconfigure(0, weight=1)
        counters_tab.rowconfigure(0, weight=1)
        history_tab = ttk.Frame(stats_notebook, padding=4)
        history_tab.columnconfigure(0, weight=1)
        history_tab.rowconfigure(1, weight=1)

        stats_notebook.add(counters_tab, text="Contatori")
        stats_notebook.add(history_tab, text="Storico")

        self.counters_tree = ttk.Treeview(
            counters_tab,
            columns=("item", "count"),
            show="headings",
            height=20,
        )
        self.counters_tree.heading("item", text="Articolo")
        self.counters_tree.heading("count", text="Venduti")
        self.counters_tree.column("item", width=150)
        self.counters_tree.column("count", width=70, anchor="center")
        self.counters_tree.grid(row=0, column=0, sticky="nsew")

        history_controls = ttk.Frame(history_tab)
        history_controls.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        history_controls.columnconfigure(1, weight=1)
        ttk.Label(history_controls, text="Data (gg/mm/aaaa):").grid(row=0, column=0, sticky="w")
        ttk.Entry(history_controls, textvariable=self.history_filter_var, width=14).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(history_controls, text="Filtra", command=self.refresh_history_view).grid(row=0, column=2, padx=4)
        ttk.Button(history_controls, text="Oggi", command=self.filter_history_today).grid(row=0, column=3)

        self.history_tree = ttk.Treeview(
            history_tab,
            columns=("sale_id", "timestamp", "items", "total"),
            show="headings",
            height=16,
        )
        self.history_tree.heading("sale_id", text="ID")
        self.history_tree.heading("timestamp", text="Ora")
        self.history_tree.heading("items", text="Articoli")
        self.history_tree.heading("total", text="Totale")
        self.history_tree.column("sale_id", width=50, anchor="center")
        self.history_tree.column("timestamp", width=135)
        self.history_tree.column("items", width=70, anchor="center")
        self.history_tree.column("total", width=90, anchor="e")
        self.history_tree.grid(row=1, column=0, sticky="nsew")

        ttk.Label(history_tab, text="Incasso giorno:", font=("Segoe UI", 10, "bold")).grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Label(history_tab, textvariable=self.daily_total_var, font=("Segoe UI", 10, "bold")).grid(row=3, column=0, sticky="w")

    def build_menu_section(self, parent: ttk.Frame, row_index: int, title: str, items: list[dict[str, Any]], fallback_color: str) -> None:
        section = ttk.LabelFrame(parent, text=title, padding=10, style="Panel.TLabelframe")
        section.grid(row=row_index, column=0, sticky="nsew", pady=(0, 10) if row_index == 0 else (0, 0))
        section.columnconfigure(0, weight=1)

        grid = ttk.Frame(section, style="Panel.TFrame")
        grid.grid(row=0, column=0, sticky="nsew")
        for index, item in enumerate(items):
            label = f"{item['name']}\n{self.format_amount(decimalize(item['price']))}"
            button = ttk.Button(
                grid,
                text=label,
                command=lambda selected=item: self.add_item(selected),
                style=self.get_button_style(resolve_button_color(item.get("color"), fallback_color)),
            )
            row = index // 3
            column = index % 3
            grid.columnconfigure(column, weight=1)
            button.grid(row=row, column=column, sticky="nsew", padx=7, pady=7)

    def get_button_style(self, color: str) -> str:
        style_name = f"Menu{color[1:].upper()}.TButton"
        style = ttk.Style()
        if not style.configure(style_name):
            foreground = pick_text_color(color)
            style.configure(
                style_name,
                font=("Segoe UI Semibold", 11),
                padding=(14, 18),
                background=color,
                foreground=foreground,
                borderwidth=0,
            )
            style.map(
                style_name,
                background=[("active", color)],
                foreground=[("active", foreground)],
            )
        return style_name

    def add_item(self, item: dict[str, Any]) -> None:
        for order_item in self.current_order:
            if order_item["name"] == item["name"]:
                order_item["qty"] += 1
                break
        else:
            self.current_order.append(
                {
                    "name": item["name"],
                    "price": decimalize(item["price"]),
                    "qty": 1,
                    "description": item.get("description", ""),
                }
            )

        self.logger.info("ADD_ITEM | name=%s | price=%s", item["name"], item["price"])
        self.status_var.set(f"Aggiunto: {item['name']}")
        self.refresh_order_view()

    def delete_selected_item(self) -> None:
        selection = self.order_tree.selection()
        if not selection:
            self.status_var.set("Nessun articolo selezionato")
            return

        item_id = selection[0]
        index = int(item_id)
        order_item = self.current_order[index]
        self.current_order.pop(index)

        self.logger.info("DELETE_ITEM | name=%s", order_item["name"])
        self.status_var.set(f"Eliminato: {order_item['name']}")
        self.refresh_order_view()

    def clear_order(self) -> None:
        if not self.current_order:
            self.status_var.set("Ordine gia vuoto")
            return

        self.current_order.clear()
        self.logger.info("CLEAR_ORDER")
        self.status_var.set("Ordine svuotato")
        self.refresh_order_view()

    def refresh_order_view(self) -> None:
        for item_id in self.order_tree.get_children():
            self.order_tree.delete(item_id)

        total = Decimal("0.00")
        for index, item in enumerate(self.current_order):
            line_total = (item["price"] * item["qty"]).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
            total += line_total
            self.order_tree.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    item["qty"],
                    item["name"],
                    self.format_amount(item["price"]),
                    self.format_amount(line_total),
                ),
            )

        self.total_var.set(self.format_amount(total))

    def refresh_counters_view(self) -> None:
        for item_id in self.counters_tree.get_children():
            self.counters_tree.delete(item_id)

        counters = Counter(self.sales_data.get("item_counters", {}))
        for name, count in counters.most_common():
            self.counters_tree.insert("", "end", values=(name, count))

    def filter_history_today(self) -> None:
        self.history_filter_var.set(datetime.now().strftime("%d/%m/%Y"))
        self.refresh_history_view()

    def refresh_history_view(self) -> None:
        for item_id in self.history_tree.get_children():
            self.history_tree.delete(item_id)

        filtered_total = Decimal("0.00")
        filter_date = self.history_filter_var.get().strip()
        for sale in reversed(self.sales_data.get("sales", [])):
            if filter_date and not str(sale.get("timestamp", "")).startswith(filter_date):
                continue

            sale_total = decimalize(sale.get("total", 0))
            filtered_total += sale_total
            item_count = sum(int(item.get("qty", 0)) for item in sale.get("items", []))
            self.history_tree.insert(
                "",
                "end",
                values=(
                    sale.get("sale_id", ""),
                    sale.get("timestamp", ""),
                    item_count,
                    self.format_amount(sale_total),
                ),
            )

        self.daily_total_var.set(self.format_amount(filtered_total))

    def finalize_sale(self) -> None:
        if not self.current_order:
            messagebox.showwarning("Ordine vuoto", "Aggiungi almeno un articolo prima di confermare.")
            self.logger.info("CONFIRM_ATTEMPT_EMPTY_ORDER")
            return

        try:
            sale_id = self.sales_data["last_sale_id"] + 1
            timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            sale_items: list[dict[str, Any]] = []
            total = Decimal("0.00")

            for item in self.current_order:
                line_total = (item["price"] * item["qty"]).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
                total += line_total
                sale_items.append(
                    {
                        "name": item["name"],
                        "qty": item["qty"],
                        "price": float(item["price"]),
                        "description": item["description"],
                    }
                )

            sale_record = {
                "sale_id": sale_id,
                "timestamp": timestamp,
                "items": sale_items,
                "total": float(total),
            }

            self.sales_data["last_sale_id"] = sale_id
            self.sales_data["sales"].append(sale_record)

            counters = self.sales_data.setdefault("item_counters", {})
            for item in sale_items:
                counters[item["name"]] = counters.get(item["name"], 0) + item["qty"]

            self.save_sales_data()
            receipt_payload = self.build_receipt_payload(sale_record)
            self.write_receipt_snapshot(sale_record, receipt_payload)
            self.try_print_receipt(receipt_payload)

            self.logger.info(
                "SALE_COMPLETED | sale_id=%s | items=%s | total=%s",
                sale_id,
                len(sale_items),
                total,
            )

            self.current_order.clear()
            self.refresh_order_view()
            self.refresh_counters_view()
            self.refresh_history_view()
            if self.menu_config.get("printer", {}).get("enabled", False):
                self.status_var.set(f"Vendita registrata e inviata in stampa: #{sale_id}")
            else:
                self.status_var.set(f"Vendita registrata: #{sale_id}")
        except Exception as exc:
            self.logger.exception("SALE_FAILED")
            self.status_var.set("Errore durante la registrazione della vendita")
            messagebox.showerror("Errore vendita", str(exc))

    def build_receipt_payload(self, sale_record: dict[str, Any]) -> dict[str, Any]:
        receipt_config = self.menu_config.get("receipt", {})
        phrases = receipt_config.get("effect_phrases", [])
        selected_phrase = random.choice(phrases) if phrases else ""

        return {
            "receipt_title": receipt_config.get("title", self.menu_config.get("store_name", "Festa di paese")),
            "address": self.menu_config.get("address", ""),
            "order_id": f"{sale_record['sale_id']:05d}",
            "timestamp": sale_record["timestamp"],
            "show_time": receipt_config.get("show_time", True),
            "time_label": receipt_config.get("time_label", "Ora"),
            "items": sale_record["items"],
            "discount": 0,
            "tax": 0,
            "show_subtotal": receipt_config.get("show_subtotal", False),
            "show_unit_price": receipt_config.get("show_unit_price", False),
            "subtotal_label": receipt_config.get("subtotal_label", "Subtotale"),
            "total_label": receipt_config.get("total_label", "Totale"),
            "unit_price_label": receipt_config.get("unit_price_label", "Prezzo"),
            "currency_symbol": self.price_config.get("currency_symbol", ""),
            "show_currency": self.price_config.get("show_currency", False),
            "highlight_phrase": selected_phrase,
            "notes": receipt_config.get("notes", []),
            "footer": receipt_config.get("footer", "Buona festa!"),
        }

    def write_receipt_snapshot(self, sale_record: dict[str, Any], receipt_payload: dict[str, Any]) -> None:
        receipt_file = RECEIPTS_DIR / f"receipt_{sale_record['sale_id']:05d}.json"
        receipt_file.write_text(
            json.dumps(receipt_payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def try_print_receipt(self, receipt_payload: dict[str, Any]) -> None:
        printer_config = self.menu_config.get("printer", {})
        if not printer_config.get("enabled", False):
            self.logger.info("PRINT_SKIPPED | reason=disabled_in_config")
            return

        args = argparse.Namespace(
            connection=printer_config.get("connection"),
            vendor_id=self.parse_config_int(printer_config.get("vendor_id")),
            product_id=self.parse_config_int(printer_config.get("product_id")),
            in_ep=self.parse_config_int(printer_config.get("in_ep", 0x82)),
            out_ep=self.parse_config_int(printer_config.get("out_ep", 0x01)),
            timeout=int(printer_config.get("timeout", 0)),
            port=printer_config.get("port"),
            baudrate=int(printer_config.get("baudrate", 9600)),
            bytesize=int(printer_config.get("bytesize", 8)),
            parity=printer_config.get("parity", "N"),
            stopbits=int(printer_config.get("stopbits", 1)),
            host=printer_config.get("host"),
            printer_port=int(printer_config.get("printer_port", 9100)),
            printer_name=printer_config.get("printer_name"),
        )

        try:
            printer = build_printer(args)
            try:
                print_receipt(printer, receipt_payload, no_cut=bool(printer_config.get("no_cut", False)))
            finally:
                try:
                    printer.close()
                except Exception:
                    pass
            self.logger.info("PRINT_COMPLETED | order_id=%s", receipt_payload.get("order_id"))
            self.status_var.set(f"Vendita registrata e stampata: {receipt_payload.get('order_id')}")
        except Exception as exc:
            self.logger.exception("PRINT_FAILED | order_id=%s", receipt_payload.get("order_id"))
            self.status_var.set("Vendita registrata, stampa non riuscita")
            messagebox.showwarning("Stampa non riuscita", str(exc))

    @staticmethod
    def parse_config_int(value: Any) -> int | None:
        if value in (None, ""):
            return None
        if isinstance(value, int):
            return value
        return int(str(value), 0)


def main() -> None:
    root: tk.Tk | None = None
    try:
        root = tk.Tk()
        app = PosApp(root)
        root.minsize(1240, 760)
        root.mainloop()
    except KeyboardInterrupt:
        raise
    except SystemExit as exc:
        if root is not None:
            try:
                root.destroy()
            except Exception:
                pass
        report_startup_error(exc)
        raise
    except Exception as exc:
        if root is not None:
            try:
                root.destroy()
            except Exception:
                pass
        report_startup_error(exc)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()