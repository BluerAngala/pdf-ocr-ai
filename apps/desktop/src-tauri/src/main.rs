// Prevents additional console window on Windows in release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::path::{Path, PathBuf};
use std::process::Stdio;
use std::sync::{Arc, Mutex};
use tauri::{AppHandle, Manager, State, Window};
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::process::{Child, Command};
use tokio::sync::mpsc;

// Python 服务状态（后台初始化，避免阻塞首屏）
#[derive(Clone)]
struct PythonService {
    child: Arc<Mutex<Option<Child>>>,
    pid: Arc<Mutex<Option<u32>>>,
    request_tx: Arc<Mutex<Option<mpsc::UnboundedSender<String>>>>,
    initialized: Arc<Mutex<bool>>,
    error_message: Arc<Mutex<Option<String>>>,
}

impl PythonService {
    fn placeholder() -> Self {
        Self {
            child: Arc::new(Mutex::new(None)),
            pid: Arc::new(Mutex::new(None)),
            request_tx: Arc::new(Mutex::new(None)),
            initialized: Arc::new(Mutex::new(false)),
            error_message: Arc::new(Mutex::new(None)),
        }
    }
}

// JSON-RPC 请求
#[derive(serde::Serialize)]
struct JsonRpcRequest {
    jsonrpc: String,
    method: String,
    params: serde_json::Value,
    id: u64,
}

// 初始化 Python 服务
async fn init_python_service(
    app_handle: tauri::AppHandle,
) -> Result<(Child, u32, mpsc::UnboundedSender<String>), String> {
    let python_path = get_python_path(&app_handle)?;
    let server_script = get_server_script_path(&app_handle)?;

    let paths = compute_runtime_paths(&app_handle)?;
    let bundled = paths.bundled;
    eprintln!(
        "[init_python_service] Starting Python, bundled={}, root={:?}, resources={:?}",
        bundled, paths.app_root, paths.resources_dir
    );
    eprintln!("[init_python_service] python_path={:?}", python_path);
    eprintln!("[init_python_service] server_script={:?}", server_script);
    
    if !std::path::Path::new(&python_path).exists() {
        return Err(format!("Python executable not found: {:?}", python_path));
    }

    let mut cmd = Command::new(&python_path);
    if !bundled {
        cmd.arg(&server_script);
    }
    cmd.current_dir(&paths.app_root)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .env("GJJ_OCR_ROOT", paths.app_root.as_str())
        .env("GJJ_OCR_RESOURCES", paths.resources_dir.as_str())
        .env("GJJ_OCR_USER_DATA", paths.user_data_dir.as_str())
        .env("PYTHONUTF8", "1")
        .env("PYTHONIOENCODING", "utf-8");

    #[cfg(target_os = "windows")]
    {
        #[allow(unused_imports)]
        use std::os::windows::process::CommandExt;
        cmd.creation_flags(0x0800_0000); // CREATE_NO_WINDOW
    }

    let mut child = cmd.spawn()
        .map_err(|e| format!("Failed to start Python: {}", e))?;

    let stdin = child.stdin.take().ok_or("Failed to get stdin")?;
    let stdout = child.stdout.take().ok_or("Failed to get stdout")?;
    let stderr = child.stderr.take().ok_or("Failed to get stderr")?;

    let (request_tx, mut request_rx) = mpsc::unbounded_channel::<String>();

    // 写入线程
    let mut stdin = stdin;
    tokio::spawn(async move {
        while let Some(request) = request_rx.recv().await {
            if let Err(e) = stdin.write_all(request.as_bytes()).await {
                eprintln!("Failed to write to Python stdin: {}", e);
                break;
            }
            if let Err(e) = stdin.write_all(b"\n").await {
                eprintln!("Failed to write newline: {}", e);
                break;
            }
            if let Err(e) = stdin.flush().await {
                eprintln!("Failed to flush stdin: {}", e);
                break;
            }
        }
    });

    // 读取 stdout 线程
    let app_handle_clone = app_handle.clone();
    tokio::spawn(async move {
        let reader = BufReader::new(stdout);
        let mut lines = reader.lines();

        while let Ok(Some(line)) = lines.next_line().await {
            if let Ok(response) = serde_json::from_str::<serde_json::Value>(&line) {
                if response.get("jsonrpc").is_some() {
                    let _ = app_handle_clone.emit_all("jsonrpc-response", response);
                    continue;
                }
            }
            let notification = serde_json::json!({
                "jsonrpc": "2.0",
                "method": "notify.log",
                "params": {"level": "info", "message": line}
            });
            let _ = app_handle_clone.emit_all("jsonrpc-notification", notification);
        }
    });

    // 读取 stderr 线程（进度推送）
    let app_handle_clone = app_handle.clone();
    tokio::spawn(async move {
        let reader = BufReader::new(stderr);
        let mut lines = reader.lines();

        while let Ok(Some(line)) = lines.next_line().await {
            if let Ok(notification) = serde_json::from_str::<serde_json::Value>(&line) {
                let _ = app_handle_clone.emit_all("jsonrpc-notification", notification);
            }
        }
        eprintln!("[Python stderr] stderr reader exited");
    });

    // 等待一小段时间确保 Python 启动成功
    tokio::time::sleep(tokio::time::Duration::from_millis(500)).await;

    // 检查进程是否还在运行
    match child.try_wait() {
        Ok(Some(status)) => {
            return Err(format!("Python process exited immediately with status: {:?}", status));
        }
        Ok(None) => {
            eprintln!("[init_python_service] Python process is running");
        }
        Err(e) => {
            return Err(format!("Failed to check Python process status: {}", e));
        }
    }

    let pid: u32 = child.id().ok_or("Failed to get Python PID")?;
    Ok((child, pid, request_tx))
}

