# OCR 识别通用化设计方案

## 核心问题

当前实现存在以下硬编码问题：
1. 正则表达式硬编码特定机构名称（"穗公积金中心"）
2. 纠错规则分散在多个层级
3. 缺乏自适应学习能力
4. 每个新场景都需要修改代码

## 通用化架构设计

### 1. 配置驱动的识别模式

```yaml
# config.yaml 新增识别模式配置
recognition_patterns:
  # 责令号识别模式
  notice_number:
    # 多城市支持
    cities:
      - name: 广州
        prefix: 穗公积金中心
        suffix: 责字
        region_keywords: [番禺, 天河, 白云, 荔湾, 海珠, 越秀, 黄埔, 花都, 萝岗, 南沙, 从化, 增城]
      - name: 深圳
        prefix: 深公积金中心
        suffix: 责字
        region_keywords: [福田, 罗湖, 南山, 盐田, 宝安, 龙岗]
      - name: 佛山
        prefix: 佛公积金中心
        suffix: 责字
        region_keywords: [禅城, 南海, 顺德, 三水, 高明]
    
    # 通用模式模板
    pattern_template: "{prefix}{region}{suffix}{year_bracket}{year}{year_close}{number}号"
    
    # 括号变体
    year_brackets:
      - open: "〔"
        close: "〕"
      - open: "("
        close: ")"
      - open: "["
        close: "]"
      - open: "【"
        close: "】"
    
    # 容错模式（OCR常见错误）
    fuzzy_patterns:
      - "公积金中心{region}{suffix}"
      - "{prefix}{region}责"
      - "{prefix}{region}贵字"

  # 案号识别模式
  case_number:
    patterns:
      - "({court})({year})({type})({number})号"
    variables:
      court: [番禺法院, 天河法院, 白云法院]
      year: "\\d{4}"
      type: [民初, 刑初, 行初, 执]
      number: "\\d+"

  # 公司名称识别
  company_name:
    # 上下文线索
    context_markers:
      - [委托单位, 委托人, 申请人, 被执行人]
      - [甲方, 乙方, 丙方]
    
    # 公司名后缀
    suffixes:
      - 有限公司
      - 有限责任公司
      - 股份有限公司
      - 集团有限公司
      - 合伙企业
      - 工作室
```

### 2. 分层纠错系统

```yaml
# 三层纠错体系
ocr_correction_layers:
  # 第一层：字符级纠错（通用）
  character_level:
    description: "单字符OCR误识"
    rules:
      - pattern: "[番禹]"
        correct: "番禺"
        context: "公积金"
      - pattern: "[天何]"
        correct: "天河"
        context: "公积金"
    
    # 基于相似字符的自动纠错
    similar_chars:
      "禺": ["禹", "遇", "愚"]
      "州": ["洲", "川"]
      "责": ["贵", "货"]
      "任": ["仕", "伍"]
      "限": ["银", "很"]
  
  # 第二层：词汇级纠错（业务相关）
  word_level:
    description: "业务词汇纠错"
    rules:
      - wrong: "住房公积全"
        correct: "住房公积金"
      - wrong: "公积全"
        correct: "公积金"
      - wrong: "住方公积金"
        correct: "住房公积金"
  
  # 第三层：语义级纠错（上下文感知）
  semantic_level:
    description: "基于上下文的智能纠错"
    strategies:
      # 策略1：台账匹配
      - name: ledger_matching
        description: "从台账中查找最匹配的记录"
        threshold: 0.85
        
      # 策略2：序列推断
      - name: sequence_inference
        description: "基于序列规律推断"
        example: "如果已有 3517, 3518, 3519, 则 3539 可能是 3519 的误识"
        
      # 策略3：上下文验证
      - name: context_validation
        description: "验证识别结果是否符合上下文"
        rules:
          - "责令号中的地区应与台账一致"
          - "年份应与文档日期一致"
```

### 3. 自适应学习机制

