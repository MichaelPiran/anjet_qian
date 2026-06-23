from __future__ import annotations

import argparse
import json
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any


TWOPLACES = Decimal("0.01")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stampa scontrini personalizzati su stampanti termiche ESC/POS."
    )
    parser.add_argument(
        "receipt",
        nargs="?",
        type=Path,
        help="Percorso del file JSON con i dati dello scontrino.",
    )
    parser.add_argument(
        "--connection",
        choices=("usb", "serial", "network", "windows"),
        required=False,
        help="Tipo di connessione verso la stampante.",
    )
    parser.add_argument("--vendor-id", type=parse_int, help="USB Vendor ID, es. 0x0416")
    parser.add_argument("--product-id", type=parse_int, help="USB Product ID, es. 0x5011")
    parser.add_argument("--in-ep", type=parse_int, default=0x82, help="USB IN endpoint")
    parser.add_argument("--out-ep", type=parse_int, default=0x01, help="USB OUT endpoint")
    parser.add_argument("--timeout", type=int, default=0, help="USB timeout in ms")
    parser.add_argument("--port", help="Porta seriale, es. COM3")
    parser.add_argument("--baudrate", type=int, default=9600, help="Baudrate seriale")
    parser.add_argument("--bytesize", type=int, default=8, help="Byte size seriale")
    parser.add_argument("--parity", default="N", help="Parita seriale: N, E, O")
    parser.add_argument("--stopbits", type=int, default=1, help="Stop bits seriale")
    parser.add_argument("--host", help="IP o hostname della stampante di rete")
    parser.add_argument("--printer-port", type=int, default=9100, help="Porta TCP della stampante")
    parser.add_argument(
        "--printer-name",
        help="Nome della stampante installata in Windows per il backend Win32Raw.",
    )
    parser.add_argument(
        "--no-cut",
        action="store_true",
        help="Non invia il comando di taglio carta.",
    )
    parser.add_argument(
        "--list-printers",
        action="store_true",
        help="Elenca le stampanti Windows installate ed esce.",
    )
    return parser.parse_args()


def parse_int(value: str) -> int:
    return int(value, 0)


