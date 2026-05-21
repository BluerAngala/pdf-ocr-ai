use std::fs;
use std::path::{Path, PathBuf};

fn copy_dir_all(src: &Path, dst: &Path) -> std::io::Result<()> {
    if !dst.exists() {
        fs::create_dir_all(dst)?;
    }

    for entry in fs::read_dir(src)? {
        let entry = entry?;
        let file_type = entry.file_type()?;
        let target = dst.join(entry.file_name());
        if file_type.is_dir() {
            copy_dir_all(&entry.path(), &target)?;
        } else {
            if let Some(parent) = target.parent() {
                fs::create_dir_all(parent)?;
            }
            fs::copy(entry.path(), target)?;
        }
    }

    Ok(())
}

/// 安装包内嵌样本：仅非诉第 1 批（减小体积；其它模块需用户自选目录）
const BUNDLE_SAMPLE_MAPPINGS: &[(&[&str], &str)] =
    &[(&["非诉组自动化样本材料"], "non-litigation-batch1")];

fn sync_sample_data(
    project_root: &Path,
    dst_sample_data: &Path,
    mappings: &[(&[&str], &str)],
) -> std::io::Result<()> {
    let samples_root = project_root.join("样本材料");
    let repo_sample_data = project_root.join("resources").join("sample-data");

    if !samples_root.is_dir() {
        let repo_batch = repo_sample_data.join("non-litigation-batch1");
        if repo_batch.is_dir() {
            eprintln!(
                "[build] 样本材料/ 不存在，回退仅复制 non-litigation-batch1 {:?}",
                repo_batch
            );
            if dst_sample_data.exists() {
                fs::remove_dir_all(dst_sample_data)?;
            }
            fs::create_dir_all(dst_sample_data)?;
            copy_dir_all(&repo_batch, &dst_sample_data.join("non-litigation-batch1"))?;
            return Ok(());
        }
        eprintln!(
            "[build] skip sample-data sync: not found {:?} nor {:?}",
            samples_root, repo_batch
        );
        return Ok(());
    }

    if dst_sample_data.exists() {
        fs::remove_dir_all(dst_sample_data)?;
    }
    fs::create_dir_all(dst_sample_data)?;

    for (src_parts, dst_rel) in mappings {
        let mut src = samples_root.to_path_buf();
        for part in *src_parts {
            src.push(part);
        }
        if !src.is_dir() {
            eprintln!("[build] skip missing sample source {:?}", src);
            continue;
        }
        let target = dst_sample_data.join(dst_rel);
        if let Some(parent) = target.parent() {
            fs::create_dir_all(parent)?;
        }
        copy_dir_all(&src, &target)?;
        eprintln!("[build] synced {:?} -> {:?}", src, target);
    }

    Ok(())
}

fn verify_sample_data_bundle(dst_sample_data: &Path) -> std::io::Result<()> {
    let marker = dst_sample_data
        .join("non-litigation-batch1")
        .join("台账及命名规则.xlsx");
    if marker.is_file() {
        eprintln!("[build] sample-data OK: {:?}", marker);
        return Ok(());
    }
    Err(std::io::Error::new(
        std::io::ErrorKind::NotFound,
        format!(
            "打包样本缺失: {:?} — 请确认 样本材料/ 或 resources/sample-data/ 存在后重新 build",
            marker
        ),
    ))
}

fn sync_resources() -> std::io::Result<()> {
    let manifest_dir = std::env::var("CARGO_MANIFEST_DIR")
        .map_err(|err| std::io::Error::new(std::io::ErrorKind::Other, err))?;
    let tauri_dir = Path::new(&manifest_dir);
    let desktop_dir = tauri_dir.parent().unwrap();
    let apps_dir = desktop_dir.parent().unwrap();
    let project_root = apps_dir.parent().unwrap();
    let resources_dir = tauri_dir.join("resources");
    let server_src_dst = resources_dir.join("server_src");
    let server_src_src = apps_dir.join("server").join("src");
    let config_src = project_root.join("config.yaml");
    let config_dst = resources_dir.join("config.yaml");

    if server_src_dst.exists() {
        fs::remove_dir_all(&server_src_dst)?;
    }
    copy_dir_all(&server_src_src, &server_src_dst)?;

    if let Some(parent) = config_dst.parent() {
        fs::create_dir_all(parent)?;
    }
    fs::copy(config_src, config_dst)?;

    let tauri_sample = resources_dir.join("sample-data");
    if let Some(parent) = tauri_sample.parent() {
        fs::create_dir_all(parent)?;
    }
    sync_sample_data(project_root, &tauri_sample, BUNDLE_SAMPLE_MAPPINGS)?;

    let dev_sample = project_root.join("resources").join("sample-data");
    if let Some(parent) = dev_sample.parent() {
        fs::create_dir_all(parent)?;
    }
    let dev_mappings: &[(&[&str], &str)] = &[
        (&["非诉组自动化样本材料"], "non-litigation-batch1"),
        (
            &["非诉组自动化样本材料（第2批）"],
            "non-litigation-batch2",
        ),
        (&["强制组-自动化", "提取信息"], "enforcement/extract"),
        (&["强制组-自动化", "自动打印"], "enforcement/print"),
        (&["企业信息查询"], "company-query"),
    ];
    sync_sample_data(project_root, &dev_sample, dev_mappings)?;

    let profile = std::env::var("PROFILE").unwrap_or_default();
    if profile == "release" {
        verify_sample_data_bundle(&tauri_sample)?;
    }

    Ok(())
}

