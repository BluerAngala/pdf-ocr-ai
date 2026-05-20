"""
预设样本/台账路径解析 — 开发态与打包 exe 共用同一套逻辑。

开发：ROOT=仓库根目录，优先 样本材料/，其次 resources/sample-data/
打包：ROOT=exe 旁 resources/，使用 resources/sample-data/（由 build 从样本材料同步）
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Literal, Optional, TypedDict

from core.paths import RESOURCES_DIR, ROOT

PresetKind = Literal["sample", "excel"]


class PresetDefinition(TypedDict):
    id: str
    name: str
    description: str
    mode: str
    sample_paths: List[str]
    excel_paths: List[str]


PRESET_DEFINITIONS: List[PresetDefinition] = [
    {
        "id": "non-litigation-batch1",
        "name": "非诉审查 - 第1批",
        "description": "非诉组自动化样本材料（第1批）- 3个案件",
        "mode": "mock",
        "sample_paths": [
            "sample-data/non-litigation-batch1",
            "resources/sample-data/non-litigation-batch1",
            "样本材料/非诉组自动化样本材料",
        ],
        "excel_paths": [
            "sample-data/non-litigation-batch1/台账及命名规则.xlsx",
            "resources/sample-data/non-litigation-batch1/台账及命名规则.xlsx",
            "样本材料/非诉组自动化样本材料/台账及命名规则.xlsx",
        ],
    },
    {
        "id": "non-litigation-batch2",
        "name": "非诉审查 - 第2批",
        "description": "非诉组自动化样本材料（第2批）- 5个案件",
        "mode": "mock",
        "sample_paths": [
            "sample-data/non-litigation-batch2",
            "resources/sample-data/non-litigation-batch2",
            "样本材料/非诉组自动化样本材料（第2批）",
        ],
        "excel_paths": [
            "sample-data/non-litigation-batch2/台账及命名规则.xlsx",
            "resources/sample-data/non-litigation-batch2/台账及命名规则.xlsx",
            "样本材料/非诉组自动化样本材料（第2批）/台账及命名规则.xlsx",
        ],
    },
    {
        "id": "enforcement-extract",
        "name": "强制执行 - 提取信息",
        "description": "强制组-自动化/提取信息 - 裁定书信息提取",
        "mode": "real_ocr",
        "sample_paths": [
            "sample-data/enforcement/extract",
            "resources/sample-data/enforcement/extract",
            "样本材料/强制组-自动化/提取信息",
        ],
        "excel_paths": [
            "sample-data/enforcement/extract/非诉表格.xlsx",
            "resources/sample-data/enforcement/extract/非诉表格.xlsx",
            "样本材料/强制组-自动化/提取信息/非诉表格.xlsx",
            "sample-data/enforcement/extract/cases.xlsx",
        ],
    },
    {
        "id": "enforcement-print",
        "name": "强制执行 - 自动打印",
        "description": "强制组-自动化/自动打印",
        "mode": "real_ocr",
        "sample_paths": [
            "sample-data/enforcement/print",
            "resources/sample-data/enforcement/print",
            "样本材料/强制组-自动化/自动打印",
        ],
        "excel_paths": [
            "sample-data/enforcement/print/AOL网上网立台账.xlsx",
            "resources/sample-data/enforcement/print/AOL网上网立台账.xlsx",
            "样本材料/强制组-自动化/自动打印/AOL网上网立台账.xlsx",
            "sample-data/enforcement/print/aol-ledger.xlsx",
        ],
    },
    {
        "id": "company-query",
        "name": "企业信息查询",
        "description": "企业工商信息、司法信息查询",
        "mode": "mock",
        "sample_paths": [
            "sample-data/company-query",
            "resources/sample-data/company-query",
            "样本材料/企业信息查询",
        ],
        "excel_paths": [
            "sample-data/company-query/001.xlsx",
            "resources/sample-data/company-query/001.xlsx",
            "样本材料/企业信息查询/001.xlsx",
            "样本材料/5月案件-被执行人信息.xlsx",
            "sample-data/company-query/companies.xlsx",
        ],
    },
]

# 兼容 server.py 旧常量名
PRESET_SAMPLE_PATHS: Dict[str, List[str]] = {
    p["id"]: p["sample_paths"] for p in PRESET_DEFINITIONS
}
PRESET_EXCEL_PATHS: Dict[str, List[str]] = {
    p["id"]: p["excel_paths"] for p in PRESET_DEFINITIONS
}


def get_data_roots() -> List[Path]:
    """所有可能挂载 sample-data / 样本材料 的根目录。"""
    roots: List[Path] = []
    seen: set[str] = set()

    def add(path: Path) -> None:
        try:
            resolved = path.resolve()
        except OSError:
            return
        key = str(resolved)
        if key in seen:
            return
        seen.add(key)
        roots.append(resolved)

    add(ROOT)
    add(RESOURCES_DIR)
    project_resources = ROOT / "resources"
    if project_resources.is_dir():
        add(project_resources)

    return roots


def iter_path_candidates(rel: str):
    rel_norm = rel.replace("\\", "/").lstrip("./")
    rel_path = Path(rel_norm)
    seen: set[str] = set()

    for base in get_data_roots():
        variants = [base / rel_path]
        if rel_norm.startswith("resources/"):
            variants.append(base / rel_norm[len("resources/") :])
        elif not rel_norm.startswith("样本材料/"):
            variants.append(base / "resources" / rel_path)

        for candidate in variants:
            try:
                key = str(candidate.resolve())
            except OSError:
                continue
            if key in seen:
                continue
            seen.add(key)
            yield candidate


def resolve_path_candidates(path_list: List[str]) -> Path:
    tried: List[str] = []
    for rel in path_list:
        for candidate in iter_path_candidates(rel):
            tried.append(str(candidate))
            if candidate.exists():
                return candidate.resolve()
        for candidate in iter_path_candidates(rel):
            parent = candidate.parent
            if parent.is_dir():
                for xlsx in sorted(parent.glob("*.xlsx")):
                    if xlsx.name.startswith("~$"):
                        continue
                    tried.append(str(xlsx))
                    return xlsx.resolve()
                break
    raise FileNotFoundError(
        f"所有预设路径均不存在: {path_list} (ROOT={ROOT}, RESOURCES={RESOURCES_DIR}, tried={tried[:16]})"
    )


def resolve_preset(preset_id: str, kind: PresetKind) -> Path:
    key = "sample_paths" if kind == "sample" else "excel_paths"
    for preset in PRESET_DEFINITIONS:
        if preset["id"] == preset_id:
            return resolve_path_candidates(preset[key])
    raise KeyError(f"未知预设: {preset_id}")


def resolve_data_path(relative: str) -> Path:
    return resolve_path_candidates([relative])


def get_resolved_presets() -> List[dict]:
    """供前端 system.get_presets 使用。"""
    out: List[dict] = []
    for preset in PRESET_DEFINITIONS:
        sample = resolve_path_candidates(preset["sample_paths"])
        excel = resolve_path_candidates(preset["excel_paths"])
        out.append(
            {
                "id": preset["id"],
                "name": preset["name"],
                "description": preset["description"],
                "mode": preset["mode"],
                "sampleRoot": str(sample),
                "excelPath": str(excel),
            }
        )
    return out


def get_preset_by_id(preset_id: str) -> Optional[PresetDefinition]:
    for preset in PRESET_DEFINITIONS:
        if preset["id"] == preset_id:
            return preset
    return None