/// 运行时路径（Rust / 前端 / Python 共用语义，由 Tauri PathResolver + 少量回退推导）
#[derive(Clone, serde::Serialize)]
#[serde(rename_all = "camelCase")]
struct RuntimePathsDto {
    app_root: String,
    resources_dir: String,
    user_data_dir: String,
    bundled: bool,
}

fn get_app_dir() -> Result<PathBuf, String> {
    let exe_path = std::env::current_exe()
        .map_err(|e| format!("Failed to get current exe: {}", e))?;
    Ok(exe_path
        .parent()
        .ok_or("Cannot determine app directory")?
        .to_path_buf())
}

/// 历史用户数据目录（升级安装时优先沿用，避免缓存丢失）
fn legacy_user_data_dir() -> PathBuf {
    if let Ok(local) = std::env::var("LOCALAPPDATA") {
        return PathBuf::from(local).join("gjj-ocr-tool");
    }
    PathBuf::from("user-data")
}

/// 可写目录：优先 Tauri app_data_dir API，若已有 legacy 目录则继续沿用
fn resolve_user_data_dir(app: &AppHandle) -> Result<PathBuf, String> {
    if let Ok(env) = std::env::var("GJJ_OCR_USER_DATA") {
        let p = PathBuf::from(env);
        std::fs::create_dir_all(&p).map_err(|e| format!("无法创建用户目录 {:?}: {}", p, e))?;
        return Ok(p);
    }
    let legacy = legacy_user_data_dir();
    if legacy.exists() {
        return Ok(legacy);
    }
    if let Some(dir) = app.path_resolver().app_data_dir() {
        std::fs::create_dir_all(&dir).map_err(|e| format!("无法创建用户目录 {:?}: {}", dir, e))?;
        return Ok(dir);
    }
    std::fs::create_dir_all(&legacy).map_err(|e| format!("无法创建用户目录 {:?}: {}", legacy, e))?;
    Ok(legacy)
}

/// 开发态 resources：仓库 resources/ 或 src-tauri/resources/
fn resolve_dev_resources_dir(project_root: &Path) -> Result<PathBuf, String> {
    let bundled_layout = project_root.join("sample-data");
    if bundled_layout.is_dir() {
        return Ok(project_root.to_path_buf());
    }
    let project_resources = project_root.join("resources");
    if project_resources.join("sample-data").is_dir() {
        return Ok(project_resources);
    }
    let tauri_resources = project_root
        .join("apps")
        .join("desktop")
        .join("src-tauri")
        .join("resources");
    if tauri_resources.join("sample-data").is_dir() {
        return Ok(tauri_resources);
    }
    if project_resources.is_dir() {
        return Ok(project_resources);
    }
    Ok(project_root.to_path_buf())
}

