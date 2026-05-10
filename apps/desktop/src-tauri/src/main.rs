// Prevents additional console window on Windows in release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::process::Stdio;
use std::sync::{Arc, Mutex};
use tauri::{Manager, State, Window};
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::process::{Child, Command};
use tokio::sync::mpsc;

// Python 服务状态
#[allow(dead_code)]
struct PythonService {
    child: Arc<Mutex<Option<Child>>>,
    request_tx: Option<mpsc::UnboundedSender<String>>,
    initialized: bool,
    error_message: Option<String>,
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
async fn init_python_service(app_handle: tauri::AppHandle) -> Result<PythonService, String> {
    // 获取 Python 可执行文件路径
    let python_path = get_python_path(&app_handle)?;
    let server_script = get_server_script_path(&app_handle)?;

    // 获取项目根目录作为工作目录
    let project_root = get_project_root()?;
    eprintln!("[init_python_service] Starting Python with working dir: {:?}", project_root);

    // 启动 Python 子进程
    let mut child = Command::new(&python_path)
        .arg(&server_script)
        .current_dir(&project_root)  // 设置工作目录
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("Failed to start Python: {}", e))?;

    let stdin = child.stdin.take().ok_or("Failed to get stdin")?;
    let stdout = child.stdout.take().ok_or("Failed to get stdout")?;
    let stderr = child.stderr.take().ok_or("Failed to get stderr")?;

    let (request_tx, mut request_rx) = mpsc::unbounded_channel::<String>();

    // 写入线程
    let mut stdin = stdin;
    tokio::spawn(async move {
        while let Some(request) = request_rx.recv().await {
            eprintln!("[Rust] Sending request to Python: {}", request);
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
            eprintln!("[Rust] Request sent successfully");
        }
    });

    // 读取 stdout 线程
    let app_handle_clone = app_handle.clone();
    tokio::spawn(async move {
        let reader = BufReader::new(stdout);
        let mut lines = reader.lines();

        while let Ok(Some(line)) = lines.next_line().await {
            eprintln!("[Python stdout] {}", line); // 调试输出
            if let Ok(response) = serde_json::from_str::<serde_json::Value>(&line) {
                // 发送响应到前端
                let _ = app_handle_clone.emit_all("jsonrpc-response", response);
            }
        }
    });

