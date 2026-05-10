#!/usr/bin/env python3
"""
从Coze工作流获取企业信息，填充到Excel中

功能：
1. 读取Excel中的被执行人公司名称
2. 调用Coze API查询企业信息
3. 填充现用名、法代、所在地、社会信用代码

现用名格式：现用名（曾用名：xxxx，如有）
"""

import sys
import json
import time
from pathlib import Path

# 添加src目录到路径
ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / 'apps' / 'server' / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import requests
import pandas as pd

# Coze API 配置
COZE_API_URL = "https://api.coze.cn/v1/workflow/run"
COZE_API_TOKEN = "sat_xo6jKTKmaerCALRXHE7ZrRowHOvHARoplcU0HiYQtARY3QMr4C1MXqUO3FAJFuHA"
WORKFLOW_ID = "7637504045536428084"


class CompanyQueryError(Exception):
    """企业查询错误"""
    def __init__(self, message: str, raw_response: dict = None):
        self.message = message
        self.raw_response = raw_response
        super().__init__(self.message)


def query_company_info(company_name: str) -> dict:
    """调用 Coze 工作流 API 查询企业信息"""
    headers = {
        "Authorization": f"Bearer {COZE_API_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "workflow_id": WORKFLOW_ID,
        "parameters": {
            "companyName": company_name
        },
        "is_async": False
    }

    response = requests.post(
        COZE_API_URL,
        headers=headers,
        json=payload,
        timeout=60
    )

    response.raise_for_status()
    result = response.json()

    # 解析嵌套的 data 字段
    if result.get("code") == 0 and "data" in result and isinstance(result["data"], str):
        try:
            inner_data = json.loads(result["data"])
            result["data"] = inner_data
        except json.JSONDecodeError:
            pass

    return result


def get_company_data(company_name: str) -> dict:
    """
    查询企业信息

    Returns:
        企业数据字典

    Raises:
        CompanyQueryError: 查询失败时抛出
    """
    result = query_company_info(company_name)

    if result.get("code") != 0:
        raise CompanyQueryError(
            f"API 返回错误: {result.get('msg', '未知错误')}",
            raw_response=result
        )

    data = result.get("data", {})
    company_data = data.get("data") if isinstance(data, dict) else None

    if not company_data:
        raise CompanyQueryError(
            "未查询到企业数据",
            raw_response=result
        )

    return company_data


def format_current_name(company_data: dict) -> str:
    """
    格式化现用名
    格式：现用名（曾用名：xxxx）
    """
    current_name = company_data.get("CompanyName", "")
    history_names = company_data.get("HistoryNames", "")

    if history_names and history_names != current_name:
        return f"{current_name}（曾用名：{history_names}）"
    return current_name


def extract_location(company_data: dict) -> str:
    """提取所在地（省市区）"""
    province = company_data.get("Province", "")
    city = company_data.get("City", "")
    district = company_data.get("District", "")

    parts = [p for p in [province, city, district] if p]
    return "".join(parts)


def process_company(company_name: str) -> dict:
    """
    处理单个企业，返回需要填充的字段

    Returns:
        {
            "现用名": str,
            "法代": str,
            "所在地": str,
            "社会信用代码": str,
            "success": bool,
            "error": str
        }
    """
    try:
        company_data = get_company_data(company_name)

        return {
            "现用名": format_current_name(company_data),
            "法代": company_data.get("LegalPerson", ""),
            "所在地": extract_location(company_data),
            "社会信用代码": company_data.get("CreditNo", ""),
            "success": True,
            "error": ""
        }
    except CompanyQueryError as e:
        return {
            "现用名": "",
            "法代": "",
            "所在地": "",
            "社会信用代码": "",
            "success": False,
            "error": e.message
        }
    except Exception as e:
        return {
            "现用名": "",
            "法代": "",
            "所在地": "",
            "社会信用代码": "",
            "success": False,
            "error": str(e)
        }


def main():
    # 文件路径
    input_file = ROOT / "样本材料" / "5月案件-被执行人信息.xlsx"
    output_file = ROOT / "output" / "5月案件-被执行人信息_已填充.xlsx"

    print(f"读取文件: {input_file}")

    # 读取Excel，所有列都作为字符串处理
    df = pd.read_excel(input_file, dtype=str)

    # 取前10条
    df_to_process = df.head(10).copy()

    # 确保目标列是字符串类型
    for col in ["现用名", "法代", "所在地", "社会信用代码"]:
        df_to_process[col] = df_to_process[col].astype(str)
        df[col] = df[col].astype(str)

    print(f"将处理前 {len(df_to_process)} 条数据\n")

    # 处理每条数据
    results = []
    for idx, row in df_to_process.iterrows():
        company_name = row["被执行人"]
        print(f"[{idx + 1}/10] 查询: {company_name}")

        result = process_company(company_name)
        results.append(result)

        if result["success"]:
            print(f"  ✅ 成功")
            print(f"     现用名: {result['现用名']}")
            print(f"     法代: {result['法代']}")
            print(f"     所在地: {result['所在地']}")
            print(f"     社会信用代码: {result['社会信用代码']}")
        else:
            print(f"  ❌ 失败: {result['error']}")

        # 添加延迟，避免请求过快
        time.sleep(0.5)

    # 填充数据到DataFrame
    for idx, result in enumerate(results):
        df_to_process.at[idx, "现用名"] = result["现用名"]
        df_to_process.at[idx, "法代"] = result["法代"]
        df_to_process.at[idx, "所在地"] = result["所在地"]
        df_to_process.at[idx, "社会信用代码"] = result["社会信用代码"]

    # 更新原DataFrame
    df.update(df_to_process)

    # 保存结果
    output_file.parent.mkdir(exist_ok=True)
    df.to_excel(output_file, index=False)

    print(f"\n{'='*60}")
    print(f"处理完成！")
    print(f"输出文件: {output_file}")
    print(f"{'='*60}")

    # 统计
    success_count = sum(1 for r in results if r["success"])
    print(f"成功: {success_count}/{len(results)}")

    if success_count < len(results):
        print(f"\n失败明细:")
        for idx, result in enumerate(results):
            if not result["success"]:
                company_name = df_to_process.iloc[idx]["被执行人"]
                print(f"  - {company_name}: {result['error']}")


if __name__ == "__main__":
    main()
