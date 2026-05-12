#!/usr/bin/env python3

import json
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import requests

from config_loader import _load_config


class CompanyQueryError(Exception):
    def __init__(self, message: str, raw_response: dict = None, recharge_url: str = None):
        self.message = message
        self.raw_response = raw_response
        self.recharge_url = recharge_url
        super().__init__(self.message)


_cancel_flags: Dict[str, bool] = {}
_cancel_lock = threading.Lock()


def request_cancel(task_id: str):
    with _cancel_lock:
        _cancel_flags[task_id] = True


def is_cancelled(task_id: str) -> bool:
    with _cancel_lock:
        return _cancel_flags.get(task_id, False)


def clear_cancel(task_id: str):
    with _cancel_lock:
        _cancel_flags.pop(task_id, None)


def _get_cache_path(excel_path: Path) -> Path:
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    return output_dir / f"company_query_cache_{excel_path.stem}.json"


def _load_cache(cache_path: Path) -> Dict[str, dict]:
    if not cache_path.exists():
        return {}
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {item["original_name"]: item for item in data.get("results", []) if "original_name" in item}
    except Exception:
        return {}


def _save_cache(cache_path: Path, results: List[dict]):
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump({"results": results, "updated_at": datetime.now().isoformat()}, f, ensure_ascii=False, indent=2)


def _is_cache_expired(cache_path: Path, ttl_days: int) -> bool:
    if ttl_days <= 0:
        return True
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        updated_at = data.get("updated_at", "")
        if not updated_at:
            return True
        updated_time = datetime.fromisoformat(updated_at)
        return (datetime.now() - updated_time).days >= ttl_days
    except Exception:
        return True


def load_cached_results(excel_path: str, ttl_days: int = 0) -> List[dict]:
    cache_path = _get_cache_path(Path(excel_path))
    if not cache_path.exists():
        return []
    if _is_cache_expired(cache_path, ttl_days):
        return []
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("results", [])
    except Exception:
        return []


def clear_cache(excel_path: str) -> bool:
    """清除指定 Excel 文件的缓存"""
    cache_path = _get_cache_path(Path(excel_path))
    if cache_path.exists():
        try:
            cache_path.unlink()
            return True
        except Exception:
            return False
    return True  # 缓存文件不存在，视为清除成功


def _get_api_config() -> dict:
    raw = _load_config()
    cq = raw.get("company_query", {})
    return {
        "api_url": cq.get("api_url", ""),
        "userid": cq.get("userid", ""),
        "userkey": cq.get("userkey", ""),
        "request_delay": cq.get("request_delay", 0.5),
        "excel_column_name": cq.get("excel_column_name", "被执行人"),
    }