/// 生产态 resources：优先 Tauri resource_dir()，否则安装目录下 resources/
fn resolve_bundled_resources_dir(app: &AppHandle, app_root: &Path) -> PathBuf {
    if let Some(dir) = app.path_resolver().resource_dir() {
        if dir.join("config.yaml").is_file() || dir.join("sample-data").is_dir() {
            return dir;
        }
    }
    app_root.join("resources")
}

fn is_bundled() -> bool {
    // Debug 开发始终用 venv + apps/server/src，避免 target/debug/resources 里的过期 server_src
    #[cfg(debug_assertions)]
    {
        return false;
    }
    #[cfg(not(debug_assertions))]
    {
        if let Ok(exe_path) = std::env::current_exe() {
            if let Some(exe_dir) = exe_path.parent() {
                let onedir = exe_dir
                    .join("resources")
                    .join("gjj-ocr-server")
                    .join("gjj-ocr-server.exe");
                if onedir.exists() {
                    eprintln!("[is_bundled] Detected onedir server: {:?}", onedir);
                    return true;
                }
                // 兼容旧安装包中的 onefile 后端
                let onefile = exe_dir.join("resources").join("gjj-ocr-server.exe");
                if onefile.exists() {
                    eprintln!("[is_bundled] Detected legacy onefile server: {:?}", onefile);
                    return true;
                }
            }
        }
        false
    }
}

fn get_dev_project_root() -> Result<PathBuf, String> {
    let current_dir = std::env::current_dir()
        .map_err(|e| format!("Failed to get current dir: {}", e))?;

    let mut check_dir = current_dir.clone();
    for _ in 0..5 {
        if let Some(parent) = check_dir.parent() {
            if check_dir.file_name() == Some(std::ffi::OsStr::new("debug"))
                || check_dir.file_name() == Some(std::ffi::OsStr::new("release"))
                || check_dir.file_name() == Some(std::ffi::OsStr::new("target"))
            {
                check_dir = parent.to_path_buf();
                continue;
            }
            if check_dir.file_name() == Some(std::ffi::OsStr::new("src-tauri")) {
                if let Some(apps_desktop) = parent.parent() {
                    if let Some(project_root) = apps_desktop.parent() {
                        return Ok(project_root.to_path_buf());
                    }
                }
            }
            check_dir = parent.to_path_buf();
        } else {
            break;
        }
    }

    Ok(current_dir)
}

/// 统一路径入口：前端 invoke、Python 环境变量注入均走此处
fn compute_runtime_paths(app: &AppHandle) -> Result<RuntimePathsDto, String> {
    let bundled = is_bundled();
    let app_root = if bundled {
        get_app_dir()?
    } else {
        get_dev_project_root()?
    };
    let resources_dir = if bundled {
        resolve_bundled_resources_dir(app, &app_root)
    } else {
        resolve_dev_resources_dir(&app_root)?
    };
    let user_data_dir = resolve_user_data_dir(app)?;
    Ok(RuntimePathsDto {
        app_root: app_root.to_string_lossy().to_string(),
        resources_dir: resources_dir.to_string_lossy().to_string(),
        user_data_dir: user_data_dir.to_string_lossy().to_string(),
        bundled,
    })
}

fn bundled_server_exe(resources: &Path) -> Result<PathBuf, String> {
    let onedir = resources
        .join("gjj-ocr-server")
        .join("gjj-ocr-server.exe");
    if onedir.exists() {
        return Ok(onedir);
    }
    let onefile = resources.join("gjj-ocr-server.exe");
    if onefile.exists() {
        return Ok(onefile);
    }
    Err(format!(
        "Bundled server not found under {:?} (expected gjj-ocr-server/ or gjj-ocr-server.exe)",
        resources
    ))
}

