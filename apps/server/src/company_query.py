#!/usr/bin/env python3

import json
import time
from datetime import datetime
from pathlib import Path
from typing import List

import pandas as pd
import requests

from config_loader import _load_config


class CompanyQueryError(Exception):
    def __init__(self, message: str, raw_response: dict = None):
        self.message = message
        self.raw_response = raw_response
        super().__init__(self.message)


def _get_coze_config() -> dict:
    raw = _load_config()
    cq = raw.get("company_query", {})
    return {
        "api_url": cq.get("coze_api_url", "https://api.coze.cn/v1/workflow/run"),
        "api_token": cq.get("coze_api_token", ""),
        "workflow_id": cq.get("coze_workflow_id", ""),
        "request_delay": cq.get("request_delay", 0.5),
        "excel_column_name": cq.get("excel_column_name", "被执行人"),
    }


def query_company_info(company_name: str, config: dict) -> dict:
    headers = {
        "Authorization": f"Bearer {config['api_token']}",
        "Content-Type": "application/json",
    }
    payload = {
        "workflow_id": config["workflow_id"],
        "parameters": {"companyName": company_name},
        "is_async": False,
    }
    response = requests.post(
        config["api_url"],
        headers=headers,
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    result = response.json()
    if result.get("code") == 0 and "data" in result and isinstance(result["data"], str):
        try:
            result["data"] = json.loads(result["data"])
        except json.JSONDecodeError:
            pass
    return result


def get_company_data(company_name: str, config: dict) -> dict:
    result = query_company_info(company_name, config)
    if result.get("code") != 0:
        raise CompanyQueryError(
            f"API 返回错误: {result.get('msg', '未知错误')}",
            raw_response=result,
        )
    data = result.get("data", {})
    company_data = data.get("data") if isinstance(data, dict) else None
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


def process_single_company(company_name: str, config: dict) -> dict:
    try:
        company_data = get_company_data(company_name, config)
        return {
            "original_name": company_name,
            "current_name": format_current_name(company_data),
            "legal_person": company_data.get("LegalPerson", ""),
            "location": extract_location(company_data),
            "credit_code": company_data.get("CreditNo", ""),
            "status": "success",
        }
    except CompanyQueryError as e:
        return {
            "original_name": company_name,
            "current_name": "",
            "legal_person": "",
            "location": "",
            "credit_code": "",
            "status": "failed",
            "error": e.message,
        }
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


def process_company_query(excel_path: Path, emitter=None) -> dict:
    config = _get_coze_config()
    column_name = config["excel_column_name"]

    df = pd.read_excel(excel_path, dtype=str)
    if column_name not in df.columns:
        raise ValueError(f"Excel 中缺少 '{column_name}' 列，可用列: {list(df.columns)}")

    company_names = df[column_name].dropna().tolist()
    total = len(company_names)
    results: List[dict] = []

    for i, name in enumerate(company_names):
        if emitter:
            emitter.progress("company_query", i + 1, total, f"查询: {name}")
        result = process_single_company(name, config)
        results.append(result)
        if config["request_delay"] > 0:
            time.sleep(config["request_delay"])

    success_count = sum(1 for r in results if r["status"] == "success")
    fail_count = total - success_count

    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_excel_path = output_dir / f"企业查询结果_{timestamp}.xlsx"

    result_df = df.copy()
    n_results = len(results)
    for col, key in [("现用名", "current_name"), ("法代", "legal_person"), ("所在地", "location"), ("社会信用代码", "credit_code")]:
        if col not in result_df.columns:
            result_df[col] = ""
        values = [r.get(key, "") for r in results]
        if len(values) < len(result_df):
            values += [""] * (len(result_df) - len(values))
        result_df[col] = values[:len(result_df)]

    result_df.to_excel(str(output_excel_path), index=False)

    return {
        "total": total,
        "success_count": success_count,
        "fail_count": fail_count,
        "companies": results,
        "output_excel_path": str(output_excel_path),
    }
