#!/usr/bin/env python3
"""
测试 unicloud 企业信息查询接口
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from infra.company_query import _get_api_config, query_company_info, get_company_data

# 测试用的企业名称
TEST_COMPANY_NAME = "珠海横琴航投一号投资中心（有限合伙）"


def test_api_config():
    """测试配置读取"""
    config = _get_api_config()
    print("配置信息:")
    print(f"  API URL: {config['api_url']}")
    print(f"  User ID: {config['userid']}")
    print(f"  User Key: {'*' * len(config['userkey']) if config['userkey'] else '(未配置)'}")
    print(f"  Request Delay: {config['request_delay']}")
    print(f"  Excel Column: {config['excel_column_name']}")
    return config


def test_query_company_info(config):
    """测试查询接口"""
    print(f"\n测试查询企业: {TEST_COMPANY_NAME}")
    try:
        result = query_company_info(TEST_COMPANY_NAME, config)
        print(f"响应 code: {result.get('code')}")
        print(f"响应 msg: {result.get('msg')}")
        print(f"响应 data: {result.get('data')}")
        return result
    except Exception as e:
        print(f"查询失败: {e}")
        return None


def test_get_company_data(config):
    """测试获取企业数据"""
    print(f"\n测试获取企业数据: {TEST_COMPANY_NAME}")
    try:
        company_data = get_company_data(TEST_COMPANY_NAME, config)
        print(f"企业数据: {company_data}")
        return company_data
    except Exception as e:
        print(f"获取失败: {e}")
        return None


if __name__ == "__main__":
    print("=" * 60)
    print("测试 unicloud 企业信息查询接口")
    print("=" * 60)

    config = test_api_config()

    # 检查配置是否完整
    if not config['userid'] or not config['userkey']:
        print("\n警告: userid 或 userkey 未配置，请在 config.yaml 中设置")
        sys.exit(1)

    result = test_query_company_info(config)
    if result and result.get('code') == 200:
        company_data = test_get_company_data(config)
        if company_data:
            print("\n企业信息:")
            for key, value in company_data.items():
                print(f"  {key}: {value}")