fn get_python_path(app_handle: &AppHandle) -> Result<String, String> {
    if is_bundled() {
        let paths = compute_runtime_paths(app_handle)?;
        let exe_path = bundled_server_exe(Path::new(&paths.resources_dir))?;
        println!("Using bundled server exe: {:?}", exe_path);
        return Ok(exe_path.to_string_lossy().to_string());
    }

    let project_root = get_dev_project_root()?;
    let venv_python = project_root.join(".venv312").join("Scripts").join("python.exe");
    if venv_python.exists() {
        println!("Using venv Python: {:?}", venv_python);
        return Ok(venv_python.to_string_lossy().to_string());
    }
    Ok("python".to_string())
}

fn get_server_script_path(_app_handle: &AppHandle) -> Result<String, String> {
    if is_bundled() {
        return Ok(String::new());
    }
    let project_root = get_dev_project_root()?;
    let server_script = project_root.join("apps").join("server").join("src").join("server.py");
    if !server_script.exists() {
        return Err(format!("Server script not found: {:?}", server_script));
    }
    Ok(server_script.to_string_lossy().to_string())
}

/// 运行时路径（安装目录 / 内嵌 resources / 用户数据）。前端与 Python 均不应硬编码路径。
#[tauri::command]
fn get_runtime_paths(app: AppHandle) -> Result<RuntimePathsDto, String> {
    compute_runtime_paths(&app)
}

#[tauri::command]
fn get_project_root_cmd(app: AppHandle) -> Result<String, String> {
    Ok(compute_runtime_paths(&app)?.app_root)
}

#[tauri::command]
fn is_production_bundle() -> bool {
    is_bundled()
}

// Tauri 命令：发送 JSON-RPC 请求
#[tauri::command]
async fn send_jsonrpc_request(
    service: State<'_, PythonService>,
    method: String,
    params: serde_json::Value,
    id: u64,
) -> Result<(), String> {
    let initialized = *service
        .initialized
        .lock()
        .map_err(|e| format!("Lock error: {}", e))?;
    if !initialized {
        let err = service
            .error_message
            .lock()
            .ok()
            .and_then(|g| g.clone())
            .unwrap_or_else(|| "后端正在启动，请稍候".to_string());
        return Err(format!("Python service not initialized: {}", err));
    }

    let request = JsonRpcRequest {
        jsonrpc: "2.0".to_string(),
        method,
        params,
        id,
    };

    let request_json = serde_json::to_string(&request)
        .map_err(|e| format!("Failed to serialize request: {}", e))?;

    eprintln!("[send_jsonrpc_request] Sending request: {}", request_json);

    let tx = service
        .request_tx
        .lock()
        .map_err(|e| format!("Lock error: {}", e))?
        .clone()
        .ok_or("Python service request channel not available")?;
    tx.send(request_json)
        .map_err(|e| format!("Failed to send request: {}", e))?;
    eprintln!("[send_jsonrpc_request] Request queued successfully");

    Ok(())
}

// Tauri 命令：强制终止 Python 进程
#[tauri::command]
async fn kill_python(service: State<'_, PythonService>) -> Result<(), String> {
    let pid = service
        .pid
        .lock()
        .map_err(|e| format!("Lock error: {}", e))?
        .ok_or("Python process not running")?;
    if pid != 0 {
        #[cfg(target_os = "windows")]
        {
            std::process::Command::new("taskkill")
                .args(["/F", "/T", "/PID", &pid.to_string()])
                .spawn()
                .map_err(|e| format!("Failed to kill Python (PID {}): {}", pid, e))?;
        }
        #[cfg(not(target_os = "windows"))]
        {
            std::process::Command::new("kill")
                .args(["-9", &pid.to_string()])
                .spawn()
                .map_err(|e| format!("Failed to kill Python (PID {}): {}", pid, e))?;
        }
        eprintln!("[kill_python] Python process (PID {}) killed", pid);
    }
    *service.initialized.lock().map_err(|e| format!("Lock error: {}", e))? = false;
    Ok(())
}

// Tauri 命令：选择文件夹
#[tauri::command]
async fn select_folder(window: Window) -> Result<Option<String>, String> {
    let (tx, rx) = std::sync::mpsc::channel();
    
    tauri::api::dialog::FileDialogBuilder::new()
        .set_parent(&window)
        .pick_folder(move |folder| {
            let _ = tx.send(folder);
        });

    let folder = rx.recv().map_err(|e| format!("Failed to receive: {}", e))?;
    Ok(folder.map(|p: std::path::PathBuf| p.to_string_lossy().to_string()))
}

