// Prevents additional console window on Windows in release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::process::Stdio;
use std::sync::{Arc, Mutex};
use tauri::{Manager, State, Window};
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::process::{Child, Command};
use tokio::sync::mpsc;

// Python 服务状态
struct PythonService {
    child: Arc<Mutex<Option<Child>>>,
    request_tx: mpsc::UnboundedSender<String>,
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

    // 启动 Python 子进程
    let mut child = Command::new(&python_path)
        .arg(&server_script)
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
            if let Ok(notification) = serde_json::from_str::<serde_json::Value>(&line) {
                // 发送通知到前端
                let _ = app_handle_clone.emit_all("jsonrpc-notification", notification);
            }
        }
    });

    Ok(PythonService {
        child: Arc::new(Mutex::new(Some(child))),
        request_tx,
    })
}

// 获取 Python 路径
fn get_python_path(app_handle: &tauri::AppHandle) -> Result<String, String> {
    // 优先使用虚拟环境
    let app_dir = app_handle.path_resolver().app_dir()
        .ok_or("Failed to get app dir")?;
    
    let venv_python = if cfg!(target_os = "windows") {
        app_dir.join("..").join("..").join(".venv312").join("Scripts").join("python.exe")
    } else {
        app_dir.join("..").join("..").join(".venv312").join("bin").join("python")
    };

    if venv_python.exists() {
        return Ok(venv_python.to_string_lossy().to_string());
    }

    //  fallback 到系统 Python
    Ok("python".to_string())
}

// 获取服务端脚本路径
fn get_server_script_path(app_handle: &tauri::AppHandle) -> Result<String, String> {
    let app_dir = app_handle.path_resolver().app_dir()
        .ok_or("Failed to get app dir")?;
    
    let server_script = app_dir.join("..").join("..").join("apps").join("server").join("src").join("server.py");
    
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
    let request = JsonRpcRequest {
        jsonrpc: "2.0".to_string(),
        method,
        params,
        id,
    };

    let request_json = serde_json::to_string(&request)
        .map_err(|e| format!("Failed to serialize request: {}", e))?;

    service.request_tx
        .send(request_json)
        .map_err(|e| format!("Failed to send request: {}", e))?;

    Ok(())
}

// Tauri 命令：选择文件夹
#[tauri::command]
async fn select_folder(window: Window) -> Result<Option<String>, String> {
    let folder = tauri::api::dialog::FileDialogBuilder::new()
        .set_parent(&window)
        .pick_folder();

    Ok(folder.map(|p| p.to_string_lossy().to_string()))
}

// Tauri 命令：选择文件
#[tauri::command]
async fn select_files(
    window: Window,
    multiple: bool,
) -> Result<Option<Vec<String>>, String> {
    let dialog = tauri::api::dialog::FileDialogBuilder::new()
        .set_parent(&window);

    if multiple {
        Ok(dialog.pick_files().map(|files| {
            files.into_iter().map(|p| p.to_string_lossy().to_string()).collect()
        }))
    } else {
        Ok(dialog.pick_file().map(|file| vec![file.to_string_lossy().to_string()]))
    }
}

fn main() {
    tauri::Builder::default()
        .setup(|app| {
            let app_handle = app.handle();
            
            // 初始化 Python 服务
            tauri::async_runtime::block_on(async {
                match init_python_service(app_handle).await {
                    Ok(service) => {
                        app.manage(service);
                        println!("Python service initialized successfully");
                    }
                    Err(e) => {
                        eprintln!("Failed to initialize Python service: {}", e);
                    }
                }
            });

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            send_jsonrpc_request,
            select_folder,
            select_files,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
