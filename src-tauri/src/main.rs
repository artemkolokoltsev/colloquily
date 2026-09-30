#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
use std::{sync::Mutex, time::Duration};
use tauri::{Manager, State};
use tauri_plugin_shell::{process::{CommandChild, CommandEvent}, ShellExt};

#[derive(Clone, serde::Serialize)]
struct Connection { url: String, token: String }
struct Backend {
    child: Mutex<Option<CommandChild>>,
    connection: Mutex<Result<Connection, String>>,
}

#[tauri::command]
async fn backend_connection(state: State<'_, Backend>) -> Result<Connection, String> {
    for _ in 0..180 {
        let result = state.connection.lock().unwrap().clone();
        match result {
            Err(ref message) if message == "starting" => tokio::time::sleep(Duration::from_millis(500)).await,
            other => return other,
        }
    }
    Err("Local backend startup timed out. Restart Colloquily and inspect backend.log in its data directory.".into())
}

#[tauri::command]
fn open_ollama_download(app: tauri::AppHandle) -> Result<(), String> {
    #[allow(deprecated)]
    app.shell().open("https://ollama.com/download", None).map_err(|e| e.to_string())
}

fn main() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _, _| {
            if let Some(window) = app.get_webview_window("main") { let _ = window.set_focus(); }
        }))
        .plugin(tauri_plugin_shell::init())
        .manage(Backend { child: Mutex::new(None), connection: Mutex::new(Err("starting".into())) })
        .invoke_handler(tauri::generate_handler![backend_connection, open_ollama_download])
        .setup(|app| {
            let handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                let result = launch(&handle).await;
                *handle.state::<Backend>().connection.lock().unwrap() = result;
            });
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("Unable to initialize Colloquily desktop");
    app.run(|handle, event| {
        if let tauri::RunEvent::Exit = event {
            if let Some(mut child) = handle.state::<Backend>().child.lock().unwrap().take() {
                let _ = child.write(b"shutdown\n");
                std::thread::sleep(Duration::from_secs(2));
                let _ = child.kill();
            }
        }
    });
}

async fn launch(app: &tauri::AppHandle) -> Result<Connection, String> {
    // Reserve an available loopback port; failure to bind never attaches to another API.
    let listener = std::net::TcpListener::bind("127.0.0.1:0").map_err(|e| e.to_string())?;
    let port = listener.local_addr().map_err(|e| e.to_string())?.port();
    let data = if let Some(path) = std::env::var_os("COLLOQUILY_DATA_DIR") {
        std::path::PathBuf::from(path)
    } else {
        app.path().data_dir().map_err(|e| e.to_string())?.join("Colloquily")
    };
    std::fs::create_dir_all(&data).map_err(|e| e.to_string())?;
    let connection = Connection { url: format!("http://127.0.0.1:{port}"), token: uuid::Uuid::new_v4().to_string() };
    let command = app.shell().sidecar("colloquily-backend").map_err(|e| format!("Backend executable missing: {e}. Build it with npm run build:sidecar."))?
        .args(["--port", &port.to_string(), "--data-dir", &data.to_string_lossy(), "--parent-stdin"])
        .env("COLLOQUILY_API_TOKEN", &connection.token);
    drop(listener);
    let (mut events, child) = command.spawn().map_err(|e| format!("Cannot start local backend: {e}"))?;
    *app.state::<Backend>().child.lock().unwrap() = Some(child);
    let handle = app.clone();
    let log_path = data.join("backend.log");
    tauri::async_runtime::spawn(async move {
        use std::io::Write;
        // Rotate each launch; no document content is logged by this adapter.
        let mut log = std::fs::File::create(log_path).ok();
        while let Some(event) = events.recv().await {
            match event {
                CommandEvent::Stderr(bytes) | CommandEvent::Stdout(bytes) => {
                    if let Some(file) = log.as_mut() { let _ = file.write_all(&bytes); let _ = file.write_all(b"\n"); }
                },
                CommandEvent::Terminated(payload) => {
                    *handle.state::<Backend>().connection.lock().unwrap() = Err(format!("Backend exited ({:?}). See backend.log in the Colloquily data folder, then restart the app.", payload.code));
                    break;
                },
                _ => {}
            }
        }
    });
    let client = reqwest::Client::builder().timeout(Duration::from_secs(2)).build().map_err(|e| e.to_string())?;
    for _ in 0..180 {
        if let Ok(response) = client.get(format!("{}/api/health", connection.url)).send().await {
            if response.status().is_success() {
                // Confirm identity using the launch token before exposing the connection.
                if let Ok(check) = client.get(format!("{}/api/exams", connection.url)).header("X-Colloquily-Token", &connection.token).send().await {
                    if check.status().is_success() { return Ok(connection); }
                }
            }
        }
        if let Err(message) = &*app.state::<Backend>().connection.lock().unwrap() {
            if message != "starting" { return Err(message.clone()); }
        }
        tokio::time::sleep(Duration::from_millis(500)).await;
    }
    if let Some(child) = app.state::<Backend>().child.lock().unwrap().take() { let _ = child.kill(); }
    Err("Backend did not become ready. See backend.log in the Colloquily data directory.".into())
}
