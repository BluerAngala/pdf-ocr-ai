#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模型性能对比测试
测试不同模型的：
1. 内存占用
2. 加载时间
3. 推理速度
4. 输出质量
"""

import os
import sys
import time
import json
import psutil
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

# 添加项目路径
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


@dataclass
class BenchmarkResult:
    """基准测试结果"""
    model_name: str
    model_size_mb: float
    
    # 内存指标
    memory_before_mb: float
    memory_after_mb: float
    memory_peak_mb: float
    memory_used_mb: float
    
    # 时间指标
    load_time_seconds: float
    first_token_time_ms: float
    tokens_per_second: float
    
    # 质量评分（人工评估）
    quality_score: Optional[int] = None  # 1-10
    notes: str = ""


class ModelBenchmark:
    """模型基准测试器"""
    
    # 测试用的OCR文本样本
    TEST_SAMPLES = {
        "legal_doc": """广州铁路运输法院
行政裁定书
（2025）粤7101行审3352号
申请执行人：广州住房公积金管理中心
被执行人：广东润生箱包制造有限公司
申请执行人向本院申请强制执行其作出的穗公积金中心番禺责字〔2024〕595号《责令限期办理决定书》。
本院经审查认为，被执行人未依法为职工缴存住房公积金。
依照《最高人民法院关于适用〈中华人民共和国行政诉讼法〉的解释》第一百零一条第一款第（十四）项规定，裁定如下：
准予强制执行。
""",
        "company_info": """广州住房公积金管理中心
责令限期办理决定书
穗公积金中心黄埔责字〔2025〕594号
名称：三菱电机（广州）压缩机有限公司
统一社会信用代码：9144011661842063XT
地址：广州经济技术开发区东江大道102号
经查，你单位未按规定为李庆秀缴存2016年10月至2024年06月期间的住房公积金。
责令你单位在收到本决定书之日起10个工作日内补缴合计35052元。""",
        "mixed_content": """合同编号：HT-2026-001
