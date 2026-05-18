from pathlib import Path
import sys

SRC = Path(__file__).resolve().parents[4] / 'apps' / 'server' / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from core.paths import ROOT, USER_DATA_DIR
SCRIPTS = ROOT / 'apps' / 'server' / 'scripts'
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from run_non_litigation_flow import (
    ALL_BATCH_SUMMARY_PATH,
    BATCH2_SAMPLE_ROOT,
    DEFAULT_HTML_REPORT_PATH,
    DEFAULT_SUMMARY_PATH,
    build_aggregate_summary,
    build_batch_config,
    build_run_summary,
    clean_rebuildable_outputs,
    format_all_batches_summary,
    format_summary,
    infer_paths_for_sample_root,
    resolve_sample_root,
)


def test_run_non_litigation_flow_should_build_summary_with_expected_paths_and_outputs():
    summary = build_run_summary(ROOT)
    text = format_summary(summary)

    assert summary['input_root'] in {
        str(ROOT / 'input' / 'non-litigation'),
        str(ROOT / '样本材料' / '非诉组自动化样本材料' / '原始文件'),
    }
    assert summary['result_root'] == str(USER_DATA_DIR / 'output' / 'non-litigation-results')
    assert summary['html_report_path'] == str(USER_DATA_DIR / 'output' / 'ocr-validation-report.html')
    assert summary['created_count'] > 0
    assert summary['quality']['total_files'] > 0
    assert summary['runtime_seconds'] >= summary['export_runtime_seconds']
    assert '非诉输入目录:' in text
    assert '最终识别准确率:' in text
    assert '业务导出准确率:' in text
    assert '输出文件（申请书）' in summary['output_folders']


def test_resolve_sample_root_should_support_relative_batch2_path():
    sample_root = resolve_sample_root('样本材料/非诉组自动化样本材料（第2批）')
    assert sample_root == BATCH2_SAMPLE_ROOT


def test_build_run_summary_should_use_sample_original_dir_when_present(monkeypatch):
    batch2_root = BATCH2_SAMPLE_ROOT

    monkeypatch.setattr('run_non_litigation_flow.build_mock_ocr_results', lambda *args, **kwargs: {})
    monkeypatch.setattr('run_non_litigation_flow.export_non_litigation_standard_outputs', lambda **kwargs: {'created_count': 1})
    monkeypatch.setattr('run_non_litigation_flow.evaluate_non_litigation_quality', lambda *args, **kwargs: {'total_files': 1, 'page_count_matched': 1, 'page_count_match_rate': 1.0})
    monkeypatch.setattr('run_non_litigation_flow.load_non_litigation_cases', lambda sample_root: [{'sequence': '1', 'notice_number': 'X', 'company_name': 'Y'}])
    monkeypatch.setattr('run_non_litigation_flow.validate_ocr_results', lambda *args, **kwargs: {'summary': {'total': 1, 'passed': 1, 'warnings': 0, 'failed': 0, 'pass_rate': 1.0}, 'failed_items': [], 'warning_items': [], 'accuracy_summary': {'same_root_remap_warnings': 0, 'notice_failures': 0, 'basis_mismatch_warnings': 0, 'fuzzy_mapping_warnings': 0, 'ocr_or_heuristic_failures': 0, 'documents_with_high_fallback': 0, 'fallback_pages_total': 0}})
    monkeypatch.setattr('run_non_litigation_flow.generate_html_report', lambda *args, **kwargs: None)

    summary = build_run_summary(ROOT, sample_root=batch2_root)
    assert summary['input_root'] == str(batch2_root / '原始文件')
    assert summary['result_root'] == str(USER_DATA_DIR / 'output' / 'non-litigation-results-batch2')
    assert summary['html_report_path'] == str(USER_DATA_DIR / 'output' / 'ocr-validation-report-batch2.html')


