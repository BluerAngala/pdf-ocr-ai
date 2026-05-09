from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from non_litigation_validator import NonLitigationValidator, ValidationStatus


CASES = [
    {'sequence': '1', 'notice_number': '穗公积金中心南沙责字（2025）1175号', 'company_name': '甲公司'},
    {'sequence': '2', 'notice_number': '穗公积金中心南沙责字（2025）1195号', 'company_name': '乙公司'},
]

REMAPPED_CASES = [
    {'sequence': '1', 'notice_number': '穗公积金中心南沙责字（2025）1175-2号', 'company_name': '甲公司'},
]


def test_validate_notice_ocr_should_include_accuracy_guardrail_metrics():
    validator = NonLitigationValidator(CASES)
    result = validator.validate_notice_ocr('1.pdf', {
        'total_pages': 1,
        'total_duration': 1.2,
        'method': 'region_first_sequential',
        'optimization_strategy': 'region_first_sequential',
        'stopped_early': True,
        'selected_notice': '穗公积金中心南沙责字〔2025〕1175号',
        'selected_page': 1,
        'candidate_notices': [{'page': 1, 'number': '穗公积金中心南沙责字〔2025〕1175号'}],
        'pages': [
            {
                'page': 1,
                'text': '穗公积金中心南沙责字〔2025〕1175号',
                'duration': 1.0,
                'method': 'region_first',
                'fallback_used': False,
            }
        ],
    })

    assert result.status == ValidationStatus.PASS
    assert result.details['stopped_early'] is True
    assert result.details['fallback_pages'] == 0
    assert result.details['selected_notice'] == '穗公积金中心南沙责字〔2025〕1175号'
    assert result.details['selected_page'] == 1
    assert result.accuracy['fallback_rate'] == 0.0
    assert result.accuracy['region_first_hit_rate'] == 100.0


def test_validate_notice_ocr_should_warn_when_main_number_is_remapped_to_same_root_subnumber():
    validator = NonLitigationValidator(REMAPPED_CASES)
    result = validator.validate_notice_ocr('1.pdf', {
        'total_pages': 3,
        'total_duration': 2.5,
        'method': 'region_first_sequential',
        'optimization_strategy': 'region_first_sequential',
        'selected_notice': '穗公积金中心南沙责字〔2025〕1175号',
        'selected_page': 3,
        'matched_target': '1-责催-穗公积金中心南沙责字（2025）1175-2号.pdf',
        'matched_target_notice': '穗公积金中心南沙责字（2025）1175-2号',
        'export_match_type': 'same_root_base',
        'same_root_remap': True,
        'candidate_notices': [
            {'page': 1, 'number': '穗公积金中心南沙责字〔2025〕1175-2号'},
            {'page': 3, 'number': '穗公积金中心南沙责字〔2025〕1175号'},
        ],
        'pages': [
            {'page': 1, 'text': '送达回证\n穗公积金中心南沙责字〔2025〕1175-2号', 'duration': 0.7, 'method': 'region_first', 'fallback_used': False},
            {'page': 2, 'text': '正文', 'duration': 0.8, 'method': 'region_first', 'fallback_used': False},
            {'page': 3, 'text': '责令限期办理决定书\n穗公积金中心南沙责字〔2025〕1175号', 'duration': 1.0, 'method': 'region_first', 'fallback_used': False},
        ],
    })

    assert result.status == ValidationStatus.WARNING
    assert result.details['same_root_remap'] is True
    assert result.details['diagnostic_category'] == 'basis_mismatch'
    assert result.details['diagnostic_reason'] == '识别主号成功，但导出目标被同根号子号重映射'
    assert result.details['same_root_remap_summary']['target_notice'] == '穗公积金中心南沙责字〔2025〕1175-2号'
    assert '同根目标导出' in result.message


def test_validate_application_ocr_should_report_boundary_and_fallback_metrics():
    validator = NonLitigationValidator(CASES)
    result = validator.validate_application_ocr('申请书.pdf', {
        'total_pages': 4,
        'total_duration': 3.0,
        'method': 'region_first_with_fallback',
        'optimization_strategy': 'region_first_with_fallback',
        'pages': [
            {'page': 1, 'text': '强制执行申请书', 'duration': 0.8, 'boundary_detected': True, 'fallback_used': False},
            {'page': 2, 'text': '正文', 'duration': 0.5, 'boundary_detected': False, 'fallback_used': False},
            {'page': 3, 'text': '强制执行申请书', 'duration': 0.9, 'boundary_detected': True, 'fallback_used': True},
            {'page': 4, 'text': '正文', 'duration': 0.6, 'boundary_detected': False, 'fallback_used': False},
        ],
    }, expected_cases=2)

    assert result.status == ValidationStatus.PASS
    assert result.details['boundary_pages_detected'] == [1, 3]
    assert result.details['fallback_pages'] == 1
    assert result.accuracy['boundary_detection_rate'] == 100
    assert result.accuracy['fallback_rate'] == 25.0


