#!/usr/bin/env python3
"""
调试 unicloud 企业信息查询接口 - 查看完整响应数据结构
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import json
from infra.company_query import _get_api_config, query_company_info

# 测试用的企业名称（一个成功一个可能失败）
TEST_COMPANIES = [
    "北京讯鸟软件有限公司广州分公司",
    "北京元年诺亚舟咨询有限公司",
]


def test_query_debug(company_name, config):
    """测试查询并打印完整响应"""
    print(f"\n{'='*60}")
    print(f"查询企业: {company_name}")
    print(f"{'='*60}")
    try:
        result = query_company_info(company_name, config)
        print(f"\n完整响应:")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        
        # 解析关键字段
        print(f"\n关键字段解析:")
        print(f"  code: {result.get('code')}")
        print(f"  msg: {result.get('msg')}")
        
        data = result.get('data', {})
        print(f"  data: {type(data)}")
        
        if isinstance(data, dict):
            print(f"    data.companyName: {data.get('companyName')}")
            print(f"    data.usedTimes: {data.get('usedTimes')}")
            print(f"    data.remainingTimes: {data.get('remainingTimes')}")
            
            company_info = data.get('companyInfo')
            print(f"    data.companyInfo: {type(company_info)}")
            
            if isinstance(company_info, dict):
                print(f"\n    企业详细信息:")
                for key, value in company_info.items():
                    print(f"      {key}: {value}")
            else:
                print(f"      companyInfo 为空或不是字典: {company_info}")
        
        return result
    except Exception as e:
        print(f"查询失败: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    print("=" * 60)
    print("调试 unicloud 企业信息查询接口")
    print("=" * 60)

    config = _get_api_config()
    print(f"\n配置:")
    print(f"  API URL: {config['api_url']}")
    print(f"  User ID: {config['userid']}")

    for company in TEST_COMPANIES:
        test_query_debug(company, config)