fn find_python(project_root: &Path) -> Option<PathBuf> {
    let venv = project_root.join(".venv312").join("Scripts").join("python.exe");
    if venv.exists() {
        return Some(venv);
    }
    std::process::Command::new("python")
        .arg("--version")
        .output()
        .ok()
        .filter(|o| o.status.success())
        .map(|_| PathBuf::from("python"))
}

/// PyInstaller onefile -> resources/gjj-ocr-server.exe
fn bundle_python_server_onefile(project_root: &Path, resources_dir: &Path) -> std::io::Result<()> {
    if std::env::var("GJJ_SKIP_SERVER_BUNDLE").ok().as_deref() == Some("1") {
        eprintln!("[build] GJJ_SKIP_SERVER_BUNDLE=1, skip PyInstaller");
        return Ok(());
    }

    let dst = resources_dir.join("gjj-ocr-server.exe");
    if dst.is_file() {
        eprintln!("[build] using existing onefile {:?}", dst);
        return Ok(());
    }

    let python = match find_python(project_root) {
        Some(p) => p,
        None => {
            return Err(std::io::Error::new(
                std::io::ErrorKind::NotFound,
                "未找到 Python 3.12（.venv312），无法运行 PyInstaller",
            ));
        }
    };

    let server_dir = project_root.join("apps").join("server");
    let spec = server_dir.join("gjj-ocr-server.spec");
    if !spec.is_file() {
        return Err(std::io::Error::new(
            std::io::ErrorKind::NotFound,
            format!("spec not found: {:?}", spec),
        ));
    }

    eprintln!("[build] PyInstaller onefile via {:?}", python);
    let status = std::process::Command::new(&python)
        .args(["-m", "PyInstaller", "gjj-ocr-server.spec", "--noconfirm", "--clean"])
        .current_dir(&server_dir)
        .status()?;
    if !status.success() {
        return Err(std::io::Error::new(
            std::io::ErrorKind::Other,
            format!("PyInstaller failed with status {status}"),
        ));
    }

    let onefile = server_dir.join("dist").join("gjj-ocr-server.exe");
    if !onefile.is_file() {
        return Err(std::io::Error::new(
            std::io::ErrorKind::NotFound,
            format!("PyInstaller onefile output not found: {:?}", onefile),
        ));
    }

    if let Some(parent) = dst.parent() {
        fs::create_dir_all(parent)?;
    }
    fs::copy(&onefile, &dst)?;
    eprintln!("[build] onefile backend -> {:?}", dst);

    // 避免旧方案残留打进安装包
    let legacy_onedir = resources_dir.join("gjj-ocr-server");
    if legacy_onedir.exists() {
        fs::remove_dir_all(&legacy_onedir)?;
    }
    let legacy_portable = resources_dir.join("python-runtime");
    if legacy_portable.exists() {
        fs::remove_dir_all(&legacy_portable)?;
    }

    Ok(())
}

fn main() {
    if let Err(err) = sync_resources() {
        panic!("failed to sync tauri resources: {err}");
    }

    let manifest_dir = std::env::var("CARGO_MANIFEST_DIR").expect("CARGO_MANIFEST_DIR");
    let tauri_dir = Path::new(&manifest_dir);
    let project_root = tauri_dir.parent().unwrap().parent().unwrap().parent().unwrap();
    let resources_dir = tauri_dir.join("resources");
    if let Err(err) = bundle_python_server_onefile(project_root, &resources_dir) {
        panic!("failed to bundle python server (onefile): {err}");
    }

    tauri_build::build()
}
