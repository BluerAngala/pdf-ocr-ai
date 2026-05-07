from pathlib import Path
import sys
import json
import subprocess

ROOT = Path(__file__).resolve().parent.parent


def test_notice_product_cli_should_write_result_json(tmp_path: Path):
    result_json = tmp_path / 'notice-product.json'
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / 'src' / 'notice_product_cli.py'),
            '--ledger-excel', str(ROOT / '样本材料' / '非诉组自动化样本材料' / '台账及命名规则.xlsx'),
            '--input-dir', str(ROOT / 'input'),
            '--output-dir', str(ROOT / 'output'),
            '--result-json', str(result_json),
        ],
        capture_output=True,
    )

    assert result.returncode == 0
    assert result_json.exists()
    payload = json.loads(result_json.read_text(encoding='utf-8'))
    assert 'summary' in payload