def load_receipt(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if "items" not in data or not data["items"]:
        raise SystemExit("Il file JSON deve contenere almeno un elemento in 'items'.")
    return data


def decimalize(value: Any) -> Decimal:
    return Decimal(str(value)).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def format_price(value: Decimal, currency_symbol: str = "EUR ", show_currency: bool = True) -> str:
    amount = f"{value:.2f}"
    return f"{currency_symbol}{amount}" if show_currency else amount


def build_printer(args: argparse.Namespace):
    if not args.connection:
        raise SystemExit("Specifica --connection oppure usa --list-printers.")

    if args.connection == "usb":
        try:
            from escpos.printer import Usb  # type: ignore[import-not-found]
        except ImportError as exc:
            raise SystemExit(
                "Manca la dipendenza 'python-escpos'. Installa con: pip install python-escpos pyusb pyserial pywin32"
            ) from exc
        if args.vendor_id is None or args.product_id is None:
            raise SystemExit("Per la connessione USB servono --vendor-id e --product-id.")
        try:
            return Usb(
                args.vendor_id,
                args.product_id,
                timeout=args.timeout,
                in_ep=args.in_ep,
                out_ep=args.out_ep,
            )
        except NotImplementedError as exc:
            raise SystemExit(
                "Il backend USB libusb non riesce ad aprire la stampante su Windows. "
                "Se la stampante e gia installata in Windows, usa --connection windows --printer-name \"NOME STAMPANTE\". "
                "Se vuoi restare su USB diretto, associa alla periferica un driver WinUSB/libusb con Zadig e riprova."
            ) from exc

    if args.connection == "serial":
        try:
            from escpos.printer import Serial  # type: ignore[import-not-found]
        except ImportError as exc:
            raise SystemExit(
                "Manca la dipendenza 'python-escpos'. Installa con: pip install python-escpos pyusb pyserial pywin32"
            ) from exc
        if not args.port:
            raise SystemExit("Per la connessione seriale serve --port, ad esempio COM3.")
        return Serial(
            devfile=args.port,
            baudrate=args.baudrate,
            bytesize=args.bytesize,
            parity=args.parity,
            stopbits=args.stopbits,
            timeout=1.0,
            dsrdtr=True,
        )

    if args.connection == "network":
        try:
            from escpos.printer import Network  # type: ignore[import-not-found]
        except ImportError as exc:
            raise SystemExit(
                "Manca la dipendenza 'python-escpos'. Installa con: pip install python-escpos pyusb pyserial pywin32"
            ) from exc
        if not args.host:
            raise SystemExit("Per la connessione network serve --host.")
        return Network(args.host, port=args.printer_port, timeout=10)

    try:
        from escpos.printer import Win32Raw  # type: ignore[import-not-found]
    except ImportError as exc:
        raise SystemExit(
            "Per --connection windows installa anche pywin32: pip install pywin32"
        ) from exc

    try:
        if args.printer_name:
            return Win32Raw(args.printer_name)
        return Win32Raw()
    except RuntimeError as exc:
        message = str(exc)
        if "win32print" in message:
            raise SystemExit(
                "Il backend Windows richiede pywin32 installato nello stesso Python con cui stai eseguendo lo script. "
                "Esegui: py -m pip install pywin32"
            ) from exc
        raise


def item_total(item: dict[str, Any]) -> Decimal:
    qty = Decimal(str(item.get("qty", 1)))
    price = decimalize(item["price"])
    return (qty * price).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def print_line(printer: Any, left: str, right: str, width: int = 42) -> None:
    safe_right = right[: width - 1]
    remaining = max(width - len(safe_right), 1)
    safe_left = left[:remaining]
    spaces = max(width - len(safe_left) - len(safe_right), 1)
    printer.text(f"{safe_left}{' ' * spaces}{safe_right}\n")


def print_receipt(printer: Any, receipt: dict[str, Any], no_cut: bool) -> None:
    store_name = receipt.get("receipt_title") or receipt.get("store_name", "")
    notes = receipt.get("notes", [])
    order_id = receipt.get("order_id", "")
    timestamp = receipt.get("timestamp") or datetime.now().strftime("%d/%m/%Y %H:%M")
    show_time = receipt.get("show_time", True)
    time_label = receipt.get("time_label", "Ora")
    subtotal_label = receipt.get("subtotal_label", "Subtotale")
    total_label = receipt.get("total_label", "Totale")
    unit_price_label = receipt.get("unit_price_label", "Prezzo")
    currency_symbol = receipt.get("currency_symbol", "EUR ")
    show_currency = receipt.get("show_currency", True)
    show_unit_price = receipt.get("show_unit_price", True)
    show_subtotal = receipt.get("show_subtotal", True)
    highlight_phrase = receipt.get("highlight_phrase", "")
    footer = receipt.get("footer", "")
    item_count = len(receipt["items"])
    extra_item_spacing = 2 if item_count <= 2 else 1 if item_count <= 4 else 0

    printer.set(align="center", bold=True, width=2, height=3)
    printer.text(f"{store_name}\n")
    printer.set(align="center", bold=False, width=1, height=1)
    printer.text("\n")
    if order_id:
        printer.set(align="center", bold=True, width=1, height=3)
        printer.text(f"Scontrino {order_id}\n")
        printer.set(align="center", bold=False, width=1, height=1)
        printer.text("\n")
    printer.text("\n")

    printer.set(align="left")
    if show_time:
        printer.text(f"{time_label}:   {timestamp}\n")
        printer.text("\n")
    printer.text("------------------------------------------\n")
    printer.text("\n")

    subtotal = Decimal("0.00")
    for item in receipt["items"]:
        qty = Decimal(str(item.get("qty", 1)))
        name = str(item["name"])
        price = decimalize(item["price"])
        total = item_total(item)
        subtotal += total
        printer.set(align="left", bold=True, width=1, height=2)
        print_line(printer, f"{qty} x {name}", format_price(total, currency_symbol, show_currency))
        printer.set(align="left", bold=False, width=1, height=1)
        if item.get("description"):
            printer.text(f"  {item['description']}\n")
        if show_unit_price:
            printer.text(
                f"  {unit_price_label}: {format_price(price, currency_symbol, show_currency)}\n"
            )
        printer.text("\n" * extra_item_spacing)

    total_due = subtotal.quantize(TWOPLACES, rounding=ROUND_HALF_UP)

    printer.text("------------------------------------------\n")
    printer.text("\n")
    if show_subtotal:
        print_line(printer, subtotal_label, format_price(subtotal, currency_symbol, show_currency))
    printer.set(bold=True, width=1, height=2)
    print_line(printer, total_label.upper(), format_price(total_due, currency_symbol, show_currency))
    printer.set(bold=False, width=1, height=1)

    if notes:
        printer.text("\n")
        for note in notes:
            printer.text(f"{note}\n")

    highlight_phrase = receipt.get("highlight_phrase", "")
    if highlight_phrase:
        printer.text("\n")
        printer.text("\n")
        printer.set(align="center", bold=True)
        printer.text(f"{highlight_phrase}\n")
        printer.set(align="left", bold=False)

    if footer:
        printer.text("\n")
        printer.text("\n")
        printer.set(align="center")
        printer.text(f"{footer}\n")
        printer.set(align="left")

    if not no_cut:
        printer.cut()


def list_windows_printers() -> None:
    try:
        import win32print  # type: ignore[import-not-found]
    except ImportError as exc:
        raise SystemExit(
            "Per elencare le stampanti Windows installa pywin32: py -m pip install pywin32"
        ) from exc

    printers = win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS)
    if not printers:
        print("Nessuna stampante Windows trovata.")
        return

    print("Stampanti Windows disponibili:")
    for printer in printers:
        printer_name = printer[2]
        print(f"- {printer_name}")


def main() -> None:
    args = parse_args()

    if args.list_printers:
        list_windows_printers()
        return

    if not args.receipt:
        raise SystemExit("Specifica il file JSON dello scontrino oppure usa --list-printers.")

    receipt = load_receipt(args.receipt)
    printer = build_printer(args)
    try:
        print_receipt(printer, receipt, no_cut=args.no_cut)
    finally:
        try:
            printer.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()