def test_build_run_summary_should_allow_injected_paths(monkeypatch, tmp_path: Path):
    sample_root = ROOT / '样本材料' / '非诉组自动化样本材料'
    result_root = tmp_path / 'custom-results'
    html_report_path = tmp_path / 'custom-report.html'

    monkeypatch.setattr('run_non_litigation_flow.build_mock_ocr_results', lambda *args, **kwargs: {})
    monkeypatch.setattr('run_non_litigation_flow.export_non_litigation_standard_outputs', lambda **kwargs: {'created_count': 3})
    monkeypatch.setattr('run_non_litigation_flow.evaluate_non_litigation_quality', lambda *args, **kwargs: {'total_files': 3, 'page_count_matched': 3, 'page_count_match_rate': 1.0})
    monkeypatch.setattr('run_non_litigation_flow.load_non_litigation_cases', lambda sample_root: [{'sequence': '1', 'notice_number': 'X', 'company_name': 'Y'}])
    monkeypatch.setattr('run_non_litigation_flow.validate_ocr_results', lambda *args, **kwargs: {'summary': {'total': 3, 'passed': 3, 'warnings': 0, 'failed': 0, 'pass_rate': 1.0}, 'failed_items': [], 'warning_items': [], 'accuracy_summary': {'same_root_remap_warnings': 0, 'notice_failures': 0, 'basis_mismatch_warnings': 0, 'fuzzy_mapping_warnings': 0, 'ocr_or_heuristic_failures': 0, 'documents_with_high_fallback': 1, 'fallback_pages_total': 2}})
    monkeypatch.setattr('run_non_litigation_flow.generate_html_report', lambda *args, **kwargs: None)

    summary = build_run_summary(
        ROOT,
        sample_root=sample_root,
        result_root=result_root,
        html_report_path=html_report_path,
    )

    assert summary['result_root'] == str(result_root)
    assert summary['html_report_path'] == str(html_report_path)
    assert summary['export_runtime_seconds'] >= 0


def test_infer_paths_for_sample_root_should_pick_batch_specific_paths():
    batch1 = infer_paths_for_sample_root(ROOT / '样本材料' / '非诉组自动化样本材料')
    batch2 = infer_paths_for_sample_root(BATCH2_SAMPLE_ROOT)

    assert batch1['summary_path'] == DEFAULT_SUMMARY_PATH
    assert batch2['summary_path'].name == 'non-litigation-run-summary-batch2.json'
    assert batch2['result_root'].name == 'non-litigation-results-batch2'


def test_clean_rebuildable_outputs_should_only_remove_whitelisted_generated_paths(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        'run_non_litigation_flow.REBUILDABLE_PATHS',
        [
            tmp_path / 'output' / 'non-litigation-results',
            tmp_path / 'output' / 'non-litigation-run-summary.json',
        ],
    )

    generated_dir = tmp_path / 'output' / 'non-litigation-results'
    generated_dir.mkdir(parents=True)
    (generated_dir / 'x.pdf').write_text('x', encoding='utf-8')

    generated_file = tmp_path / 'output' / 'non-litigation-run-summary.json'
    generated_file.parent.mkdir(parents=True, exist_ok=True)
    generated_file.write_text('{}', encoding='utf-8')

    untouched = tmp_path / 'output' / 'keep-me'
    untouched.mkdir(parents=True)
    (untouched / 'manual.pdf').write_text('keep', encoding='utf-8')

    removed = clean_rebuildable_outputs()

    assert str(generated_dir) in removed
    assert str(generated_file) in removed
    assert not generated_dir.exists()
    assert not generated_file.exists()
    assert untouched.exists()


def test_build_aggregate_summary_should_merge_batch_metrics():
    batch_summaries = [
        {
            'batch_name': 'batch1',
            'label': '第一批',
            'sample_root': 'sample-1',
            'result_root': 'result-1',
            'html_report_path': 'report-1.html',
            'summary_path': 'summary-1.json',
            'runtime_seconds': 12.5,
            'export_runtime_seconds': 2.5,
            'quality': {'total_files': 10, 'page_count_matched': 9, 'page_count_match_rate': 0.9},
            'validation': {
                'summary': {'total': 10, 'passed': 8, 'warnings': 1, 'failed': 1, 'pass_rate': 0.8},
                'accuracy_summary': {'same_root_remap_warnings': 1, 'notice_failures': 1, 'basis_mismatch_warnings': 1, 'fuzzy_mapping_warnings': 0, 'ocr_or_heuristic_failures': 1, 'documents_with_high_fallback': 1, 'fallback_pages_total': 2},
            },
        },
        {
            'batch_name': 'batch2',
            'label': '第二批',
            'sample_root': 'sample-2',
            'result_root': 'result-2',
            'html_report_path': 'report-2.html',
            'summary_path': 'summary-2.json',
            'runtime_seconds': 7.5,
            'export_runtime_seconds': 1.5,
            'quality': {'total_files': 20, 'page_count_matched': 19, 'page_count_match_rate': 0.95},
            'validation': {
                'summary': {'total': 20, 'passed': 18, 'warnings': 2, 'failed': 0, 'pass_rate': 0.9},
                'accuracy_summary': {'same_root_remap_warnings': 2, 'notice_failures': 0, 'basis_mismatch_warnings': 2, 'fuzzy_mapping_warnings': 1, 'ocr_or_heuristic_failures': 0, 'documents_with_high_fallback': 1, 'fallback_pages_total': 3},
            },
        },
    ]

    summary = build_aggregate_summary(batch_summaries, mode='real_ocr')
    text = format_all_batches_summary(summary)

    assert summary['total_runtime_seconds'] == 20.0
    assert summary['overall_page_count_match_rate'] == 0.9333
    assert summary['overall_validation_pass_rate'] == 0.8667
    assert summary['accuracy_summary']['same_root_remap_warnings'] == 3
    assert summary['accuracy_summary']['notice_failures'] == 1
    assert summary['accuracy_summary']['basis_mismatch_warnings'] == 3
    assert summary['accuracy_summary']['fuzzy_mapping_warnings'] == 1
    assert summary['accuracy_summary']['ocr_or_heuristic_failures'] == 1
    assert summary['accuracy_summary']['documents_with_high_fallback'] == 2
    assert summary['accuracy_summary']['fallback_pages_total'] == 5
    assert '两批合计总耗时:' in text
    assert '总体识别准确率:' in text
    assert '总体业务导出准确率:' in text


