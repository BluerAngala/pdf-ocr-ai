from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_current_regression_artifacts_should_exist():
    required_files = [
        ROOT / 'output' / '7-责催-穗公积金中心越秀责字（2024）914-1号_ultra_result.txt',
        ROOT / 'output' / '8-责催-穗公积金中心越秀责字（2025）856号_ultra_result.txt',
        ROOT / 'output' / '（2025）粤7101行审3355号_ultra_result.txt',
        ROOT / '样本材料' / '非诉组自动化样本材料' / '台账及命名规则.xlsx',
        ROOT / '样本材料' / '强制组-自动化' / '提取信息' / '非诉表格.xlsx',
    ]

    for path in required_files:
        assert path.exists(), str(path)
