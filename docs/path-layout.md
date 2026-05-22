# 路径管理：告别硬编码，拥抱 API

## 原则

| 层级 | 职责 | 禁止 |
|------|------|------|
| **Tauri (Rust)** | 用 `PathResolver` 解析安装目录、内嵌 `resources`、用户数据目录 | 在前端/业务里写 `C:\...\pdf识别\样本材料` |
| **Python** | 用 `core.paths` + `preset_paths` 在多个根下解析相对路径；RPC 返回**绝对路径** | `ROOT / "sample-data"` 且假定 ROOT 一定是仓库根 |
| **前端 (React)** | `invoke("get_runtime_paths")` + `system.get_presets` / `system.describe_paths` | 维护第二份预设相对路径表 |

## 三个目录

- **appRoot** — 应用根（开发=仓库根，生产=exe 所在安装目录）
- **resourcesDir** — 只读资源：`config.yaml`、`sample-data/`、`poppler/`、`server_src/`
- **userDataDir** — 可写：`output/`、OCR 缓存等（优先沿用 `%LOCALAPPDATA%\gjj-ocr-tool`，否则 Tauri `app_data_dir()`）

Rust 启动 Python 时注入环境变量：`GJJ_OCR_ROOT`、`GJJ_OCR_RESOURCES`、`GJJ_OCR_USER_DATA`。

## 前端 API

```ts
import { getRuntimePaths } from "./services/paths";
const paths = await getRuntimePaths();
// paths.resourcesDir — 不要自己拼
```

```ts
import { getPresets } from "./presets";
const presets = await getPresets(); // 内部调用 system.get_presets
```

## 打包

`build.rs` 把要带进安装包的内容同步到 `apps/desktop/src-tauri/resources/`，再由 `tauri.conf.json` → `bundle.resources` 复制到安装目录的 `resources/`。

开发态额外使用仓库 `样本材料/` 与 `resources/sample-data/`（全批次）；安装包仅嵌入 `non-litigation-batch1`。

## 发版自检

1. 日志中有 `APP_ROOT=...\GJJ-OCR-Tool`、`RESOURCES=...\resources\config.yaml (exists=True)`
2. `system.get_presets` 至少解析出 `non-litigation-batch1`
3. `tauri.conf.json` 的 `bundle.resources` 必须包含 `resources/server_src/**`
4. 版本号在 `tauri.conf.json` 和 `Cargo.toml` 两处保持一致
5. 旧版安装残留会在版本号变化时自动清理（`output/`、`temp/`、`ocr-gpu-cache.json`）
