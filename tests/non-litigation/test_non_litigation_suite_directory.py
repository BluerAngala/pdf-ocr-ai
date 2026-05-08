from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_non_litigation_test_suite_directory_should_exist():
    assert (ROOT / 'tests' / 'non-litigation').exists()


def test_non_litigation_temp_directory_should_be_available_for_test_artifacts():
    target = ROOT / 'temp' / 'non-litigation'
    target.mkdir(parents=True, exist_ok=True)
    assert target.exists()


def test_non_litigation_input_directory_should_be_available_for_source_files():
    target = ROOT / 'input' / 'non-litigation'
    target.mkdir(parents=True, exist_ok=True)
    assert target.exists()
