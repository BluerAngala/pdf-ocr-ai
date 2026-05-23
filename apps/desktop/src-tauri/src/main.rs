// Prevents additional console window on Windows in release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::collections::HashSet;
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
    /// 进程已拉起且 stdin 通道可用
    initialized: Arc<Mutex<bool>>,
    /// Python 已打印「JSON-RPC 服务已启动」，可安全收发 RPC
    rpc_ready: Arc<Mutex<bool>>,
    error_message: Arc<Mutex<Option<String>>>,
    /// 请求发送失败计数（用于检测 channel 问题）
    send_fail_count: Arc<Mutex<u32>>,
    /// 最后一次成功通信时间
    last_success_time: Arc<Mutex<std::time::Instant>>,
}

impl PythonService {
    fn placeholder() -> Self {
        Self {
            child: Arc::new(Mutex::new(None)),
            pid: Arc::new(Mutex::new(None)),
            request_tx: Arc::new(Mutex::new(None)),
            initialized: Arc::new(Mutex::new(false)),
            rpc_ready: Arc::new(Mutex::new(false)),
            error_message: Arc::new(Mutex::new(None)),
            send_fail_count: Arc::new(Mutex::new(0)),
            last_success_time: Arc::new(Mutex::new(std::time::Instant::now())),
        }
    }

    /// 检查服务是否健康（进程存活 + channel 可用）
    fn is_healthy(&self) -> bool {
        // 检查 rpc_ready 标志（最关键的标志）
        if !*self.rpc_ready.lock().unwrap_or_else(|e| e.into_inner()) {
            return false;
        }

        // 检查进程是否还在运行（如果 child 已设置）
        if let Some(child) = self.child.lock().unwrap_or_else(|e| e.into_inner()).as_mut() {
            match child.try_wait() {
                Ok(None) => {} // 进程还在运行
                Ok(Some(_)) => return false, // 进程已退出
                Err(_) => return false,
            }
        }
        // 注意：child 可能还没设置，但只要 rpc_ready 为 true，就认为服务健康

        // 检查 channel 是否可用
        if self.request_tx.lock().unwrap_or_else(|e| e.into_inner()).is_none() {
            return false;
        }

        // 检查失败次数
        if *self.send_fail_count.lock().unwrap_or_else(|e| e.into_inner()) > 5 {
            return false;
        }

        true
    }

    /// 记录发送成功
    fn record_send_success(&self) {
        *self.send_fail_count.lock().unwrap_or_else(|e| e.into_inner()) = 0;
        *self.last_success_time.lock().unwrap_or_else(|e| e.into_inner()) = std::time::Instant::now();
    }

    /// 记录发送失败
    fn record_send_failure(&self) {
        *self.send_fail_count.lock().unwrap_or_else(|e| e.into_inner()) += 1;
    }
}

/// Windows 长路径前缀 `\\?\` 仅用于系统 API，UI 展示应去掉。
fn path_for_display(path: &Path) -> String {
    let s = path.to_string_lossy();
    let s = s.as_ref();
    #[cfg(windows)]
    {
        if let Some(rest) = s.strip_prefix(r"\\?\UNC\") {
            return format!(r"\\{}", rest);
        }
        if let Some(rest) = s.strip_prefix(r"\\?\") {
            return rest.to_string();
        }
    }
    s.to_string()
}

