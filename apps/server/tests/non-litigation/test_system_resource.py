import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SRC = ROOT / 'apps' / 'server' / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from system_resource import detect_system_resources, ResourceProfile, OCR_MODEL_MEMORY_GB


def test_detect_system_resources_returns_valid_profile():
    profile = detect_system_resources()
    assert isinstance(profile, ResourceProfile)
    assert profile.cpu_count >= 1
    assert profile.total_memory_gb > 0
    assert profile.available_memory_gb > 0
    assert profile.recommended_workers >= 1
    assert profile.memory_per_worker_gb > 0
    assert profile.safety_level in ('high', 'moderate', 'low', 'critical')


def test_recommended_workers_reserves_memory():
    profile = detect_system_resources(reserve_gb=2.0)
    max_memory_workers = int((profile.available_memory_gb - 2.0) / OCR_MODEL_MEMORY_GB)
    expected = max(1, min(max_memory_workers, profile.cpu_count - 1 if profile.cpu_count > 2 else 1))
    assert profile.recommended_workers <= expected + 1


def test_max_workers_caps_result():
    profile = detect_system_resources(max_workers=1)
    assert profile.recommended_workers == 1


def test_str_representation():
    profile = detect_system_resources()
    text = str(profile)
    assert 'CPU' in text
    assert 'GB' in text


def test_reserve_gb_reduces_workers_on_tight_memory():
    large_reserve = detect_system_resources(reserve_gb=100.0)
    normal = detect_system_resources(reserve_gb=1.5)
    assert large_reserve.recommended_workers <= normal.recommended_workers


def test_profile_safety_level_consistency():
    profile = detect_system_resources()
    needed = profile.recommended_workers * OCR_MODEL_MEMORY_GB
    if needed >= profile.available_memory_gb * 0.85:
        assert profile.safety_level == 'critical'
    elif needed >= profile.available_memory_gb * 0.65:
        assert profile.safety_level == 'low'
    elif needed >= profile.available_memory_gb * 0.45:
        assert profile.safety_level == 'moderate'
    else:
        assert profile.safety_level == 'high'
