#!/usr/bin/env python3

from pathlib import Path
from typing import List


def list_printers() -> List[dict]:
    try:
        import win32print
    except ImportError:
        return [{"name": "默认打印机", "is_default": True}]

    printers = []
    default_printer = None
    try:
        default_printer = win32print.GetDefaultPrinter()
    except Exception:
        pass

    try:
        for printer_info in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS):
            name = printer_info[2]
            printers.append({
                "name": name,
                "is_default": name == default_printer,
            })
    except Exception:
        pass

    if not printers and default_printer:
        printers.append({"name": default_printer, "is_default": True})

    return printers


def _print_pdf(pdf_path: Path, printer_name: str, copies: int = 1) -> dict:
    try:
        import win32api

        win32api.ShellExecute(
            0,
            "print",
            str(pdf_path),
            f'/d:"{printer_name}"',
            ".",
            0,
        )
        return {"filename": pdf_path.name, "status": "printed"}
    except Exception as e:
        return {"filename": pdf_path.name, "status": "failed", "error": str(e)}


def process_print(folder_path: Path, printer_name: str, copies: int = 1, emitter=None) -> dict:
    config_exts = {".pdf"}

    all_files = [p for p in folder_path.rglob("*") if p.is_file() and p.suffix.lower() in config_exts]
    all_files.sort(key=lambda p: p.name)

    total = len(all_files)
    results: List[dict] = []
    printed_count = 0
    failed_count = 0

    for i, pdf_path in enumerate(all_files):
        if emitter:
            emitter.progress("printing", i + 1, total, f"打印: {pdf_path.name}")

        result = _print_pdf(pdf_path, printer_name, copies)
        results.append(result)

        if result["status"] == "printed":
            printed_count += 1
        else:
            failed_count += 1

    return {
        "total_files": total,
        "printed": printed_count,
        "failed": failed_count,
        "printer_used": printer_name,
        "files": results,
    }
