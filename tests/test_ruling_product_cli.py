from pathlib import Path
import sys
import json
import subprocess

ROOT = Path(__file__).resolve().parent.parent


def test_ruling_product_cli_should_write_result_json(tmp_path: Path):
    result_json = tmp_path / 'ruling-product.json'
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / 'src' / 'ruling_product_cli.py'),
            '--excel', str(ROOT / '样本材料' / '强制组-自动化' / '提取信息' / '非诉表格.xlsx'),
            '--ocr-text', str(ROOT / 'output' / '（2025）粤7101行审3355号_ultra_result.txt'),
            '--result-json', str(result_json),
        ],
        capture_output=True,
    )

    assert result.returncode == 0
    assert result_json.exists()
    payload = json.loads(result_json.read_text(encoding='utf-8'))
    assert 'rows' in payload
