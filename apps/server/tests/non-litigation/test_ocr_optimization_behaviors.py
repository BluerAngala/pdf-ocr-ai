from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
SRC = ROOT / 'apps' / 'server' / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from non_litigation_validator import NonLitigationValidator, ValidationStatus


CASES = [
    {'sequence': '77', 'notice_number': '穗公积金中心南沙责字（2025）1175号', 'company_name': '甲公司'},
    {'sequence': '195', 'notice_number': '穗公积金中心南沙责字（2025）1195号', 'company_name': '乙公司'},
]


def test_notice_fuzzy_match_should_warn_not_pass_when_only_similar():
    validator = NonLitigationValidator(CASES)
    result = validator.validate_notice_ocr('notice.pdf', {
        'total_pages': 1,
        'total_duration': 1.1,
        'method': 'region_first_with_fallback',
        'pages': [
            {
                'page': 1,
                'text': '穗公积金中心南沙责字〔2025〕117S号',
                'duration': 1.1,
                'method': 'full_page_fallback',
                'fallback_used': True,
            }
        ],
    })
    assert result.status in {ValidationStatus.WARNING, ValidationStatus.FAIL}


def test_company_doc_should_capture_fallback_and_region_usable_rates():
    validator = NonLitigationValidator(CASES)
    result = validator.validate_company_document_ocr('授权书.pdf', {
        'total_pages': 2,
        'total_duration': 2.0,
        'method': 'region_first_with_fallback',
        'pages': [
            {
                'page': 1,
                'text': '授权委托书',
                'duration': 0.8,
                'method': 'region_first',
                'fallback_used': False,
                'region_usable': True,
                'marker_detected': True,
            },
            {
                'page': 2,
                'text': '授权委托书',
                'duration': 1.2,
                'method': 'full_page_fallback',
                'fallback_used': True,
                'region_usable': False,
                'marker_detected': False,
            },
        ],
    }, expected_count=2, doc_type='authorization')

    assert result.status == ValidationStatus.PASS
    assert result.accuracy['fallback_rate'] == 50.0
    assert result.accuracy['region_usable_rate'] == 50.0
    assert result.accuracy['marker_detection_rate'] == 50.0


def test_application_missing_boundary_should_warn_for_generalized_case():
    validator = NonLitigationValidator(CASES)
    result = validator.validate_application_ocr('申请书.pdf', {
        'total_pages': 4,
        'total_duration': 2.2,
        'method': 'region_first',
        'pages': [
            {'page': 1, 'text': '强制执行申请书', 'duration': 0.5, 'boundary_detected': True, 'fallback_used': False},
            {'page': 2, 'text': '正文', 'duration': 0.5, 'boundary_detected': False, 'fallback_used': False},
            {'page': 3, 'text': '正文', 'duration': 0.6, 'boundary_detected': False, 'fallback_used': False},
            {'page': 4, 'text': '正文', 'duration': 0.6, 'boundary_detected': False, 'fallback_used': False},
        ],
    }, expected_cases=2)

    assert result.status == ValidationStatus.WARNING
    assert result.accuracy['boundary_detection_rate'] == 50.0


def test_company_doc_should_allow_short_title_region_without_fallback():
    validator = NonLitigationValidator(CASES)
    result = validator.validate_company_document_ocr('所函.pdf', {
        'total_pages': 2,
        'total_duration': 1.2,
        'method': 'region_first',
        'pages': [
            {
                'page': 1,
                'text': '律师事务所函',
                'duration': 0.6,
                'method': 'region_first',
                'fallback_used': False,
                'region_usable': True,
                'marker_detected': True,
            },
            {
                'page': 2,
                'text': '律师 事务所',
                'duration': 0.6,
                'method': 'region_first',
                'fallback_used': False,
                'region_usable': True,
                'marker_detected': False,
            },
        ],
    }, expected_count=2, doc_type='letter')

    assert result.status == ValidationStatus.PASS
    assert result.accuracy['fallback_rate'] == 0.0
    assert result.accuracy['region_usable_rate'] == 100.0