```yaml
# 自动学习配置
adaptive_learning:
  enabled: true
  
  # 学习来源
  sources:
    # 从人工纠正中学习
    manual_corrections:
      storage: corrections_learned.json
      min_confidence: 0.9
      
    # 从台账数据中学习
    ledger_analysis:
      extract_patterns: true
      learn_company_names: true
      learn_notice_numbers: true
  
  # 学习到的规则自动应用
  auto_apply_rules:
    min_occurrence: 3  # 出现3次以上才自动应用
    max_false_positive: 0.05  # 误报率不超过5%
```

### 4. 多策略识别引擎

```python
# 伪代码：多策略识别引擎
class AdaptiveRecognitionEngine:
    def __init__(self, config):
        self.patterns = config.recognition_patterns
        self.corrections = config.ocr_correction_layers
        self.ledger = None  # 台账数据
    
    def recognize(self, text: str, context: dict) -> RecognitionResult:
        """
        多策略识别流程：
        1. 原始识别
        2. 字符级纠错
        3. 词汇级纠错
        4. 模式匹配
        5. 语义验证
        6. 台账匹配
        """
        
        # 步骤1-3：预处理
        corrected = self.apply_corrections(text, level=['character', 'word'])
        
        # 步骤4：多模式匹配
        candidates = []
        for pattern_name, pattern_config in self.patterns.items():
            matches = self.match_pattern(corrected, pattern_config)
            candidates.extend(matches)
        
        # 步骤5：语义验证
        validated = [c for c in candidates if self.validate_semantics(c, context)]
        
        # 步骤6：台账匹配（如果有台账）
        if self.ledger:
            best_match = self.find_best_ledger_match(validated, context)
            if best_match.confidence > 0.9:
                return best_match
        
        # 返回置信度最高的结果
        return max(validated, key=lambda x: x.confidence, default=None)
    
    def validate_semantics(self, candidate: Candidate, context: dict) -> bool:
        """语义验证：检查结果是否符合业务逻辑"""
        
        # 验证1：地区一致性
        if 'region' in candidate and 'expected_region' in context:
            if candidate['region'] != context['expected_region']:
                return False
        
        # 验证2：年份合理性
        if 'year' in candidate:
            year = int(candidate['year'])
            current_year = datetime.now().year
            if not (2020 <= year <= current_year + 1):
                return False
        
        # 验证3：序列合理性
        if 'number' in candidate and 'sequence_context' in context:
            number = int(candidate['number'])
            expected_range = context['sequence_context']
            if not (expected_range[0] <= number <= expected_range[1]):
                # 可能是OCR错误，记录但不禁用
                candidate['warning'] = f"号码 {number} 超出预期范围"
        
        return True
```

### 5. 配置验证和测试框架

```yaml
# 测试配置
recognition_tests:
  # 单元测试用例
  test_cases:
    - name: "广州番禺责催"
      input: "穗公积金中心番禹责字〔2025〕3527号"
      expected:
        city: 广州
        region: 番禺
        year: "2025"
        number: "3527"
      expected_corrections:
        - "番禹" -> "番禺"
    
    - name: "数字误识"
      input: "穗公积金中心番禺责字〔2025〕3539号"
      context:
        ledger_numbers: [3517, 3518, 3519, 3520]
      expected:
        number: "3519"  # 应通过序列推断纠正
        confidence: high
  
  # 集成测试
  integration_tests:
    - sample_batch: "第3批"
      expected_pass_rate: 0.95
      max_warnings: 3
```

## 实施建议

### 阶段1：配置化（已完成部分）
- ✅ 将区名纠错放入配置
- ✅ 将文档类型配置化
- 🔄 将识别模式配置化（建议）

### 阶段2：智能纠错（下一步）
- 实现基于台账的模糊匹配
- 实现序列推断纠错
- 实现上下文验证

### 阶段3：自适应学习（未来）
- 收集人工纠正数据
- 自动学习新的错误模式
- 定期更新纠错规则

## 当前可立即实施的改进

1. **将正则表达式配置化**
2. **增加更多城市的支持**
3. **实现基于台账的智能匹配**
4. **添加识别置信度评估**
