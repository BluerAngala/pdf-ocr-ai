use std::fs;
use std::path::Path;

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

    Ok(())
}

fn main() {
    if let Err(err) = sync_resources() {
        panic!("failed to sync tauri resources: {err}");
    }

    tauri_build::build()
}