// Tauri 命令：打开文件/文件夹（用系统默认程序）
#[tauri::command]
async fn open_path(path: String) -> Result<(), String> {
    #[cfg(target_os = "windows")]
    {
        std::process::Command::new("explorer")
            .arg(&path)
            .spawn()
            .map_err(|e| format!("无法打开: {}", e))?;
    }
    #[cfg(target_os = "macos")]
    {
        std::process::Command::new("open")
            .arg(&path)
            .spawn()
            .map_err(|e| format!("无法打开: {}", e))?;
    }
    #[cfg(target_os = "linux")]
    {
        std::process::Command::new("xdg-open")
            .arg(&path)
            .spawn()
            .map_err(|e| format!("无法打开: {}", e))?;
    }
    Ok(())
}

// Tauri 命令：用系统浏览器打开 URL
#[tauri::command]
async fn open_url(url: String) -> Result<(), String> {
    #[cfg(target_os = "windows")]
    {
        std::process::Command::new("cmd")
            .args(["/C", "start", "", &url])
            .spawn()
            .map_err(|e| format!("无法打开链接: {}", e))?;
    }
    #[cfg(target_os = "macos")]
    {
        std::process::Command::new("open")
            .arg(&url)
            .spawn()
            .map_err(|e| format!("无法打开链接: {}", e))?;
    }
    #[cfg(target_os = "linux")]
    {
        std::process::Command::new("xdg-open")
            .arg(&url)
            .spawn()
            .map_err(|e| format!("无法打开链接: {}", e))?;
    }
    Ok(())
}

// Tauri 命令：选择文件
#[tauri::command]
async fn select_files(
    window: Window,
    multiple: bool,
) -> Result<Option<Vec<String>>, String> {
    if multiple {
        let (tx, rx) = std::sync::mpsc::channel::<Option<Vec<std::path::PathBuf>>>();
        
        tauri::api::dialog::FileDialogBuilder::new()
            .set_parent(&window)
            .pick_files(move |files| {
                let _ = tx.send(files);
            });

        let files = rx.recv().map_err(|e| format!("Failed to receive: {}", e))?;
        Ok(files.map(|f| {
            f.into_iter().map(|p| p.to_string_lossy().to_string()).collect()
        }))
    } else {
        let (tx, rx) = std::sync::mpsc::channel::<Option<std::path::PathBuf>>();
        
        tauri::api::dialog::FileDialogBuilder::new()
            .set_parent(&window)
            .pick_file(move |file| {
                let _ = tx.send(file);
            });

        let file = rx.recv().map_err(|e| format!("Failed to receive: {}", e))?;
        Ok(file.map(|f| vec![f.to_string_lossy().to_string()]))
    }
}

fn main() {
    tauri::Builder::default()
        .setup(|app| {
            let app_handle = app.handle().clone();
            let service = PythonService::placeholder();
            app.manage(service.clone());

            tauri::async_runtime::spawn(async move {
                let _ = app_handle.emit_all(
                    "backend-init-progress",
                    serde_json::json!({ "step": "python" }),
                );
                match init_python_service(app_handle.clone()).await {
                    Ok((child, pid, request_tx)) => {
                        *service.child.lock().unwrap() = Some(child);
                        *service.pid.lock().unwrap() = Some(pid);
                        *service.request_tx.lock().unwrap() = Some(request_tx);
                        *service.initialized.lock().unwrap() = true;
                        *service.error_message.lock().unwrap() = None;
                        println!("Python service initialized successfully");
                        let _ = app_handle.emit_all("python-service-ready", ());
                    }
                    Err(e) => {
                        eprintln!("Failed to initialize Python service: {}", e);
                        *service.error_message.lock().unwrap() = Some(e.clone());
                        let _ = app_handle.emit_all("python-service-error", e);
                    }
                }
            });

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            send_jsonrpc_request,
            kill_python,
            select_folder,
            select_files,
            open_path,
            open_url,
            get_runtime_paths,
            get_project_root_cmd,
            is_production_bundle,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
