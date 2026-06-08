//! HTTP 服务模式 - 替代 stdin/stdout JSON-RPC
//! 
//! 架构变更：
//! - Python 作为独立 HTTP 服务运行
//! - Rust 通过 HTTP 客户端与 Python 通信
//! - 支持服务健康检查、自动重启

use std::path::{Path, PathBuf};
use std::process::Stdio;
use std::sync::{Arc, Mutex};
use std::time::Duration;
use tokio::process::{Child, Command};
use tokio::time::{sleep, timeout};
use serde_json::Value;
use once_cell::sync::Lazy;

/// HTTP 服务配置
const PYTHON_HTTP_PORT: u16 = 17852;
const HEALTH_CHECK_INTERVAL_MS: u64 = 2000;
const SERVICE_START_TIMEOUT_SECS: u64 = 300;
const HEALTH_CHECK_TIMEOUT_SECS: u64 = 5;

/// 全局 HTTP 客户端
static HTTP_CLIENT: Lazy<reqwest::Client> = Lazy::new(|| {
    reqwest::Client::builder()
        .timeout(Duration::from_secs(60))
        .pool_idle_timeout(Duration::from_secs(30))
        .build()
        .expect("Failed to build HTTP client")
});

/// Python HTTP 服务状态
#[derive(Clone)]
pub struct PythonHttpService {
    child: Arc<Mutex<Option<Child>>>,
    port: Arc<Mutex<u16>>,
    /// 服务是否已启动
    initialized: Arc<Mutex<bool>>,
    /// 服务是否健康
    healthy: Arc<Mutex<bool>>,
    /// 错误信息
    error_message: Arc<Mutex<Option<String>>>,
}

impl PythonHttpService {
    pub fn new() -> Self {
        Self {
            child: Arc::new(Mutex::new(None)),
            port: Arc::new(Mutex::new(PYTHON_HTTP_PORT)),
            initialized: Arc::new(Mutex::new(false)),
            healthy: Arc::new(Mutex::new(false)),
            error_message: Arc::new(Mutex::new(None)),
        }
    }

    /// 获取服务基础 URL
    fn base_url(&self) -> String {
        let port = *self.port.lock().unwrap_or_else(|e| e.into_inner());
        format!("http://127.0.0.1:{}", port)
    }

    /// 检查服务是否就绪
    pub async fn is_ready(&self) -> bool {
        // 首先检查 initialized 标志
        if !*self.initialized.lock().unwrap_or_else(|e| e.into_inner()) {
            return false;
        }

        // 然后发送健康检查请求
        match self.health_check().await {
            Ok(healthy) => {
                *self.healthy.lock().unwrap_or_else(|e| e.into_inner()) = healthy;
                healthy
            }
            Err(_) => {
                *self.healthy.lock().unwrap_or_else(|e| e.into_inner()) = false;
                false
            }
        }
    }

    /// 健康检查
    async fn health_check(&self) -> Result<bool, String> {
        let url = format!("{}/health", self.base_url());
        
        match timeout(
            Duration::from_secs(HEALTH_CHECK_TIMEOUT_SECS),
            HTTP_CLIENT.get(&url).send()
        ).await {
            Ok(Ok(response)) => {
                if response.status().is_success() {
                    Ok(true)
                } else {
                    Err(format!("Health check failed with status: {}", response.status()))
                }
            }
            Ok(Err(e)) => Err(format!("Health check request failed: {}", e)),
            Err(_) => Err("Health check timeout".to_string()),
        }
    }

    /// 检查 OCR 引擎是否就绪
    pub async fn is_ocr_ready(&self) -> Result<bool, String> {
        let url = format!("{}/ready", self.base_url());
        
        match timeout(
            Duration::from_secs(HEALTH_CHECK_TIMEOUT_SECS),
            HTTP_CLIENT.get(&url).send()
        ).await {
            Ok(Ok(response)) => {
                if response.status().is_success() {
                    match response.json::<Value>().await {
                        Ok(json) => Ok(json.get("ready").and_then(|v| v.as_bool()).unwrap_or(false)),
                        Err(e) => Err(format!("Failed to parse ready response: {}", e)),
                    }
                } else {
                    Err(format!("Ready check failed with status: {}", response.status()))
                }
            }
            Ok(Err(e)) => Err(format!("Ready check request failed: {}", e)),
            Err(_) => Err("Ready check timeout".to_string()),
        }
    }