甲方：深圳市信品科技有限公司
乙方：深圳市xxx科技有限公司
签订日期：2025年04月14日
金额：¥50,000.00
本合同一式两份，甲乙双方各执一份。"""
    }
    
    def __init__(self):
        self.process = psutil.Process()
        self.results: List[BenchmarkResult] = []
    
    def get_memory_mb(self) -> float:
        """获取当前内存使用（MB）"""
        return self.process.memory_info().rss / 1024 / 1024
    
    def benchmark_model(self, model_path: str, model_name: str) -> Optional[BenchmarkResult]:
        """测试单个模型"""
        from src.local_llm import LocalLLM, LLMConfig
        
        print(f"\n{'='*70}")
        print(f"🧪 测试模型: {model_name}")
        print(f"{'='*70}")
        
        model_file = Path(model_path)
        if not model_file.exists():
            print(f"❌ 模型文件不存在: {model_path}")
            return None
        
        model_size_mb = model_file.stat().st_size / 1024 / 1024
        print(f"📦 模型大小: {model_size_mb:.1f} MB")
        
        # 记录加载前内存
        memory_before = self.get_memory_mb()
        print(f"💾 加载前内存: {memory_before:.1f} MB")
        
        # 加载模型
        print(f"\n🔄 正在加载模型...")
        start_time = time.time()
        
        try:
            config = LLMConfig(
                model_path=str(model_path),
                threads=4,
                context_length=4096,
                max_tokens=512
            )
            llm = LocalLLM(config)
            
            if not llm.load_model():
                print("❌ 模型加载失败")
                return None
            
            load_time = time.time() - start_time
            memory_after = self.get_memory_mb()
            memory_used = memory_after - memory_before
            
            print(f"✅ 加载完成")
            print(f"⏱️  加载时间: {load_time:.2f} 秒")
            print(f"💾 加载后内存: {memory_after:.1f} MB")
            print(f"📈 内存增加: {memory_used:.1f} MB")
            
            # 测试推理速度
            print(f"\n📝 测试推理速度...")
            test_text = self.TEST_SAMPLES["legal_doc"][:200]
            
            # 预热
            _ = llm.chat("你好")
            
            # 正式测试
            prompt = f"请提取以下文本中的案号：\n{test_text}"
            
            infer_start = time.time()
            response = llm.chat(prompt)
            infer_time = time.time() - infer_start
            
            # 估算token数（粗略）
            tokens_in = len(prompt) // 2
            tokens_out = len(response) // 2
            total_tokens = tokens_in + tokens_out
            tokens_per_sec = total_tokens / infer_time if infer_time > 0 else 0
            
            print(f"⏱️  推理时间: {infer_time:.2f} 秒")
            print(f"🚀 生成速度: {tokens_per_sec:.1f} tokens/秒")
            print(f"📝 输出预览: {response[:100]}...")
            
            # 测试功能
            print(f"\n🔍 测试OCR分析功能...")
            analysis_start = time.time()
            analysis = llm.analyze_ocr_text(test_text, task="extract")
            analysis_time = time.time() - analysis_start
            
            print(f"⏱️  分析时间: {analysis_time:.2f} 秒")
            print(f"📊 分析结果: {json.dumps(analysis, ensure_ascii=False, indent=2)[:200]}...")
            
            # 获取峰值内存（粗略估计）
            memory_peak = max(memory_after, self.get_memory_mb())
            
            result = BenchmarkResult(
                model_name=model_name,
                model_size_mb=model_size_mb,
                memory_before_mb=memory_before,
                memory_after_mb=memory_after,
                memory_peak_mb=memory_peak,
                memory_used_mb=memory_used,
                load_time_seconds=load_time,
                first_token_time_ms=infer_time * 1000,
                tokens_per_second=tokens_per_sec,
                notes="测试完成"
            )
            
            return result
            
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return None
        finally:
            # 清理内存
            del llm
            import gc
            gc.collect()
    
    def run_comparison(self, models_dir: str = "models"):
        """运行对比测试"""
        models_path = Path(models_dir)
        
        if not models_path.exists():
            print(f"❌ 模型目录不存在: {models_path}")
            print("请先下载模型: python scripts/download_model.py --model <model_name>")
            return
        
        # 查找所有 .gguf 文件
        model_files = list(models_path.glob("*.gguf"))
        
        if not model_files:
            print("❌ 未找到模型文件")
            print("可用模型:")
            print("  python scripts/download_model.py --model gemma-3-4b")
            print("  python scripts/download_model.py --model qwen2.5-1.5b")
            return
        
        print(f"\n🔍 发现 {len(model_files)} 个模型文件")
        
        for model_file in model_files:
            model_name = model_file.stem
            result = self.benchmark_model(str(model_file), model_name)
            if result:
                self.results.append(result)
        
        # 生成报告
        self.generate_report()
    
    def generate_report(self):
        """生成对比报告"""
        if not self.results:
            print("\n❌ 没有测试结果")
            return
        
        print(f"\n{'='*70}")
        print("📊 模型对比报告")
        print(f"{'='*70}")
        
        # 按内存使用排序
        sorted_results = sorted(self.results, key=lambda x: x.memory_used_mb)
        
        print(f"\n{'模型名称':<30} {'大小(MB)':<12} {'内存(MB)':<12} {'加载(秒)':<10} {'速度(tok/s)':<12}")
        print("-" * 80)
        
        for r in sorted_results:
            print(f"{r.model_name:<30} {r.model_size_mb:<12.1f} {r.memory_used_mb:<12.1f} {r.load_time_seconds:<10.2f} {r.tokens_per_second:<12.1f}")
        
        # 推荐建议
        print(f"\n{'='*70}")
        print("💡 推荐建议")
        print(f"{'='*70}")
        
        if sorted_results:
            best_memory = sorted_results[0]
            best_speed = max(self.results, key=lambda x: x.tokens_per_second)
            
            print(f"\n🎯 内存占用最小: {best_memory.model_name}")
            print(f"   内存使用: {best_memory.memory_used_mb:.1f} MB")
            print(f"   适合: 内存受限场景（4-6GB内存）")
            
            print(f"\n⚡ 推理速度最快: {best_speed.model_name}")
            print(f"   生成速度: {best_speed.tokens_per_second:.1f} tokens/秒")
            print(f"   适合: 需要快速响应的场景")
        
        # 保存详细报告
        report_path = Path("benchmark_report.json")
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump([asdict(r) for r in self.results], f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 详细报告已保存: {report_path}")


def print_model_specs():
    """打印模型规格说明"""
    print("\n" + "="*70)
    print("📚 模型规格详细对比")
    print("="*70)
    
    specs = {
        "Gemma 3 4B IT": {
            "参数": "4B (40亿)",
            "量化大小": "2.6GB (Q4_K_M)",
            "内存需求": "3-4GB",
            "上下文": "128K tokens",
            "特点": [
                "Google 2025年3月最新发布",
                "中文能力优秀（训练数据含中文）",
                "支持多语言（100+语言）",
                "推理能力强",
                "适合长文档分析"
            ],
            "适用场景": "文本纠错、信息提取、长文档理解",
            "推荐指数": "⭐⭐⭐⭐⭐"
        },
        "Qwen2.5 1.5B Instruct": {
            "参数": "1.5B (15亿)",
            "量化大小": "1GB (Q4_K_M)",
            "内存需求": "2GB",
            "上下文": "32K tokens",
            "特点": [
                "阿里最新模型",
                "中文优化极好",
                "法律文档处理优秀",
                "轻量快速",
                "适合中文场景"
            ],
            "适用场景": "资源受限、纯中文文档处理",
            "推荐指数": "⭐⭐⭐⭐"
        },
        "Qwen2.5 3B Instruct": {
            "参数": "3B (30亿)",
            "量化大小": "1.9GB (Q4_K_M)",
            "内存需求": "3GB",
            "上下文": "32K tokens",
            "特点": [
                "1.5B的升级版",
                "推理能力更强",
                "中文依然优秀",
                "速度和质量平衡"
            ],
            "适用场景": "需要更强推理能力的中文场景",
            "推荐指数": "⭐⭐⭐⭐"
        },
        "Llama 3.2 3B Instruct": {
            "参数": "3B (30亿)",
            "量化大小": "1.9GB (Q4_K_M)",
            "内存需求": "3GB",
            "上下文": "128K tokens",
            "特点": [
                "Meta官方模型",
                "英文极强",
                "多语言支持好",
                "中文稍弱于Qwen",
                "生态完善"
            ],
            "适用场景": "多语言混合文档、英文为主",
            "推荐指数": "⭐⭐⭐"
        },
        "Phi-4 14B": {
            "参数": "14B (140亿)",
            "量化大小": "8GB (Q4_K_M)",
            "内存需求": "10GB+",
            "上下文": "16K tokens",
            "特点": [
                "微软推理王",
                "推理能力极强",
                "适合复杂分析",
                "资源需求高",
                "中文一般"
            ],
            "适用场景": "复杂推理任务（需要高配电脑）",
            "推荐指数": "⭐⭐"
        }
    }
    
    for name, spec in specs.items():
        print(f"\n{'='*70}")
        print(f"🤖 {name} {spec['推荐指数']}")
        print(f"{'='*70}")
        print(f"参数: {spec['参数']}")
        print(f"文件大小: {spec['量化大小']}")
        print(f"运行内存: {spec['内存需求']}")
        print(f"上下文长度: {spec['上下文']}")
        print(f"\n特点:")
        for feature in spec['特点']:
            print(f"  • {feature}")
        print(f"\n适用: {spec['适用场景']}")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="模型性能对比测试")
    parser.add_argument('--specs', '-s', action='store_true', help='只显示模型规格对比')
    parser.add_argument('--test', '-t', action='store_true', help='运行实际测试（需要已下载模型）')
    
    args = parser.parse_args()
    
    if args.specs or (not args.test):
        print_model_specs()
    
    if args.test:
        print("\n")
        benchmark = ModelBenchmark()
        benchmark.run_comparison()


if __name__ == '__main__':
    main()