def query_company_info(company_name: str, config: dict) -> dict:
    headers = {
        "Content-Type": "application/json",
    }
    payload = {
        "userid": config["userid"],
        "userkey": config["userkey"],
        "companyName": company_name,
    }
    response = requests.post(
        config["api_url"],
        headers=headers,
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


def get_company_data(company_name: str, config: dict) -> dict:
    result = query_company_info(company_name, config)
    if result.get("code") != 200:
        # 提取充值链接（如果 API 返回了）
        recharge_url = result.get("data", {}).get("rechargeUrl") or result.get("recharge_url")
        raise CompanyQueryError(
            f"API 返回错误: {result.get('msg', '未知错误')}",
            raw_response=result,
            recharge_url=recharge_url,
        )
    data = result.get("data", {})
    company_data = data.get("companyInfo")
    if not company_data:
        raise CompanyQueryError("未查询到企业数据", raw_response=result)
    return company_data


def format_current_name(company_data: dict) -> str:
    current_name = company_data.get("CompanyName", "")
    history_names = company_data.get("HistoryNames", "")
    if history_names and history_names != current_name:
        return f"{current_name}（曾用名：{history_names}）"
    return current_name


def extract_location(company_data: dict) -> str:
    province = company_data.get("Province", "")
    city = company_data.get("City", "")
    district = company_data.get("District", "")
    return "".join(p for p in [province, city, district] if p)


def _validate_company_result(result: dict) -> tuple[str, str]:
    """
    验证企业查询结果
    返回: (status, error_message)
    - 所有字段都为空 -> failed
    - 部分字段为空 -> warning
    - 所有字段都有值 -> success
    """
    fields = ["current_name", "legal_person", "location", "credit_code"]
    empty_fields = []
    
    for field in fields:
        if not result.get(field):
            empty_fields.append(field)
    
    if len(empty_fields) == len(fields):
        return "failed", "查询结果所有字段均为空"
    elif empty_fields:
        field_names = {
            "current_name": "现用名",
            "legal_person": "法定代表人", 
            "location": "所在地",
            "credit_code": "信用代码"
        }
        missing = "、".join([field_names.get(f, f) for f in empty_fields])
        return "warning", f"缺少字段: {missing}"
    else:
        return "success", ""


def process_single_company(company_name: str, config: dict) -> dict:
    try:
        company_data = get_company_data(company_name, config)
        result = {
            "original_name": company_name,
            "current_name": format_current_name(company_data),
            "legal_person": company_data.get("LegalPerson", ""),
            "location": extract_location(company_data),
            "credit_code": company_data.get("CreditNo", ""),
        }
        
        status, error_msg = _validate_company_result(result)
        result["status"] = status
        if error_msg:
            result["error"] = error_msg
            
        return result
        
    except CompanyQueryError as e:
        result = {
            "original_name": company_name,
            "current_name": "",
            "legal_person": "",
            "location": "",
            "credit_code": "",
            "status": "failed",
            "error": e.message,
        }
        if e.recharge_url:
            result["recharge_url"] = e.recharge_url
        return result
    except Exception as e:
        return {
            "original_name": company_name,
            "current_name": "",
            "legal_person": "",
            "location": "",
            "credit_code": "",
            "status": "failed",
            "error": str(e),
        }


def process_company_query(
    excel_path: Path,
    range_start: int = 1,
    range_end: int = 99999,
    cache_ttl_days: int = 0,
    task_id: str = "",
    emitter=None,
) -> dict:
    config = _get_api_config()
    column_name = config["excel_column_name"]
    cache_path = _get_cache_path(excel_path)

    clear_cancel(task_id)

    df = pd.read_excel(excel_path, dtype=str)
    if column_name not in df.columns:
        raise ValueError(f"Excel 中缺少 '{column_name}' 列，可用列: {list(df.columns)}")

    all_names = df[column_name].dropna().tolist()

    start_idx = max(0, range_start - 1)
    end_idx = len(all_names) if range_end >= 99999 else min(range_end, len(all_names))
    company_names = all_names[start_idx:end_idx]

    total = len(company_names)

    raw_cache = _load_cache(cache_path)
    cache: Dict[str, dict] = {}
    if cache_ttl_days > 0 and not _is_cache_expired(cache_path, cache_ttl_days):
        cache = raw_cache
    results: List[dict] = []
    skipped = 0

    for i, name in enumerate(company_names):
        if is_cancelled(task_id):
            if emitter:
                emitter.log("warn", f"任务已取消，已完成 {len(results)} 条查询")
            break

        row_num = start_idx + i + 1
        if name in cache:
            result = cache[name]
            results.append(result)
            skipped += 1
            if emitter:
                emitter.progress("company_query", i + 1, total, f"[缓存] {name}", detail={"item": result, "row": row_num, "cached": True})
        else:
            if emitter:
                emitter.progress("company_query", i + 1, total, f"查询: {name}")
            result = process_single_company(name, config)
            results.append(result)
            # 只有查询成功才缓存
            if result["status"] == "success":
                cache[name] = result
                if i % 5 == 0 or i == total - 1:
                    _save_cache(cache_path, list(cache.values()))
            if emitter:
                emitter.progress("company_query", i + 1, total, f"完成: {name}", detail={"item": result, "row": row_num, "cached": False})

        if config["request_delay"] > 0 and name not in cache:
            time.sleep(config["request_delay"])

    _save_cache(cache_path, list(cache.values()))

    success_count = sum(1 for r in results if r["status"] == "success")
    warning_count = sum(1 for r in results if r["status"] == "warning")
    fail_count = sum(1 for r in results if r["status"] == "failed")
    cancelled = is_cancelled(task_id)

    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_excel_path = output_dir / f"企业查询结果_{timestamp}.xlsx"

    result_df = df.iloc[start_idx:start_idx + len(results)].copy()
    for col, key in [("现用名", "current_name"), ("法代", "legal_person"), ("所在地", "location"), ("社会信用代码", "credit_code")]:
        if col not in result_df.columns:
            result_df[col] = ""
        values = [r.get(key, "") for r in results]
        if len(values) < len(result_df):
            values += [""] * (len(result_df) - len(values))
        result_df[col] = values[:len(result_df)]

    result_df.to_excel(str(output_excel_path), index=False)
    clear_cancel(task_id)

    return {
        "total": total,
        "success_count": success_count,
        "warning_count": warning_count,
        "fail_count": fail_count,
        "skipped_cached": skipped,
        "cancelled": cancelled,
        "companies": results,
        "output_excel_path": str(output_excel_path),
    }