    /// 启动 Python HTTP 服务
    pub async fn start(
        &self,
        app_handle: &tauri::AppHandle,
    ) -> Result<(), String> {
        // 如果服务已经在运行，先停止
        self.stop().await;

        let python_path = self.get_python_path(app_handle)?;
        let http_server_script = self.get_http_server_script_path(app_handle)?;
        
        eprintln!("[PythonHttpService] Starting Python HTTP service...");
        eprintln!("[PythonHttpService] Python: {:?}", python_path);
        eprintln!("[PythonHttpService] Script: {:?}", http_server_script);

        // 查找可用端口
        let port = self.find_free_port(PYTHON_HTTP_PORT).await?;
        *self.port.lock().unwrap_or_else(|e| e.into_inner()) = port;

        let paths = compute_runtime_paths(app_handle)?;
        
        let mut cmd = Command::new(&python_path);
        cmd.arg(&http_server_script)
            .env("GJJ_HTTP_PORT", port.to_string())
            .env("GJJ_OCR_ROOT", paths.app_root.as_str())
            .env("GJJ_OCR_RESOURCES", paths.resources_dir.as_str())
            .env("GJJ_OCR_USER_DATA", paths.user_data_dir.as_str())
            .env("PYTHONUTF8", "1")
            .env("PYTHONIOENCODING", "utf-8")
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());

        #[cfg(target_os = "windows")]
        {
            use std::os::windows::process::CommandExt;
            cmd.creation_flags(0x0800_0000); // CREATE_NO_WINDOW
        }

        let mut child = cmd.spawn()
            .map_err(|e| format!("Failed to start Python HTTP service: {}", e))?;

        let pid = child.id().ok_or("Failed to get Python PID")?;
        eprintln!("[PythonHttpService] Python process started with PID: {}", pid);

        // 启动 stderr 日志转发线程
        if let Some(stderr) = child.stderr.take() {
            let app_handle_clone = app_handle.clone();
            tokio::spawn(async move {
                use tokio::io::{AsyncBufReadExt, BufReader};
                let reader = BufReader::new(stderr);
                let mut lines = reader.lines();

                while let Ok(Some(line)) = lines.next_line().await {
                    eprintln!("[Python] {}", line);
                    // 尝试解析为 JSON 通知
                    if let Ok(notification) = serde_json::from_str::<Value>(&line) {
                        let _ = app_handle_clone.emit("http-service-log", notification);
                    }
                }
            });
        }

        // 等待服务就绪
        *self.child.lock().unwrap_or_else(|e| e.into_inner()) = Some(child);
        