fn stderr_line_rpc_ready(line: &str) -> bool {
    if line.contains("JSON-RPC 服务已启动") || line.contains("Python JSON-RPC") {
        return true;
    }
    if let Ok(v) = serde_json::from_str::<serde_json::Value>(line) {
        if v.get("method").and_then(|m| m.as_str()) == Some("notify.log") {
            if let Some(msg) = v
                .get("params")
                .and_then(|p| p.get("message"))
                .and_then(|m| m.as_str())
            {
                return msg.contains("JSON-RPC") && msg.contains("已启动");
            }
        }
    }
    false
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
    service: PythonService,
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
    if !server_script.is_empty() {
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

    // 读取 stderr 线程（进度推送 + 检测 RPC 就绪）
    let app_handle_clone = app_handle.clone();
    let rpc_ready_flag = service.rpc_ready.clone();
    tokio::spawn(async move {
        let reader = BufReader::new(stderr);
        let mut lines = reader.lines();
        eprintln!("[Python stderr] stderr reader started");

        while let Ok(Some(line)) = lines.next_line().await {
            eprintln!("[Python stderr] {}", line);
            if stderr_line_rpc_ready(&line) {
                eprintln!("[Python stderr] RPC ready line detected: {}", line);
                let mut ready = rpc_ready_flag.lock().unwrap();
                if !*ready {
                    *ready = true;
                    eprintln!("[init_python_service] Python RPC ready (stderr)");
                    let _ = app_handle_clone.emit_all("python-service-ready", ());
                }
            }
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

async fn wait_for_python_rpc_ready(
    service: &PythonService,
    child: &mut Child,
    timeout_secs: u64,
) -> Result<(), String> {
    let deadline =
        std::time::Instant::now() + std::time::Duration::from_secs(timeout_secs);
    loop {
        if *service.rpc_ready.lock().map_err(|e| format!("Lock error: {}", e))? {
            return Ok(());
        }
        if std::time::Instant::now() >= deadline {
            return Err(format!(
                "Python RPC 启动超时（{}s）。打包版首次加载模型较慢，请稍后重试或检查杀毒软件是否拦截。",
                timeout_secs
            ));
        }
        match child.try_wait() {
            Ok(Some(status)) => {
                return Err(format!("Python 进程已退出: {:?}", status));
            }
            Ok(None) => {}
            Err(e) => return Err(format!("Failed to check Python process: {}", e)),
        }
        tokio::time::sleep(tokio::time::Duration::from_millis(200)).await;
    }
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

#[allow(dead_code)]
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
#[cfg(debug_assertions)]
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

/// 安装后资源根目录（含 config.yaml、poppler 等；后端为 resources/gjj-ocr-server.exe onefile）
#[allow(dead_code)]
fn resolve_resources_content_root(base: &Path) -> Option<PathBuf> {
    for root in [base.to_path_buf(), base.join("resources")] {
        if root.join("config.yaml").is_file() {
            eprintln!("[resources] content root {:?}", root);
            return Some(root);
        }
    }
    None
}

/// 安装后 resources 可能落在 Tauri resource_dir 或 exe 旁 resources/，需逐一尝试。
#[allow(dead_code)]
fn resource_dir_candidates(app: &AppHandle, app_root: &Path) -> Vec<PathBuf> {
    let mut seen = HashSet::new();
    let mut out = Vec::new();
    let mut push = |p: PathBuf| {
        if seen.insert(p.clone()) {
            out.push(p);
        }
    };
    if let Some(d) = app.path_resolver().resource_dir() {
        push(d);
    }
    push(app_root.join("resources"));
    if let Ok(exe) = std::env::current_exe() {
        if let Some(dir) = exe.parent() {
            push(dir.join("resources"));
        }
    }
    out
}

#[allow(dead_code)]
fn find_install_resources_dir(app: &AppHandle, app_root: &Path) -> Option<PathBuf> {
    for dir in resource_dir_candidates(app, app_root) {
        if let Some(root) = resolve_resources_content_root(&dir) {
            return Some(root);
        }
    }
    eprintln!(
        "[resources] config.yaml NOT found; checked {:?}",
        resource_dir_candidates(app, app_root)
    );
    None
}

#[allow(dead_code)]
fn find_bundled_server_exe(app: &AppHandle, app_root: &Path, resources_dir: &Path) -> Option<PathBuf> {
    let mut candidates = vec![
        resources_dir.join("gjj-ocr-server.exe"),
        app_root.join("resources").join("gjj-ocr-server.exe"),
        app_root.join("gjj-ocr-server.exe"),
        resources_dir.join("gjj-ocr-server").join("gjj-ocr-server.exe"),
    ];
    if let Some(rd) = app.path_resolver().resource_dir() {
        candidates.push(rd.join("gjj-ocr-server.exe"));
        candidates.push(rd.join("resources").join("gjj-ocr-server.exe"));
        candidates.push(rd.join("gjj-ocr-server").join("gjj-ocr-server.exe"));
    }
    for exe in candidates {
        if exe.is_file() {
            eprintln!("[resources] bundled server {:?}", exe);
            return Some(exe);
        }
    }
    None
}

fn is_bundled_app(_app: &AppHandle) -> bool {
    #[cfg(debug_assertions)]
    {
        return false;
    }
    #[cfg(not(debug_assertions))]
    {
        get_app_dir()
            .ok()
            .and_then(|root| find_install_resources_dir(_app, &root))
            .is_some()
    }
}

#[cfg(debug_assertions)]
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
    #[cfg(debug_assertions)]
    {
        let app_root = get_dev_project_root()?;
        let resources_dir = resolve_dev_resources_dir(&app_root)?;
        let user_data_dir = resolve_user_data_dir(app)?;
        return Ok(RuntimePathsDto {
            app_root: path_for_display(&app_root),
            resources_dir: path_for_display(&resources_dir),
            user_data_dir: path_for_display(&user_data_dir),
            bundled: false,
        });
    }

    #[cfg(not(debug_assertions))]
    {
        let app_root = get_app_dir()?;
        let resources_dir = find_install_resources_dir(app, &app_root).ok_or_else(|| {
            format!(
                "安装包缺少配置文件 config.yaml。已检查: {:?}。请卸载后重新安装。",
                resource_dir_candidates(app, &app_root)
            )
        })?;
        if find_bundled_server_exe(app, &app_root, &resources_dir).is_none() {
            return Err(format!(
                "安装包缺少后端 gjj-ocr-server.exe（{:?}）。请卸载后重新安装。",
                resources_dir
            ));
        }
        let user_data_dir = resolve_user_data_dir(app)?;
        return Ok(RuntimePathsDto {
            app_root: path_for_display(&app_root),
            resources_dir: path_for_display(&resources_dir),
            user_data_dir: path_for_display(&user_data_dir),
            bundled: true,
        });
    }
}

fn get_python_path(_app_handle: &AppHandle) -> Result<String, String> {
    #[cfg(not(debug_assertions))]
    {
        let paths = compute_runtime_paths(_app_handle)?;
        let app_root = Path::new(&paths.app_root);
        let resources_dir = Path::new(&paths.resources_dir);
        let exe = find_bundled_server_exe(_app_handle, app_root, resources_dir).ok_or_else(|| {
            format!(
                "未找到 gjj-ocr-server.exe（resources={:?}）",
                paths.resources_dir
            )
        })?;
        eprintln!("Using bundled server: {:?}", exe);
        return Ok(path_for_display(&exe));
    }

    #[cfg(debug_assertions)]
    {
        let project_root = get_dev_project_root()?;
        let venv_python = project_root.join(".venv312").join("Scripts").join("python.exe");
        if venv_python.exists() {
            println!("Using venv Python: {:?}", venv_python);
            return Ok(venv_python.to_string_lossy().to_string());
        }
        Ok("python".to_string())
    }
}

fn get_server_script_path(_app_handle: &AppHandle) -> Result<String, String> {
    #[cfg(not(debug_assertions))]
    {
        let _ = _app_handle;
        // onefile 后端已内嵌 server.py，无需再传脚本路径
        return Ok(String::new());
    }

    #[cfg(debug_assertions)]
    {
        let project_root = get_dev_project_root()?;
        let server_script = project_root
            .join("apps")
            .join("server")
            .join("src")
            .join("server.py");
        if !server_script.exists() {
            return Err(format!("Server script not found: {:?}", server_script));
        }
        Ok(server_script.to_string_lossy().to_string())
    }
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
fn is_production_bundle(app: AppHandle) -> bool {
    is_bundled_app(&app)
}

#[tauri::command]
fn is_python_service_ready(service: State<'_, PythonService>) -> bool {
    service.is_healthy()
}

// Tauri 命令：发送 JSON-RPC 请求（带重试机制）
#[tauri::command]
async fn send_jsonrpc_request(
    service: State<'_, PythonService>,
    method: String,
    params: serde_json::Value,
    id: u64,
) -> Result<(), String> {
    // 首先检查服务健康状态
    if !service.is_healthy() {
        let err = service
            .error_message
            .lock()
            .ok()
            .and_then(|g| g.clone())
            .unwrap_or_else(|| "后端服务异常，请重启应用或等待服务恢复".to_string());
        return Err(format!("Python service unhealthy: {}", err));
    }

    let request = JsonRpcRequest {
        jsonrpc: "2.0".to_string(),
        method: method.clone(),
        params: params.clone(),
        id,
    };

    let request_json = serde_json::to_string(&request)
        .map_err(|e| format!("Failed to serialize request: {}", e))?;

    eprintln!("[send_jsonrpc_request] Sending request: method={}, id={}", method, id);

    // 尝试发送，带重试逻辑
    let max_retries = 3;
    let mut last_error = String::new();
    
    for attempt in 0..max_retries {
        let tx = service
            .request_tx
            .lock()
            .map_err(|e| format!("Lock error: {}", e))?
            .clone();
        
        match tx {
            Some(channel) => {
                match channel.send(request_json.clone()) {
                    Ok(()) => {
                        eprintln!("[send_jsonrpc_request] Request queued successfully (attempt {})", attempt + 1);
                        service.record_send_success();
                        return Ok(());
                    }
                    Err(e) => {
                        last_error = format!("Failed to send request: {}", e);
                        eprintln!("[send_jsonrpc_request] Attempt {} failed: {}", attempt + 1, last_error);
                        service.record_send_failure();
                        
                        // 如果是 channel closed，可能需要重启服务
                        if e.to_string().contains("channel closed") {
                            eprintln!("[send_jsonrpc_request] Channel closed detected, service may need restart");
                            // 标记服务为不健康
                            *service.rpc_ready.lock().unwrap_or_else(|e| e.into_inner()) = false;
                        }
                    }
                }
            }
            None => {
                last_error = "Python service request channel not available".to_string();
                eprintln!("[send_jsonrpc_request] Attempt {} failed: {}", attempt + 1, last_error);
            }
        }
        
        // 等待后重试
        if attempt < max_retries - 1 {
            tokio::time::sleep(tokio::time::Duration::from_millis(100)).await;
        }
    }
    
    Err(format!("Failed to send request after {} attempts: {}", max_retries, last_error))
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
    *service.rpc_ready.lock().map_err(|e| format!("Lock error: {}", e))? = false;
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
    Ok(folder.map(|p: std::path::PathBuf| path_for_display(&p)))
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
            f.into_iter().map(|p| path_for_display(&p)).collect()
        }))
    } else {
        let (tx, rx) = std::sync::mpsc::channel::<Option<std::path::PathBuf>>();
        
        tauri::api::dialog::FileDialogBuilder::new()
            .set_parent(&window)
            .pick_file(move |file| {
                let _ = tx.send(file);
            });

        let file = rx.recv().map_err(|e| format!("Failed to receive: {}", e))?;
        Ok(file.map(|f| vec![path_for_display(&f)]))
    }
}

/// 清理旧版本缓存 - 安装新版本时调用，清空整个 output/、temp/ 及零散缓存文件
fn clear_old_caches(app: &tauri::AppHandle) -> Result<(), String> {
    use std::fs;

    let user_data_dir = resolve_user_data_dir(app)?;

    let cache_dirs = [
        user_data_dir.join("output"),
        user_data_dir.join("temp"),
    ];
    let cache_files = [
        user_data_dir.join("ocr-gpu-cache.json"),
    ];

    for dir in &cache_dirs {
        if dir.is_dir() {
            match fs::remove_dir_all(dir) {
                Ok(_) => eprintln!("[cache-cleanup] 已清理目录: {:?}", dir),
                Err(e) => eprintln!("[cache-cleanup] 清理目录失败 {:?}: {}", dir, e),
            }
        }
    }

    for file in &cache_files {
        if file.is_file() {
            match fs::remove_file(file) {
                Ok(_) => eprintln!("[cache-cleanup] 已清理文件: {:?}", file),
                Err(e) => eprintln!("[cache-cleanup] 清理文件失败 {:?}: {}", file, e),
            }
        }
    }

    if let Err(e) = fs::create_dir_all(user_data_dir.join("output")) {
        eprintln!("[cache-cleanup] 重建 output 目录失败: {}", e);
    }

    Ok(())
}

/// 检查并执行版本升级清理
fn check_and_clear_cache_on_upgrade(app: &tauri::AppHandle) {
    use std::fs;
    
    let user_data_dir = resolve_user_data_dir(app).unwrap_or_else(|_| {
        PathBuf::from(std::env::var("LOCALAPPDATA").unwrap_or_default()).join("gjj-ocr-tool")
    });
    
    let version_file = user_data_dir.join(".app-version");
    let current_version = env!("CARGO_PKG_VERSION");
    
    // 读取上次运行的版本
    let last_version = fs::read_to_string(&version_file).unwrap_or_default().trim().to_string();
    
    // 如果版本变化或首次运行，清理缓存
    if last_version != current_version {
        eprintln!("[version-check] 版本变化: {} -> {}，执行缓存清理", 
            if last_version.is_empty() { "首次运行" } else { &last_version }, 
            current_version
        );
        
        if let Err(e) = clear_old_caches(app) {
            eprintln!("[cache-cleanup] 清理缓存失败: {}", e);
        }
        
        // 写入新版本号
        if let Err(e) = fs::write(&version_file, current_version) {
            eprintln!("[version-check] 写入版本文件失败: {}", e);
        }
    } else {
        eprintln!("[version-check] 版本未变化: {}，跳过缓存清理", current_version);
    }
}

// 启动 Python 服务（带重试逻辑）
async fn start_python_service_with_retry(
    app_handle: tauri::AppHandle,
    service: PythonService,
    max_retries: u32,
) -> Result<(), String> {
    let mut last_error = String::new();
    
    for attempt in 0..max_retries {
        if attempt > 0 {
            eprintln!("[start_python_service] Retry attempt {}/{}", attempt, max_retries);
            tokio::time::sleep(tokio::time::Duration::from_secs(2)).await;
        }
        
        let _ = app_handle.emit_all(
            "backend-init-progress",
            serde_json::json!({ "step": "python", "attempt": attempt + 1 }),
        );
        
        match init_python_service(app_handle.clone(), service.clone()).await {
            Ok((mut child, pid, request_tx)) => {
                *service.pid.lock().unwrap() = Some(pid);
                *service.request_tx.lock().unwrap() = Some(request_tx);
                *service.initialized.lock().unwrap() = true;
                *service.error_message.lock().unwrap() = None;
                
                // 开发模式缩短超时时间，快速失败
                let timeout_secs = if is_bundled_app(&app_handle) { 300 } else { 30 };
                eprintln!("[start_python_service] Waiting for RPC ready (timeout: {}s)...", timeout_secs);
                
                match wait_for_python_rpc_ready(&service, &mut child, timeout_secs).await {
                    Ok(()) => {
                        *service.child.lock().unwrap() = Some(child);
                        let rpc_ready = *service.rpc_ready.lock().unwrap();
                        eprintln!("[start_python_service] RPC ready status: {}", rpc_ready);
                        if !rpc_ready {
                            eprintln!("[start_python_service] Warning: rpc_ready is false but wait returned Ok");
                            *service.rpc_ready.lock().unwrap() = true;
                            let _ = app_handle.emit_all("python-service-ready", ());
                        }
                        eprintln!("[start_python_service] Python service started successfully");
                        return Ok(());
                    }
                    Err(e) => {
                        eprintln!("[start_python_service] Failed to wait for RPC ready: {}", e);
                        last_error = e;
                        // 清理失败的进程
                        let _ = child.kill().await;
                        *service.initialized.lock().unwrap() = false;
                        *service.rpc_ready.lock().unwrap() = false;
                        *service.request_tx.lock().unwrap() = None;
                    }
                }
            }
            Err(e) => {
                last_error = e;
            }
        }
    }
    
    Err(format!("Failed to start Python service after {} attempts: {}", max_retries, last_error))
}

fn main() {
    tauri::Builder::default()
        .setup(|app| {
            // 检查版本变化并清理缓存
            check_and_clear_cache_on_upgrade(&app.handle());
            
            let app_handle = app.handle().clone();
            let service = PythonService::placeholder();
            app.manage(service.clone());

            // 启动 Python 服务
            tauri::async_runtime::spawn(async move {
                match start_python_service_with_retry(app_handle.clone(), service.clone(), 3).await {
                    Ok(()) => {
                        eprintln!("[main] Python service started successfully");
                        // TODO: 健康监控需要重构以支持 Send bound
                        // tauri::async_runtime::spawn(service_health_monitor(
                        //     app_handle.clone(),
                        //     service.clone(),
                        // ));
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
            is_python_service_ready,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
