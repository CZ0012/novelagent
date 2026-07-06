#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::{Deserialize, Serialize};
use serde_json::Value;
#[cfg(windows)]
use std::os::windows::process::CommandExt;
use std::{
    env,
    fs::{self, File, OpenOptions},
    io::{Read, Write},
    net::{TcpStream, ToSocketAddrs},
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    sync::{
        atomic::{AtomicBool, Ordering},
        Mutex,
    },
    thread,
    time::Duration,
};
use tauri::{
    menu::MenuBuilder,
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    Manager, WindowEvent,
};

#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = 0x08000000;
const MAIN_WINDOW_LABEL: &str = "main";
const TRAY_MENU_SHOW: &str = "show-main-window";
const TRAY_MENU_QUIT: &str = "quit-storygraph-agent";

struct BackendProcess {
    child: Mutex<Option<Child>>,
    shutting_down: AtomicBool,
}

impl Default for BackendProcess {
    fn default() -> Self {
        Self {
            child: Mutex::new(None),
            shutting_down: AtomicBool::new(false),
        }
    }
}

impl Drop for BackendProcess {
    fn drop(&mut self) {
        if let Ok(mut guard) = self.child.lock() {
            if let Some(mut child) = guard.take() {
                kill_child_tree(&mut child);
            }
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct DesktopSettings {
    backend_url: String,
    workspace_path: String,
    auto_start_backend: bool,
    python_executable: String,
    backend_module: String,
}

impl Default for DesktopSettings {
    fn default() -> Self {
        Self {
            backend_url: "http://127.0.0.1:8000".to_string(),
            workspace_path: default_workspace_dir().to_string_lossy().to_string(),
            auto_start_backend: true,
            python_executable: "python".to_string(),
            backend_module: "apps.api.desktop_server".to_string(),
        }
    }
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct BackendStatus {
    backend_url: String,
    reachable: bool,
    workspace_compatible: bool,
    managed: bool,
    pid: Option<u32>,
    workspace_path: String,
    health_workspace_path: Option<String>,
    health: Option<Value>,
    error: Option<String>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct DesktopPaths {
    settings_path: String,
    workspace_path: String,
    log_dir: String,
    backend_log_path: String,
    project_root: Option<String>,
}

#[tauri::command]
fn load_desktop_settings() -> Result<DesktopSettings, String> {
    read_settings()
}

#[tauri::command]
fn save_desktop_settings(settings: DesktopSettings) -> Result<DesktopSettings, String> {
    if settings.backend_url.trim().is_empty() {
        return Err("后端 API 地址不能为空。".to_string());
    }
    if settings.workspace_path.trim().is_empty() {
        return Err("工作区路径不能为空。".to_string());
    }
    write_settings(&settings)?;
    Ok(settings)
}

#[tauri::command]
fn desktop_paths() -> Result<DesktopPaths, String> {
    let settings = read_settings()?;
    let log_dir = app_data_dir().join("logs");
    Ok(DesktopPaths {
        settings_path: settings_path().to_string_lossy().to_string(),
        workspace_path: settings.workspace_path,
        backend_log_path: log_dir.join("backend.log").to_string_lossy().to_string(),
        log_dir: log_dir.to_string_lossy().to_string(),
        project_root: project_root().map(|path| path.to_string_lossy().to_string()),
    })
}

#[tauri::command]
fn backend_status(state: tauri::State<'_, BackendProcess>) -> Result<BackendStatus, String> {
    let settings = read_settings()?;
    Ok(status_for(&settings, &state))
}

#[tauri::command]
fn start_backend(state: tauri::State<'_, BackendProcess>) -> Result<BackendStatus, String> {
    if state.shutting_down.load(Ordering::SeqCst) {
        return Err("StoryGraph Agent 正在退出，已取消启动后端。".to_string());
    }

    let settings = read_settings()?;
    let current = status_for(&settings, &state);
    if current.reachable {
        return Ok(current);
    }

    let mut guard = state
        .child
        .lock()
        .map_err(|_| "后端进程锁已损坏。".to_string())?;
    if state.shutting_down.load(Ordering::SeqCst) {
        return Err("StoryGraph Agent 正在退出，已取消启动后端。".to_string());
    }
    if let Some(child) = guard.as_mut() {
        if child
            .try_wait()
            .map_err(|error| error.to_string())?
            .is_none()
        {
            drop(guard);
            return wait_for_backend(&settings, &state);
        }
    }

    fs::create_dir_all(&settings.workspace_path)
        .map_err(|error| format!("无法创建工作区目录：{error}"))?;
    let log_dir = app_data_dir().join("logs");
    fs::create_dir_all(&log_dir).map_err(|error| format!("无法创建日志目录：{error}"))?;
    let stdout = log_file(&log_dir, "backend.log")?;
    let stderr = log_file(&log_dir, "backend.err.log")?;

    let mut command = backend_command(&settings);
    command
        .env("STORYGRAPH_HOME", &settings.workspace_path)
        .env("STORYGRAPH_GRAPH_BACKEND", "json")
        .stdout(Stdio::from(stdout))
        .stderr(Stdio::from(stderr));

    if let Some(root) = project_root() {
        command.current_dir(root);
    }

    #[cfg(windows)]
    command.creation_flags(CREATE_NO_WINDOW);

    let child = command
        .spawn()
        .map_err(|error| format!("无法启动 FastAPI 后端：{error}"))?;
    *guard = Some(child);

    if state.shutting_down.load(Ordering::SeqCst) {
        if let Some(child) = guard.as_mut() {
            kill_child_tree(child);
        }
        *guard = None;
        drop(guard);
        return Ok(status_for(&settings, &state));
    }

    drop(guard);

    wait_for_backend(&settings, &state)
}

fn backend_command(settings: &DesktopSettings) -> Command {
    if let Some(sidecar) = sidecar_backend_path() {
        return Command::new(sidecar);
    }

    let mut command = Command::new(&settings.python_executable);
    command.arg("-m").arg(&settings.backend_module);
    command
}

fn sidecar_backend_path() -> Option<PathBuf> {
    let mut candidates = Vec::new();

    if let Ok(exe_path) = env::current_exe() {
        if let Some(exe_dir) = exe_path.parent() {
            candidates.push(exe_dir.join("storygraph-backend.exe"));
            candidates.push(exe_dir.join("storygraph-backend-x86_64-pc-windows-msvc.exe"));
            candidates.push(exe_dir.join("binaries").join("storygraph-backend.exe"));
            candidates.push(
                exe_dir
                    .join("binaries")
                    .join("storygraph-backend-x86_64-pc-windows-msvc.exe"),
            );
        }
    }

    if let Some(root) = project_root() {
        candidates.push(
            root.join("apps")
                .join("desktop")
                .join("src-tauri")
                .join("binaries")
                .join("storygraph-backend-x86_64-pc-windows-msvc.exe"),
        );
    }

    candidates.into_iter().find(|path| path.exists())
}

#[tauri::command]
fn stop_backend(state: tauri::State<'_, BackendProcess>) -> Result<BackendStatus, String> {
    let settings = read_settings()?;
    stop_managed_backend(&state)?;
    Ok(status_for(&settings, &state))
}

fn stop_managed_backend(state: &BackendProcess) -> Result<(), String> {
    let mut guard = state
        .child
        .lock()
        .map_err(|_| "后端进程锁已损坏。".to_string())?;
    if let Some(mut child) = guard.take() {
        kill_child_tree(&mut child);
    }
    Ok(())
}

fn main() {
    tauri::Builder::default()
        .manage(BackendProcess::default())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .setup(|app| {
            setup_tray(app)?;
            let settings = read_settings().unwrap_or_else(|_| DesktopSettings::default());
            if settings.auto_start_backend {
                let app_handle = app.handle().clone();
                tauri::async_runtime::spawn_blocking(move || {
                    let state = app_handle.state::<BackendProcess>();
                    let _ = start_backend(state);
                });
            }
            Ok(())
        })
        .on_window_event(|window, event| {
            if window.label() != MAIN_WINDOW_LABEL {
                return;
            }
            if let WindowEvent::CloseRequested { api, .. } = event {
                api.prevent_close();
                let _ = window.hide();
                let _ = window.set_skip_taskbar(true);
            }
        })
        .on_menu_event(|app, event| match event.id().as_ref() {
            TRAY_MENU_SHOW => show_main_window(app),
            TRAY_MENU_QUIT => quit_desktop_app(app),
            _ => {}
        })
        .on_tray_icon_event(|app, event| match event {
            TrayIconEvent::Click {
                button: MouseButton::Left,
                button_state: MouseButtonState::Up,
                ..
            }
            | TrayIconEvent::DoubleClick {
                button: MouseButton::Left,
                ..
            } => show_main_window(app),
            _ => {}
        })
        .invoke_handler(tauri::generate_handler![
            backend_status,
            desktop_paths,
            load_desktop_settings,
            save_desktop_settings,
            start_backend,
            stop_backend
        ])
        .run(tauri::generate_context!())
        .expect("StoryGraph Agent 桌面壳运行失败");
}

fn setup_tray(app: &mut tauri::App) -> tauri::Result<()> {
    let menu = MenuBuilder::new(app)
        .text(TRAY_MENU_SHOW, "显示主界面")
        .separator()
        .text(TRAY_MENU_QUIT, "退出 StoryGraph 写作台")
        .build()?;
    let mut tray = TrayIconBuilder::with_id("storygraph-main-tray")
        .menu(&menu)
        .show_menu_on_left_click(false)
        .tooltip("StoryGraph 写作台正在运行");

    if let Some(icon) = app.default_window_icon().cloned() {
        tray = tray.icon(icon);
    }

    tray.build(app)?;
    Ok(())
}

fn show_main_window(app: &tauri::AppHandle) {
    if let Some(window) = app.get_webview_window(MAIN_WINDOW_LABEL) {
        let _ = window.set_skip_taskbar(false);
        let _ = window.show();
        let _ = window.unminimize();
        let _ = window.set_focus();
    }
}

fn quit_desktop_app(app: &tauri::AppHandle) {
    let state = app.state::<BackendProcess>();
    state.shutting_down.store(true, Ordering::SeqCst);
    let _ = stop_managed_backend(&state);
    app.exit(0);
}

fn wait_for_backend(
    settings: &DesktopSettings,
    state: &tauri::State<'_, BackendProcess>,
) -> Result<BackendStatus, String> {
    let mut last = status_for(settings, state);
    for _ in 0..20 {
        if last.reachable {
            return Ok(last);
        }
        thread::sleep(Duration::from_millis(250));
        last = status_for(settings, state);
    }
    Ok(last)
}

fn status_for(
    settings: &DesktopSettings,
    state: &tauri::State<'_, BackendProcess>,
) -> BackendStatus {
    reap_finished_child(state);
    let (health, fetch_error) = match fetch_health(&settings.backend_url) {
        Ok(value) => (Some(value), None),
        Err(error) => (None, Some(error)),
    };
    let (managed, pid) = managed_process(state);
    let health_workspace_path = health.as_ref().and_then(extract_health_workspace);
    let workspace_compatible = match (health.as_ref(), health_workspace_path.as_deref()) {
        (Some(_), Some(path)) => paths_equivalent(path, &settings.workspace_path),
        (Some(_), None) => false,
        (None, _) => false,
    };
    let error = if health.is_some() && !workspace_compatible {
        Some(workspace_mismatch_message(
            &settings.backend_url,
            health_workspace_path.as_deref(),
            &settings.workspace_path,
        ))
    } else {
        fetch_error
    };

    BackendStatus {
        backend_url: settings.backend_url.clone(),
        reachable: health.is_some(),
        workspace_compatible,
        managed,
        pid,
        workspace_path: settings.workspace_path.clone(),
        health_workspace_path,
        health,
        error,
    }
}

fn managed_process(state: &tauri::State<'_, BackendProcess>) -> (bool, Option<u32>) {
    match state.child.lock() {
        Ok(guard) => match guard.as_ref() {
            Some(child) => (true, Some(child.id())),
            None => (false, None),
        },
        Err(_) => (false, None),
    }
}

fn reap_finished_child(state: &tauri::State<'_, BackendProcess>) {
    let Ok(mut guard) = state.child.lock() else {
        return;
    };
    if let Some(child) = guard.as_mut() {
        if matches!(child.try_wait(), Ok(Some(_))) {
            *guard = None;
        }
    }
}

fn fetch_health(base_url: &str) -> Result<Value, String> {
    let endpoint = parse_local_http_url(base_url)?;
    let mut addrs = (endpoint.host.as_str(), endpoint.port)
        .to_socket_addrs()
        .map_err(|error| format!("无法解析后端主机：{error}"))?;
    let addr = addrs
        .next()
        .ok_or_else(|| "后端主机没有解析到可用地址。".to_string())?;
    let mut stream = TcpStream::connect_timeout(&addr, Duration::from_millis(500))
        .map_err(|error| format!("无法连接后端：{error}"))?;
    stream
        .set_read_timeout(Some(Duration::from_millis(1200)))
        .map_err(|error| error.to_string())?;
    stream
        .set_write_timeout(Some(Duration::from_millis(1200)))
        .map_err(|error| error.to_string())?;
    let request = format!(
        "GET {} HTTP/1.1\r\nHost: {}\r\nConnection: close\r\nAccept: application/json\r\n\r\n",
        endpoint.path, endpoint.host
    );
    stream
        .write_all(request.as_bytes())
        .map_err(|error| format!("无法请求后端健康检查：{error}"))?;

    let mut response = String::new();
    stream
        .read_to_string(&mut response)
        .map_err(|error| format!("无法读取后端健康检查响应：{error}"))?;
    let (head, body) = response
        .split_once("\r\n\r\n")
        .ok_or_else(|| "后端返回了无效的 HTTP 响应。".to_string())?;
    if !head.starts_with("HTTP/1.1 200") && !head.starts_with("HTTP/1.0 200") {
        return Err(format!(
            "后端健康检查返回非 200 状态：{}",
            head.lines().next().unwrap_or("unknown")
        ));
    }
    serde_json::from_str(body.trim()).map_err(|error| format!("后端健康检查不是 JSON：{error}"))
}

struct LocalHttpEndpoint {
    host: String,
    port: u16,
    path: String,
}

fn parse_local_http_url(base_url: &str) -> Result<LocalHttpEndpoint, String> {
    let rest = base_url
        .strip_prefix("http://")
        .ok_or_else(|| "桌面版只支持本机 http:// 后端地址。".to_string())?;
    let (host_port, base_path) = match rest.split_once('/') {
        Some((host_port, path)) => (host_port, format!("/{path}")),
        None => (rest, String::new()),
    };
    let (host, port) = match host_port.rsplit_once(':') {
        Some((host, port)) => {
            let port = port
                .parse::<u16>()
                .map_err(|_| "后端 API 地址端口必须是数字。".to_string())?;
            (host.to_string(), port)
        }
        None => (host_port.to_string(), 80),
    };
    if !matches!(host.as_str(), "127.0.0.1" | "localhost" | "::1") {
        return Err("桌面版后端 API 地址必须指向 localhost。".to_string());
    }
    let prefix = base_path.trim_end_matches('/');
    let path = if prefix.is_empty() {
        "/health".to_string()
    } else {
        format!("{prefix}/health")
    };
    Ok(LocalHttpEndpoint { host, port, path })
}

fn read_settings() -> Result<DesktopSettings, String> {
    let path = settings_path();
    if !path.exists() {
        let settings = DesktopSettings::default();
        write_settings(&settings)?;
        return Ok(settings);
    }
    let content =
        fs::read_to_string(&path).map_err(|error| format!("无法读取桌面设置：{error}"))?;
    serde_json::from_str(&content).map_err(|error| format!("无法解析桌面设置：{error}"))
}

fn write_settings(settings: &DesktopSettings) -> Result<(), String> {
    let path = settings_path();
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|error| format!("无法创建桌面设置目录：{error}"))?;
    }
    let payload = serde_json::to_string_pretty(settings)
        .map_err(|error| format!("无法序列化桌面设置：{error}"))?;
    fs::write(path, format!("{payload}\n")).map_err(|error| format!("无法写入桌面设置：{error}"))
}

fn log_file(dir: &Path, file_name: &str) -> Result<File, String> {
    OpenOptions::new()
        .create(true)
        .append(true)
        .open(dir.join(file_name))
        .map_err(|error| format!("无法打开后端日志文件：{error}"))
}

fn extract_health_workspace(health: &Value) -> Option<String> {
    health
        .get("workspace")
        .and_then(Value::as_str)
        .map(|value| value.to_string())
}

fn workspace_mismatch_message(
    backend_url: &str,
    health_workspace_path: Option<&str>,
    expected_workspace_path: &str,
) -> String {
    let actual = health_workspace_path.unwrap_or("未知工作区");
    format!(
        "检测到 {backend_url} 上已有后端在运行，但它的工作区是“{actual}”，不是当前桌面工作区“{expected_workspace_path}”。请停止占用该端口的旧后端，或在桌面设置中改用其他本机 API 地址。"
    )
}

fn paths_equivalent(left: &str, right: &str) -> bool {
    normalize_path_for_compare(left) == normalize_path_for_compare(right)
}

fn normalize_path_for_compare(path: &str) -> String {
    let mut normalized = path.trim().replace('/', "\\");
    if let Some(stripped) = normalized.strip_prefix(r"\\?\") {
        normalized = stripped.to_string();
    }
    while normalized.ends_with('\\') && normalized.len() > 3 {
        normalized.pop();
    }
    #[cfg(windows)]
    {
        normalized.to_ascii_lowercase()
    }
    #[cfg(not(windows))]
    {
        normalized
    }
}

fn kill_child_tree(child: &mut Child) {
    #[cfg(windows)]
    {
        let pid = child.id().to_string();
        let mut command = Command::new("taskkill");
        command
            .args(["/PID", pid.as_str(), "/T", "/F"])
            .stdout(Stdio::null())
            .stderr(Stdio::null());
        command.creation_flags(CREATE_NO_WINDOW);
        let _ = command.status();
    }

    let _ = child.kill();
    let _ = child.wait();
}

fn settings_path() -> PathBuf {
    app_data_dir().join("desktop-settings.json")
}

fn app_data_dir() -> PathBuf {
    if let Some(path) = env::var_os("LOCALAPPDATA") {
        return PathBuf::from(path).join("StoryGraph Agent");
    }
    if let Some(path) = env::var_os("APPDATA") {
        return PathBuf::from(path).join("StoryGraph Agent");
    }
    if let Some(path) = env::var_os("HOME") {
        return PathBuf::from(path).join(".storygraph-agent");
    }
    env::temp_dir().join("StoryGraph Agent")
}

fn default_workspace_dir() -> PathBuf {
    app_data_dir().join("workspace")
}

fn project_root() -> Option<PathBuf> {
    if let Some(path) = env::var_os("STORYGRAPH_PROJECT_ROOT") {
        let root = PathBuf::from(path);
        if root.join("pyproject.toml").exists() {
            return Some(root);
        }
    }

    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    for ancestor in manifest_dir.ancestors() {
        if ancestor.join("pyproject.toml").exists() {
            return Some(ancestor.to_path_buf());
        }
    }

    if let Ok(current_dir) = env::current_dir() {
        for ancestor in current_dir.ancestors() {
            if ancestor.join("pyproject.toml").exists() {
                return Some(ancestor.to_path_buf());
            }
        }
    }

    None
}