        match timeout(
            Duration::from_secs(SERVICE_START_TIMEOUT_SECS),
            self.wait_for_service_ready()
        ).await {
            Ok(Ok(())) => {
                *self.initialized.lock().unwrap_or_else(|e| e.into_inner()) = true;
                *self.error_message.lock().unwrap_or_else(|e| e.into_inner()) = None;
                eprintln!("[PythonHttpService] Service is ready on port {}", port);
                Ok(())
            }
            Ok(Err(e)) => {
                self.stop().await;
                *self.error_message.lock().unwrap_or_else(|e| e.into_inner()) = Some(e.clone());
                Err(e)
            }
            Err(_) => {
                self.stop().await;
                let err = format!(
                    "Python HTTP 服务启动超时（{}s）。打包版首次启动可能需 1-3 分钟，请稍后重试。",
                    SERVICE_START_TIMEOUT_SECS
                );
                *self.error_message.lock().unwrap_or_else(|e| e.into_inner()) = Some(err.clone());
                Err(err)
            }
        }
    }

    /// 停止 Python HTTP 服务
    pub async fn stop(&self) {
        eprintln!("[PythonHttpService] Stopping service...");
        
        *self.initialized.lock().unwrap_or_else(|e| e.into_inner()) = false;
        *self.healthy.lock().unwrap_or_else(|e| e.into_inner()) = false;

        if let Some(mut child) = self.child.lock().unwrap_or_else(|e| e.into_inner()).take() {
            // 尝试优雅终止
            let _ = child.kill().await;
            let _ = child.wait().await;
        }

        eprintln!("[PythonHttpService] Service stopped");
    }

    /// 发送 HTTP 请求
    pub async fn request(
        &self,
        method: &str,
        endpoint: &str,
        params: Option<Value>,
    ) -> Result<Value, String> {
        if !self.is_ready().await {
            return Err("Python HTTP service not ready".to_string());
        }

        let url = format!("{}{}", self.base_url(), endpoint);
        
        let response = match method.to_uppercase().as_str() {
            "GET" => HTTP_CLIENT.get(&url).send().await,
            "POST" => {
                let mut req = HTTP_CLIENT.post(&url);
                if let Some(p) = params {
                    req = req.json(&p);
                }
                req.send().await
            }
            _ => return Err(format!("Unsupported HTTP method: {}", method)),
        };

        match response {
            Ok(resp) => {
                match resp.json::<Value>().await {
                    Ok(json) => Ok(json),
                    Err(e) => Err(format!("Failed to parse response: {}", e)),
                }
            }
            Err(e) => Err(format!("HTTP request failed: {}", e)),
        }
    }

    /// 等待服务就绪
    async fn wait_for_service_ready(&self) -> Result<(), String> {
        let deadline = std::time::Instant::now() + Duration::from_secs(SERVICE_START_TIMEOUT_SECS);
        
        loop {
            if std::time::Instant::now() >= deadline {
                return Err("Service start timeout".to_string());
            }

            // 检查进程是否还在运行
            if let Some(child) = self.child.lock().unwrap_or_else(|e| e.into_inner()).as_mut() {
                match child.try_wait() {
                    Ok(Some(status)) => {
                        return Err(format!("Python process exited with status: {:?}", status));
                    }
                    Ok(None) => {}
                    Err(e) => return Err(format!("Failed to check process status: {}", e)),
                }
            }

            // 尝试健康检查
            match self.health_check().await {
                Ok(true) => return Ok(()),
                Ok(false) => {}
                Err(_) => {}
            }

            sleep(Duration::from_millis(500)).await;
        }
    }

    /// 查找可用端口
    async fn find_free_port(&self, start_port: u16) -> Result<u16, String> {
        use tokio::net::TcpListener;
        
        let mut port = start_port;
        while port < 65535 {
            match TcpListener::bind(format!("127.0.0.1:{}", port)).await {
                Ok(_) => return Ok(port),
                Err(_) => port += 1,
            }
        }
        Err("No free port available".to_string())
    }

    /// 获取 Python 可执行路径
    fn get_python_path(&self, app_handle: &tauri::AppHandle) -> Result<String, String> {
        #[cfg(not(debug_assertions))]
        {
            let paths = compute_runtime_paths(app_handle)?;
            let app_root = Path::new(&paths.app_root);
            let resources_dir = Path::new(&paths.resources_dir);
            let exe = find_bundled_server_exe(app_handle, app_root, resources_dir)
                .ok_or_else(|| format!("未找到 gjj-ocr-server.exe"))?;
            eprintln!("[PythonHttpService] Using bundled server: {:?}", exe);
            return Ok(path_for_display(&exe));
        }

        #[cfg(debug_assertions)]
        {
            let project_root = get_dev_project_root()?;
            let venv_python = project_root.join(".venv312").join("Scripts").join("python.exe");
            if venv_python.exists() {
                return Ok(venv_python.to_string_lossy().to_string());
            }
            Ok("python".to_string())
        }
    }

    /// 获取 HTTP 服务器脚本路径
    fn get_http_server_script_path(&self, app_handle: &tauri::AppHandle) -> Result<String, String> {
        #[cfg(not(debug_assertions))]
        {
            // 打包版：脚本在 resources/server_src/ 中
            let paths = compute_runtime_paths(app_handle)?;
            let script = Path::new(&paths.resources_dir)
                .join("server_src")
                .join("http_server.py");
            if script.exists() {
                return Ok(path_for_display(&script));
            }
            // 回退到内嵌模式（需要修改打包脚本）
            return Err("HTTP server script not found in resources".to_string());
        }

        #[cfg(debug_assertions)]
        {
            let project_root = get_dev_project_root()?;
            let script = project_root
                .join("apps")
                .join("server")
                .join("src")
                .join("http_server.py");
            if !script.exists() {
                return Err(format!("HTTP server script not found: {:?}", script));
            }
            Ok(script.to_string_lossy().to_string())
        }
    }

    /// 获取错误信息
    pub fn get_error_message(&self) -> Option<String> {
        self.error_message.lock().unwrap_or_else(|e| e.into_inner()).clone()
    }
}

