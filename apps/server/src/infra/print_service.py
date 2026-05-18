#!/usr/bin/env python3

import time
from pathlib import Path
from typing import List, Optional


# 虚拟打印机名称关键词（这些不是真实物理打印机）
VIRTUAL_PRINTER_KEYWORDS = [
    "pdf", "xps", "onenote", "fax", "microsoft print to pdf",
    "导出为wps pdf", "adobe pdf", "foxit", "pdf24", "cutepdf",
    "bullzip", "primo", "pdfwriter", "image", "file"
]


def _is_virtual_printer(name: str) -> bool:
    """判断是否为虚拟打印机（PDF/XPS/Image 等）"""
    name_lower = name.lower()
    return any(keyword in name_lower for keyword in VIRTUAL_PRINTER_KEYWORDS)


def list_printers(include_virtual: bool = False) -> List[dict]:
    """
    获取系统打印机列表
    
    策略：优先返回物理打印机，如果没有物理打印机则返回虚拟打印机作为备选
    
    Args:
        include_virtual: 是否强制包含虚拟打印机（PDF/XPS等），默认 False
    
    Returns:
        打印机列表，如果没有可用打印机返回空列表
    """
    try:
        import win32print
    except ImportError:
        return []

    physical_printers = []
    virtual_printers = []
    default_printer: Optional[str] = None
    
    try:
        default_printer = win32print.GetDefaultPrinter()
    except Exception:
        pass

    try:
        # 获取本地打印机和网络打印机
        printer_flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
        for printer_info in win32print.EnumPrinters(printer_flags):
            name = printer_info[2]
            is_virtual = _is_virtual_printer(name)
            
            # 检查打印机是否可用
            try:
                handle = win32print.OpenPrinter(name)
                win32print.ClosePrinter(handle)
                
                printer_info_dict = {
                    "name": name,
                    "is_default": name == default_printer,
                    "is_virtual": is_virtual,
                }
                
                if is_virtual:
                    virtual_printers.append(printer_info_dict)
                else:
                    physical_printers.append(printer_info_dict)
            except Exception:
                # 无法打开的打印机跳过
                continue
    except Exception:
        pass

    # 策略：如果有物理打印机，优先返回物理打印机
    # 如果没有物理打印机，返回虚拟打印机作为备选
    if physical_printers:
        return physical_printers
    elif include_virtual or virtual_printers:
        return virtual_printers
    else:
        return []


def list_all_printers() -> List[dict]:
    """获取所有打印机（包括虚拟打印机）"""
    return list_printers(include_virtual=True)


def get_default_printer() -> Optional[str]:
    """获取系统默认打印机名称，如果没有则返回 None"""
    try:
        import win32print
        return win32print.GetDefaultPrinter()
    except Exception:
        return None


def _print_pdf_win32(pdf_path: Path, printer_name: str, copies: int = 1) -> dict:
    """
    使用 Windows API 打印 PDF
    注意：ShellExecute 是异步的，我们只能确认任务是否成功提交到打印队列
    """
    try:
        import win32api
        import win32print
        
        # 首先验证打印机是否存在且可用
        try:
            handle = win32print.OpenPrinter(printer_name)
            win32print.ClosePrinter(handle)
        except Exception as e:
            return {
                "filename": pdf_path.name, 
                "status": "failed", 
                "error": f"打印机不可用: {str(e)}"
            }
        
        # 提交打印任务
        result = win32api.ShellExecute(
            0,
            "print",
            str(pdf_path),
            f'/d:"{printer_name}"',
            ".",
            0,
        )
        
        # ShellExecute 返回值 > 32 表示成功提交
        if result > 32:
            return {
                "filename": pdf_path.name, 
                "status": "submitted",
                "message": "打印任务已提交到队列"
            }
        else:
            return {
                "filename": pdf_path.name, 
                "status": "failed", 
                "error": f"提交打印任务失败 (错误码: {result})"
            }
            
    except Exception as e:
        return {"filename": pdf_path.name, "status": "failed", "error": str(e)}


def process_print(folder_path: Path, printer_name: str, copies: int = 1, emitter=None) -> dict:
    """
    批量打印文件夹中的 PDF 文件
    
    注意：由于 Windows 打印是异步的，此函数只能确认打印任务是否成功提交到队列，
    无法确认实际打印是否成功完成。
    """
    config_exts = {".pdf"}

    all_files = [p for p in folder_path.rglob("*") if p.is_file() and p.suffix.lower() in config_exts]
    all_files.sort(key=lambda p: p.name)

    total = len(all_files)
    results: List[dict] = []
    submitted_count = 0
    failed_count = 0

    for i, pdf_path in enumerate(all_files):
        if emitter:
            emitter.progress("printing", i + 1, total, f"提交打印: {pdf_path.name}")

        result = _print_pdf_win32(pdf_path, printer_name, copies)
        results.append(result)

        if result["status"] == "submitted":
            submitted_count += 1
        else:
            failed_count += 1

    return {
        "total_files": total,
        "submitted": submitted_count,
        "failed": failed_count,
        "printer_used": printer_name,
        "files": results,
        "note": "打印任务已提交到系统队列，实际打印结果请查看打印机状态"
    }


def check_printer_status(printer_name: str) -> dict:
    """检查指定打印机的状态"""
    try:
        import win32print
        
        handle = win32print.OpenPrinter(printer_name)
        try:
            info = win32print.GetPrinter(handle, 2)
            status_code = info['Status']
            
            # 解析状态码
            status_messages = []
            if status_code == 0:
                status_messages.append("就绪")
            if status_code & win32print.PRINTER_STATUS_PAUSED:
                status_messages.append("已暂停")
            if status_code & win32print.PRINTER_STATUS_ERROR:
                status_messages.append("错误")
            if status_code & win32print.PRINTER_STATUS_OFFLINE:
                status_messages.append("离线")
            if status_code & win32print.PRINTER_STATUS_OUT_OF_MEMORY:
                status_messages.append("内存不足")
            if status_code & win32print.PRINTER_STATUS_DOOR_OPEN:
                status_messages.append("打印机盖打开")
            if status_code & win32print.PRINTER_STATUS_NO_TONER:
                status_messages.append("无墨粉")
            if status_code & win32print.PRINTER_STATUS_PAPER_OUT:
                status_messages.append("缺纸")
            if status_code & win32print.PRINTER_STATUS_PAPER_JAM:
                status_messages.append("卡纸")
                
            return {
                "name": printer_name,
                "available": True,
                "status_code": status_code,
                "status": ", ".join(status_messages) if status_messages else "未知",
                "is_ready": status_code == 0
            }
        finally:
            win32print.ClosePrinter(handle)
            
    except Exception as e:
        return {
            "name": printer_name,
            "available": False,
            "error": str(e)
        }
