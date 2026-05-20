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

/// 将仓库 样本材料/ 同步为 sample-data/ 布局，供打包 exe 与开发 resources 共用。
fn sync_sample_data(project_root: &Path, dst_sample_data: &Path) -> std::io::Result<()> {
    let samples_root = project_root.join("样本材料");
    if !samples_root.is_dir() {
        eprintln!(
            "[build] skip sample-data sync: not found {:?}",
            samples_root
        );
        return Ok(());
    }

    let mappings: &[(&[&str], &str)] = &[
        (
            &["非诉组自动化样本材料"],
            "non-litigation-batch1",
        ),
        (
            &["非诉组自动化样本材料（第2批）"],
            "non-litigation-batch2",
        ),
        (
            &["强制组-自动化", "提取信息"],
            "enforcement/extract",
        ),
        (
            &["强制组-自动化", "自动打印"],
            "enforcement/print",
        ),
        (&["企业信息查询"], "company-query"),
    ];

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

    // Tauri 打包资源 + 仓库 resources/（开发时 Python ROOT/resources）
    let targets: [PathBuf; 2] = [
        resources_dir.join("sample-data"),
        project_root.join("resources").join("sample-data"),
    ];
    for dst in &targets {
        if let Some(parent) = dst.parent() {
            fs::create_dir_all(parent)?;
        }
        sync_sample_data(project_root, dst)?;
    }

    Ok(())
}

fn main() {
    if let Err(err) = sync_resources() {
        panic!("failed to sync tauri resources: {err}");
    }

    tauri_build::build()
}
