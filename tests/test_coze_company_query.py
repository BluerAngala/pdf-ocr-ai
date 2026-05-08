#!/usr/bin/env python3
"""
测试 Coze 工作流 API - 查询企业信息

API 文档参考: https://www.coze.cn/docs/developer_guides/workflow_run
"""

import requests
import json
import pytest

# Coze API 配置
COZE_API_URL = "https://api.coze.cn/v1/workflow/run"
COZE_API_TOKEN = "sat_xo6jKTKmaerCALRXHE7ZrRowHOvHARoplcU0HiYQtARY3QMr4C1MXqUO3FAJFuHA"
WORKFLOW_ID = "7637504045536428084"

# 测试用的企业名称
TEST_COMPANY_NAME = "珠海横琴航投一号投资中心（有限合伙）"


class CompanyQueryError(Exception):
    """企业查询错误"""
    def __init__(self, message: str, raw_response: dict = None):
        self.message = message
        self.raw_response = raw_response
        super().__init__(self.message)

    def __str__(self):
        if self.raw_response:
            return f"{self.message}\n原始响应: {json.dumps(self.raw_response, ensure_ascii=False, indent=2)}"
        return self.message


def query_company_info(company_name: str) -> dict:
    """
    调用 Coze 工作流 API 查询企业信息

    Args:
        company_name: 企业名称

    Returns:
        API 响应的 JSON 数据（已解析嵌套的 data 字段）
    """
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

    # 解析嵌套的 data 字段（data 是字符串化的 JSON）
    if result.get("code") == 0 and "data" in result and isinstance(result["data"], str):
        try:
            inner_data = json.loads(result["data"])
            result["data"] = inner_data
        except json.JSONDecodeError:
            pass

    return result


def get_company_data(company_name: str) -> dict:
    """
    查询企业信息，返回解析后的企业数据

    Args:
        company_name: 企业名称

    Returns:
        企业数据字典

    Raises:
        CompanyQueryError: 查询失败或企业数据为空时抛出，包含原始响应
    """
    result = query_company_info(company_name)

    # API 返回错误
    if result.get("code") != 0:
        raise CompanyQueryError(
            f"API 返回错误: {result.get('msg', '未知错误')} (code: {result.get('code')})",
            raw_response=result
        )

    # 获取企业数据
    data = result.get("data", {})
    company_data = data.get("data") if isinstance(data, dict) else None

    # 企业数据为空
    if not company_data:
        raise CompanyQueryError(
            "未查询到企业数据",
            raw_response=result
        )

    return company_data


class TestCozeCompanyQuery:
    """Coze 企业信息查询 API 测试类"""

    def test_query_company_info_success(self):
        """测试成功查询企业信息"""
        result = query_company_info(TEST_COMPANY_NAME)

        # 验证响应结构
        assert result["code"] == 0, f"API 返回错误: {result.get('msg', '未知错误')}"
        assert "data" in result, "响应中缺少 data 字段"

        # 获取企业数据
        company_data = result.get("data", {}).get("data", {})
        assert company_data, "企业数据为空"
        assert company_data.get("CompanyName") == TEST_COMPANY_NAME, "企业名称不匹配"

        print(f"\n✅ 查询成功")
        print(f"\n企业数据:\n{json.dumps(company_data, ensure_ascii=False, indent=2)}")

    def test_get_company_data_success(self):
        """测试获取企业数据成功"""
        company_data = get_company_data(TEST_COMPANY_NAME)

        assert company_data, "获取企业数据失败"
        assert company_data.get("CompanyName") == TEST_COMPANY_NAME

        print(f"\n✅ 获取企业数据成功")
        print(f"企业名称: {company_data.get('CompanyName')}")
        print(f"统一社会信用代码: {company_data.get('CreditNo')}")
        print(f"历史名称: {company_data.get('HistoryNames')}")

    def test_get_company_data_not_found(self):
        """测试查询不到企业时的错误处理"""
        try:
            get_company_data("不存在的公司名字XYZ123")
            assert False, "应该抛出 CompanyQueryError"
        except CompanyQueryError as e:
            print(f"\n✅ 正确捕获错误: {e.message}")
            print(f"\n原始响应:\n{json.dumps(e.raw_response, ensure_ascii=False, indent=2)}")


if __name__ == "__main__":
    # 直接运行测试
    print("=" * 60)
    print("Coze 企业信息查询 API 测试")
    print("=" * 60)

    try:
        # 查询企业信息
        company_data = get_company_data(TEST_COMPANY_NAME)

        print(f"\n✅ 查询成功")
        print(f"\n{'='*60}")
        print("企业完整数据")
        print(f"{'='*60}")
        print(json.dumps(company_data, ensure_ascii=False, indent=2))

    except CompanyQueryError as e:
        print(f"\n❌ 查询失败: {e.message}")
        print(f"\n{'='*60}")
        print("原始响应数据")
        print(f"{'='*60}")
        print(json.dumps(e.raw_response, ensure_ascii=False, indent=2))

    except requests.exceptions.RequestException as e:
        print(f"\n❌ 请求失败: {e}")

    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