    // 读取 stderr 线程（进度推送）
    let app_handle_clone = app_handle.clone();
    tokio::spawn(async move {
        let reader = BufReader::new(stderr);
        let mut lines = reader.lines();

        while let Ok(Some(line)) = lines.next_line().await {
            eprintln!("[Python stderr] {}", line); // 调试输出
            if let Ok(notification) = serde_json::from_str::<serde_json::Value>(&line) {
                // 发送通知到前端
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

    Ok(PythonService {
        child: Arc::new(Mutex::new(Some(child))),
        request_tx: Some(request_tx),
        initialized: true,
        error_message: None,
    })
}

// 获取项目根目录（从当前可执行文件路径向上查找）
fn get_project_root() -> Result<std::path::PathBuf, String> {
    // 尝试从当前工作目录推断
    let current_dir = std::env::current_dir()
        .map_err(|e| format!("Failed to get current dir: {}", e))?;
    
    println!("Current dir: {:?}", current_dir);
    
    // 如果在 src-tauri/target/debug 或 src-tauri/target/release 目录下
    let mut check_dir = current_dir.clone();
    for _ in 0..5 {
        if let Some(parent) = check_dir.parent() {
            if check_dir.file_name() == Some(std::ffi::OsStr::new("debug"))
                || check_dir.file_name() == Some(std::ffi::OsStr::new("release"))
                || check_dir.file_name() == Some(std::ffi::OsStr::new("target")) {
                check_dir = parent.to_path_buf();
                continue;
            }
            if check_dir.file_name() == Some(std::ffi::OsStr::new("src-tauri")) {
                // 从 src-tauri 向上到 apps/desktop，再到 apps，再到项目根目录 (pdf识别)
                // 路径: .../pdf识别/apps/desktop/src-tauri
                // parent = .../pdf识别/apps/desktop
                // parent.parent() = .../pdf识别/apps
                // parent.parent().parent() = .../pdf识别 (项目根目录)
                if let Some(apps_desktop) = parent.parent() {
                    if let Some(project_root) = apps_desktop.parent() {
                        println!("Project root (from src-tauri): {:?}", project_root);
                        return Ok(project_root.to_path_buf());
                    }
                }
            }
            check_dir = parent.to_path_buf();
        } else {
            break;
        }
    }
    
    // 如果在 apps/desktop 目录下，向上一级到 apps，再向上到项目根目录
    if current_dir.file_name() == Some(std::ffi::OsStr::new("desktop")) {
        if let Some(apps) = current_dir.parent() {
            if let Some(project_root) = apps.parent() {
                println!("Project root (from desktop): {:?}", project_root);
                return Ok(project_root.to_path_buf());
            }
        }
    }
    
    // 如果在 apps 目录下，向上一级到项目根目录
    if current_dir.file_name() == Some(std::ffi::OsStr::new("apps")) {
        if let Some(project_root) = current_dir.parent() {
            println!("Project root (from apps): {:?}", project_root);
            return Ok(project_root.to_path_buf());
        }
    }
    
    println!("Using current dir as project root: {:?}", current_dir);
    // 否则假设当前目录就是项目根目录
    Ok(current_dir)
}

// 获取 Python 路径
fn get_python_path(_app_handle: &tauri::AppHandle) -> Result<String, String> {
    let project_root = get_project_root()?;
    
    // 优先使用虚拟环境（从项目根目录查找）
    let venv_python = if cfg!(target_os = "windows") {
        project_root.join(".venv312").join("Scripts").join("python.exe")
    } else {
        project_root.join(".venv312").join("bin").join("python")
    };

    if venv_python.exists() {
        println!("Using venv Python: {:?}", venv_python);
        return Ok(venv_python.to_string_lossy().to_string());
    }

    // fallback 到系统 Python
    println!("Using system Python");
    Ok("python".to_string())
}

// 获取服务端脚本路径
fn get_server_script_path(_app_handle: &tauri::AppHandle) -> Result<String, String> {
    let project_root = get_project_root()?;
    
    let server_script = project_root.join("apps").join("server").join("src").join("server.py");
    
    if !server_script.exists() {
        return Err(format!("Server script not found: {:?}", server_script));
    }
    
    println!("Server script: {:?}", server_script);
    Ok(server_script.to_string_lossy().to_string())
}

// Tauri 命令：发送 JSON-RPC 请求
#[tauri::command]
async fn send_jsonrpc_request(
    service: State<'_, PythonService>,
    method: String,
    params: serde_json::Value,
    id: u64,
) -> Result<(), String> {
    // 检查服务是否已初始化
    if !service.initialized {
        return Err(format!(
            "Python service not initialized: {}",
            service.error_message.as_deref().unwrap_or("Unknown error")
        ));
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

    if let Some(ref tx) = service.request_tx {
        tx.send(request_json)
            .map_err(|e| format!("Failed to send request: {}", e))?;
        eprintln!("[send_jsonrpc_request] Request queued successfully");
    } else {
        return Err("Python service request channel not available".to_string());
    }

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
            let app_handle = app.handle();

            // 初始化 Python 服务
            let service = tauri::async_runtime::block_on(async {
                match init_python_service(app_handle).await {
                    Ok(service) => {
                        println!("Python service initialized successfully");
                        service
                    }
                    Err(e) => {
                        eprintln!("Failed to initialize Python service: {}", e);
                        // 返回一个未初始化的服务状态，避免 state not managed 错误
                        PythonService {
                            child: Arc::new(Mutex::new(None)),
                            request_tx: None,
                            initialized: false,
                            error_message: Some(e),
                        }
                    }
                }
            });

            // 始终注册服务状态
            app.manage(service);

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            send_jsonrpc_request,
            select_folder,
            select_files,
            open_path,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