// ============ 路径工具函数（复用原有代码） ============

use tauri::AppHandle;

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

#[derive(Clone, serde::Serialize)]
#[serde(rename_all = "camelCase")]
struct RuntimePathsDto {
    app_root: String,
    resources_dir: String,
    user_data_dir: String,
    bundled: bool,
}

fn compute_runtime_paths(app: &AppHandle) -> Result<RuntimePathsDto, String> {
    // 简化版 - 实际应复用 main.rs 中的完整逻辑
    #[cfg(debug_assertions)]
    {
        let app_root = get_dev_project_root()?;
        let resources_dir = app_root.join("resources");
        let user_data_dir = app_root.join("user-data");
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
        let resources_dir = app_root.join("resources");
        let user_data_dir = resolve_user_data_dir(app)?;
        return Ok(RuntimePathsDto {
            app_root: path_for_display(&app_root),
            resources_dir: path_for_display(&resources_dir),
            user_data_dir: path_for_display(&user_data_dir),
            bundled: true,
        });
    }
}

fn get_app_dir() -> Result<PathBuf, String> {
    std::env::current_exe()
        .map_err(|e| format!("Failed to get current exe: {}", e))?
        .parent()
        .ok_or("Cannot determine app directory")?
        .to_path_buf()
        .canonicalize()
        .map_err(|e| format!("Failed to canonicalize app dir: {}", e))
}

fn resolve_user_data_dir(app: &AppHandle) -> Result<PathBuf, String> {
    if let Ok(env) = std::env::var("GJJ_OCR_USER_DATA") {
        let p = PathBuf::from(env);
        std::fs::create_dir_all(&p).map_err(|e| format!("无法创建用户目录 {:?}: {}", p, e))?;
        return Ok(p);
    }
    if let Some(dir) = app.path_resolver().app_data_dir() {
        std::fs::create_dir_all(&dir).map_err(|e| format!("无法创建用户目录 {:?}: {}", dir, e))?;
        return Ok(dir);
    }
    Err("无法确定用户数据目录".to_string())
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

#[allow(dead_code)]
fn find_bundled_server_exe(
    app: &AppHandle,
    app_root: &Path,
    resources_dir: &Path,
) -> Option<PathBuf> {
    let mut candidates = vec![
        resources_dir.join("gjj-ocr-server.exe"),
        app_root.join("resources").join("gjj-ocr-server.exe"),
        app_root.join("gjj-ocr-server.exe"),
    ];
    if let Some(rd) = app.path_resolver().resource_dir() {
        candidates.push(rd.join("gjj-ocr-server.exe"));
        candidates.push(rd.join("resources").join("gjj-ocr-server.exe"));
    }
    for exe in candidates {
        if exe.is_file() {
            return Some(exe);
        }
    }
    None
}