def test_generate_report_should_include_accuracy_summary_and_guardrails():
    validator = NonLitigationValidator(CASES)
    validator.validation_report.append(validator.validate_notice_ocr('1.pdf', {
        'total_pages': 1,
        'total_duration': 1.0,
        'method': 'region_first_sequential',
        'pages': [{'page': 1, 'text': '穗公积金中心南沙责字〔2025〕1175号', 'duration': 1.0, 'method': 'region_first', 'fallback_used': False}],
    }))
    validator.validation_report.append(validator.validate_company_document_ocr('所函.pdf', {
        'total_pages': 1,
        'total_duration': 0.8,
        'method': 'region_first_with_fallback',
        'pages': [{'page': 1, 'text': '空白', 'duration': 0.8, 'method': 'full_page_fallback', 'fallback_used': True, 'region_usable': False, 'marker_detected': False}],
    }, expected_count=2, doc_type='letter'))

    report = validator.generate_report()
    assert 'accuracy_summary' in report
    assert 'optimization_guardrails' in report
    assert report['accuracy_summary']['fallback_pages_total'] >= 1
    assert report['optimization_guardrails']['needs_review'] is True


def test_generate_report_should_count_same_root_remap_warnings():
    validator = NonLitigationValidator(REMAPPED_CASES)
    validator.validation_report.append(validator.validate_notice_ocr('1.pdf', {
        'total_pages': 1,
        'total_duration': 1.0,
        'method': 'region_first_sequential',
        'selected_notice': '穗公积金中心南沙责字〔2025〕1175号',
        'matched_target': '1-责催-穗公积金中心南沙责字（2025）1175-2号.pdf',
        'matched_target_notice': '穗公积金中心南沙责字（2025）1175-2号',
        'export_match_type': 'same_root_base',
        'same_root_remap': True,
        'pages': [{'page': 1, 'text': '穗公积金中心南沙责字〔2025〕1175号', 'duration': 1.0, 'method': 'region_first', 'fallback_used': False}],
    }))

    report = validator.generate_report()
    assert report['accuracy_summary']['same_root_remap_warnings'] == 1
    assert report['accuracy_summary']['basis_mismatch_warnings'] == 1


def test_validate_notice_ocr_should_classify_fuzzy_mapping_warning():
    validator = NonLitigationValidator(CASES)
    result = validator.validate_notice_ocr('1.pdf', {
        'total_pages': 1,
        'total_duration': 1.0,
        'method': 'region_first_sequential',
        'selected_notice': '穗公积金中心南沙责字〔2025〕1176号',
        'pages': [{'page': 1, 'text': '穗公积金中心南沙责字〔2025〕1176号', 'duration': 1.0, 'method': 'region_first', 'fallback_used': False}],
    })

    assert result.status == ValidationStatus.WARNING
    assert result.details['diagnostic_category'] == 'fuzzy_mapping'
    assert '模糊匹配候选' in result.details['diagnostic_reason']



def test_validate_notice_ocr_should_classify_ocr_failure_when_notice_missing():
    validator = NonLitigationValidator(CASES)
    result = validator.validate_notice_ocr('1.pdf', {
        'total_pages': 1,
        'total_duration': 0.5,
        'method': 'region_first_sequential',
        'pages': [{'page': 1, 'text': '送达回证正文', 'duration': 0.5, 'method': 'region_first', 'fallback_used': False}],
    })

    assert result.status == ValidationStatus.FAIL
    assert result.details['diagnostic_category'] == 'ocr_failure'
    assert result.details['diagnostic_reason'] == '未识别到责令号'



def test_generate_report_should_include_new_diagnostic_aggregates():
    validator = NonLitigationValidator(REMAPPED_CASES)
    validator.validation_report.append(validator.validate_notice_ocr('basis.pdf', {
        'total_pages': 1,
        'total_duration': 1.0,
        'method': 'region_first_sequential',
        'selected_notice': '穗公积金中心南沙责字〔2025〕1175号',
        'matched_target': '1-责催-穗公积金中心南沙责字（2025）1175-2号.pdf',
        'matched_target_notice': '穗公积金中心南沙责字（2025）1175-2号',
        'export_match_type': 'same_root_base',
        'same_root_remap': True,
        'pages': [{'page': 1, 'text': '穗公积金中心南沙责字〔2025〕1175号', 'duration': 1.0, 'method': 'region_first', 'fallback_used': False}],
    }))
    validator.validation_report.append(validator.validate_notice_ocr('fuzzy.pdf', {
        'total_pages': 1,
        'total_duration': 1.0,
        'method': 'region_first_sequential',
        'selected_notice': '穗公积金中心南沙责字〔2025〕1176号',
        'pages': [{'page': 1, 'text': '穗公积金中心南沙责字〔2025〕1176号', 'duration': 1.0, 'method': 'region_first', 'fallback_used': False}],
    }))
    validator.validation_report.append(validator.validate_notice_ocr('fail.pdf', {
        'total_pages': 3,
        'total_duration': 1.5,
        'method': 'region_first_sequential',
        'selected_notice': '穗公积金中心南沙责字〔2025〕9999号',
        'pages': [
            {'page': 1, 'text': '穗公积金中心南沙责字〔2025〕9999号', 'duration': 0.5, 'method': 'region_first', 'fallback_used': True},
            {'page': 2, 'text': '正文', 'duration': 0.5, 'method': 'region_first', 'fallback_used': True},
            {'page': 3, 'text': '附页', 'duration': 0.5, 'method': 'region_first', 'fallback_used': False},
        ],
    }))

    report = validator.generate_report()
    assert report['accuracy_summary']['basis_mismatch_warnings'] == 1
    assert report['accuracy_summary']['fuzzy_mapping_warnings'] == 1
    assert report['accuracy_summary']['ocr_or_heuristic_failures'] == 1
    assert report['accuracy_summary']['documents_with_high_fallback'] == 1