def test_build_batch_config_should_return_expected_batch_paths():
    batch1 = build_batch_config('batch1')
    batch2 = build_batch_config('batch2')

    assert batch1['summary_path'] == DEFAULT_SUMMARY_PATH
    assert batch2['summary_path'].name == 'non-litigation-run-summary-batch2.json'
    assert ALL_BATCH_SUMMARY_PATH.name == 'non-litigation-run-summary-all-batches.json'


def test_format_summary_should_use_ascii_labels():
    summary = {
        'mode': 'real_ocr',
        'ocr_run_kind': 'real',
        'ocr_files_count': 5,
        'sample_root': 'sample-root',
        'input_root': 'input-root',
        'result_root': 'result-root',
        'html_report_path': 'report.html',
        'runtime_seconds': 10.0,
        'export_runtime_seconds': 2.0,
        'phase_timings': {'ocr_seconds': 1.0, 'validation_seconds': 0.5, 'report_seconds': 0.2},
        'created_count': 5,
        'quality': {'page_count_matched': 5, 'total_files': 5, 'page_count_match_rate': 1.0},
        'output_folders': {'输出文件（申请书）': ['a.pdf']},
        'validation': {
            'summary': {'total': 5, 'passed': 4, 'warnings': 1, 'failed': 0, 'pass_rate': 0.8},
            'failed_items': [],
            'warning_items': [{'file_name': '1.pdf', 'message': 'warning'}],
            'accuracy_summary': {
                'same_root_remap_warnings': 1,
                'notice_failures': 0,
                'basis_mismatch_warnings': 1,
                'fuzzy_mapping_warnings': 0,
                'ocr_or_heuristic_failures': 0,
                'documents_with_high_fallback': 0,
                'fallback_pages_total': 0,
            },
        },
    }

    text = format_summary(summary)
    assert '[INFO] 处理结果汇总' in text
    assert 'OCR 运行类型: real' in text
    assert 'OCR/规则真实失败: 0' in text


def test_format_all_batches_summary_should_show_run_kind_and_diagnostics():
    summary = {
        'mode': 'real_ocr',
        'batches': [
            {
                'label': '第一批',
                'batch_name': 'batch1',
                'sample_root': 'sample-1',
                'result_root': 'result-1',
                'html_report_path': 'report-1.html',
                'summary_path': 'summary-1.json',
                'runtime_seconds': 5.0,
                'export_runtime_seconds': 1.0,
                'phase_timings': {'ocr_seconds': 1.0},
                'ocr_run_kind': 'real',
                'ocr_files_count': 5,
                'validation_summary': {'pass_rate': 0.9},
                'quality': {'page_count_match_rate': 1.0},
                'accuracy_summary': {
                    'basis_mismatch_warnings': 1,
                    'fuzzy_mapping_warnings': 1,
                    'ocr_or_heuristic_failures': 0,
                    'same_root_remap_warnings': 1,
                    'notice_failures': 0,
                    'fallback_pages_total': 2,
                },
            }
        ],
        'total_runtime_seconds': 5.0,
        'phase_timings': {'ocr_seconds': 1.0},
        'overall_validation_pass_rate': 0.9,
        'overall_page_count_match_rate': 1.0,
        'accuracy_summary': {
            'basis_mismatch_warnings': 1,
            'fuzzy_mapping_warnings': 1,
            'ocr_or_heuristic_failures': 0,
            'documents_with_high_fallback': 1,
            'same_root_remap_warnings': 1,
            'notice_failures': 0,
            'fallback_pages_total': 2,
        },
    }

    text = format_all_batches_summary(summary)
    assert 'OCR 运行类型: real' in text
    assert '评估口径类 warning（台账/映射）: 1' in text
    assert '模糊映射 warning: 1' in text
    assert 'OCR/规则真实失败: 0' in text
