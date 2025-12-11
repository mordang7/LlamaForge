from flask import Flask, render_template, request, Response, jsonify
import subprocess
import threading
import queue
import re
import os
import platform
import pystray
from PIL import Image
import webbrowser
import logging
import json

# Optional: HuggingFace model downloading
try:
    from huggingface_hub import hf_hub_download
    HF_AVAILABLE = True
except ImportError:
    logging.warning("huggingface_hub not installed. Download feature will not work.")
    hf_hub_download = None
    HF_AVAILABLE = False

app = Flask(__name__)

# Setup logging
logging.basicConfig(
    filename="app.log",
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# Global variables
server_process = None
log_queue = queue.Queue()
stop_event = threading.Event()
log_thread = None
tray_icon = None
flask_thread = None
service_running = False
LLAMA_SERVER_PATH = None

def find_llama_server():
    is_windows = platform.system() == "Windows"
    exe_suffix = ".exe" if is_windows else ""
    
    # Priority: Current Directory -> PATH -> Common Dirs
    search_paths = [os.getcwd(), "."]
    
    path_env = os.environ.get("PATH", "")
    path_sep = ";" if is_windows else ":"
    search_paths.extend(path_env.split(path_sep))
    
    common_dirs = ["/usr/local/bin", "/usr/bin", os.path.expanduser("~/bin")]
    if is_windows:
        common_dirs.extend([
            "C:\\llamacpp",
            "C:\\Program Files\\llama.cpp",
            os.path.expanduser("~\\llamacpp"),
        ])
    search_paths.extend(common_dirs)

    for p in search_paths:
        if not p: continue
        exe_path = os.path.join(p, "llama-server" + exe_suffix)
        if os.path.exists(exe_path):
            logging.info(f"Found llama-server at: {exe_path}")
            return exe_path
    
    logging.error("llama-server executable not found in search paths.")
    return None

LLAMA_SERVER_PATH = find_llama_server()

def start_service():
    global flask_thread, service_running
    if not service_running:
        flask_thread = threading.Thread(
            target=lambda: app.run(
                debug=False, host="127.0.0.1", port=5000, threaded=True
            ),
            daemon=True,
        )
        flask_thread.start()
        service_running = True
        update_tray_menu()

def stop_service():
    global flask_thread, service_running, server_process
    if service_running:
        if server_process:
            server_process.terminate()
            server_process.wait()
            server_process = None
        service_running = False
        update_tray_menu()

def restart_service():
    stop_service()
    start_service()

def open_browser():
    webbrowser.open("http://127.0.0.1:5000")

def on_exit():
    stop_service()
    if tray_icon:
        tray_icon.stop()
    os._exit(0)

def get_menu():
    return pystray.Menu(
        pystray.MenuItem("Open", open_browser, enabled=service_running),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Start Service", start_service, enabled=not service_running),
        pystray.MenuItem("Restart Service", restart_service, enabled=service_running),
        pystray.MenuItem("Stop Service", stop_service, enabled=service_running),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Exit", on_exit),
    )

def update_tray_menu():
    if tray_icon:
        tray_icon.menu = get_menu()
        tray_icon.title = (
            f"LlamaForge: {'Running' if service_running else 'Stopped'}"
        )

def parse_runtime_info(stdout, stderr):
    output = stdout + "\n" + stderr
    runtimes = []
    
    # Debug logging
    logging.debug(f"Runtime Detection Output: {output}")

    backend_map = {
        "CUDA": "CUDA (NVIDIA GPUs)",
        "HIP": "ROCm (AMD GPUs)",
        "Vulkan": "Vulkan (Cross-platform)",
        "Metal": "Metal (Apple Silicon)",
        "SYCL": "SYCL (Intel GPUs/Accelerators)",
    }
    
    active_backends = []
    
    lines = output.split('\n')
    for line in lines:
        lower_line = line.lower()
        
        # IGNORE ggml_cuda_init lines (Fix for AMD false positives)
        if "ggml_cuda_init" in lower_line:
            continue
            
        if "error" in lower_line or "failed" in lower_line or "not found" in lower_line:
            continue
            
        if "cuda" in lower_line and ("device" in lower_line or "init" in lower_line):
            active_backends.append("CUDA")
        if ("hip" in lower_line or "rocm" in lower_line or "amd" in lower_line) and ("device" in lower_line or "init" in lower_line):
            active_backends.append("ROCm")
        if "vulkan" in lower_line and ("device" in lower_line or "init" in lower_line):
            active_backends.append("Vulkan")
        if "metal" in lower_line and ("device" in lower_line or "init" in lower_line):
            active_backends.append("Metal")
        if "sycl" in lower_line and ("device" in lower_line or "init" in lower_line):
            active_backends.append("SYCL")

    # Remove duplicates
    active_backends = list(set(active_backends))

    for backend, name in backend_map.items():
        if backend in active_backends:
            runtimes.append(
                {
                    "name": name,
                    "status": "active",
                    "tooltip": f"{name} is active and ready.",
                }
            )
    
    # Always include CPU
    runtimes.append(
        {
            "name": "CPU (Fallback)",
            "status": "active",
            "tooltip": "CPU is always available as fallback.",
        }
    )
    return runtimes

@app.route("/")
def index():
    try:
        return render_template("index.html")
    except Exception as e:
        logging.error(f"Error in index: {e}")
        return "Internal Server Error", 500

@app.route("/detect-runtime")
def detect_runtime():
    # Accept custom server path from query parameter
    server_path = request.args.get('serverPath') or LLAMA_SERVER_PATH
    
    if not server_path:
        return jsonify({"error": "llama-server not found. Please install llama.cpp or specify server path."})
    
    try:
        # Check for backend DLLs in the same directory as the server
        server_dir = os.path.dirname(server_path)
        if not server_dir: server_dir = "."
        
        available_backends = {
            "cpu": True, # CPU always available
            "cuda": False,
            "rocm": False,
            "vulkan": False,
            "sycl": False
        }
        
        # Check for specific DLLs
        if os.path.exists(os.path.join(server_dir, "ggml-cuda.dll")):
            available_backends["cuda"] = True
        if os.path.exists(os.path.join(server_dir, "ggml-hip.dll")):
            available_backends["rocm"] = True
        if os.path.exists(os.path.join(server_dir, "ggml-vk.dll")):
            available_backends["vulkan"] = True
        if os.path.exists(os.path.join(server_dir, "ggml-sycl.dll")):
            available_backends["sycl"] = True

        # Configure startup info to hide window
        startupinfo = None
        creationflags = 0
        if platform.system() == "Windows":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            creationflags = subprocess.CREATE_NO_WINDOW

        # Capture both stdout and stderr
        runtimes = []
        try:
            result = subprocess.run(
                [server_path, "--list-devices"],
                capture_output=True,
                text=True,
                timeout=10,
                startupinfo=startupinfo,
                creationflags=creationflags
            )
            runtimes = parse_runtime_info(result.stdout, result.stderr)
        except Exception as e:
            logging.warning(f"Runtime check failed (safe to ignore if configuring): {e}")
            runtimes.append({
                "name": "CPU (Fallback)",
                "status": "active",
                "tooltip": "CPU is always available."
            })
        
        return jsonify({
            "runtimes": runtimes,
            "available_backends": available_backends
        })
    except Exception as e:
        logging.error(f"Error in detect_runtime: {e}")
        return jsonify({"error": str(e)})

@app.route("/browse-folder")
def browse_folder():
    try:
        # Use PowerShell to open FolderBrowserDialog
        # This avoids Tkinter threading issues in Flask
        ps_script = """
        Add-Type -AssemblyName System.Windows.Forms
        $f = New-Object System.Windows.Forms.FolderBrowserDialog
        $f.ShowNewFolderButton = $true
        $f.Description = "Select Model Directory"
        $result = $f.ShowDialog()
        if ($result -eq 'OK') {
            Write-Output $f.SelectedPath
        }
        """
        
        startupinfo = None
        creationflags = 0
        if platform.system() == "Windows":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            creationflags = subprocess.CREATE_NO_WINDOW

        result = subprocess.run(
            ["powershell", "-Sta", "-Command", ps_script],
            capture_output=True,
            text=True,
            startupinfo=startupinfo,
            creationflags=creationflags
        )
        
        path = result.stdout.strip()
        return jsonify({"path": path})
    except Exception as e:
        logging.error(f"Error in browse_folder: {e}")
        return jsonify({"error": str(e)})

@app.route("/scan-models", methods=["POST"])
def scan_models():
    try:
        data = request.json
        path = data.get("path", ".")
        models = []
        for root, dirs, files in os.walk(path):
            for file in files:
                if file.endswith(".gguf"):
                    models.append(os.path.join(root, file))
        return jsonify({"models": models})
    except Exception as e:
        logging.error(f"Error in scan_models: {e}")
        return jsonify({"error": str(e)})

@app.route('/delete-model', methods=['POST'])
def delete_model():
    try:
        data = request.json
        model_path = data.get('path')
        if not model_path:
            return jsonify({"error": "No path provided"}), 400
            
        if os.path.exists(model_path):
            os.remove(model_path)
            logging.info(f"Deleted model: {model_path}")
            return jsonify({"success": True})
        else:
            return jsonify({"error": "File not found"}), 404
    except Exception as e:
        logging.error(f"Error deleting model: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/download-model', methods=['POST'])
def download_model():
    if not HF_AVAILABLE:
        return jsonify({"error": "huggingface_hub not installed. Please install it with: pip install huggingface_hub"}), 500
    
    try:
        data = request.json
        repo_id = data.get("repoId")
        filename = data.get("filename")
        save_dir = data.get("saveDir", ".")
        
        if not repo_id or not filename:
            return jsonify({"error": "Missing repo ID or filename"}), 400
        
        logging.info(f"Downloading {filename} from {repo_id}...")
        
        # Download the model
        file_path = hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            local_dir=save_dir,
            local_dir_use_symlinks=False
        )
        
        logging.info(f"Downloaded model to: {file_path}")
        return jsonify({"success": True, "path": file_path})
    except Exception as e:
        logging.error(f"Error downloading model: {e}")
        return jsonify({"error": str(e)}), 500

import sys
import tkinter as tk
from tkinter import filedialog

@app.route('/browse-file', methods=['POST'])
def browse_file():
    try:
        # Create hidden root window
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True) # Bring to front
        
        file_path = filedialog.askopenfilename(
            title="Select File",
            filetypes=[("Executables", "*.exe"), ("All Files", "*.*")]
        )
        
        root.destroy()
        
        if file_path:
            # Normalize path for Windows
            file_path = file_path.replace('/', '\\')
            return jsonify({"path": file_path})
        else:
            return jsonify({"path": ""}) # Cancelled
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def find_llama_server():
    # Search for llama-server in common locations
    # Critical: Check directory of the actual executable (sys.executable)
    exe_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(__file__)
    
    search_paths = [
        exe_dir, # Where the .exe is
        os.getcwd(), # Current working directory
        os.path.join(exe_dir, "llama.cpp", "build", "bin"),
        os.path.join(exe_dir, "llama.cpp"),
    ]

    # Add PATH environment variable directories
    if "PATH" in os.environ:
        search_paths.extend(os.environ["PATH"].split(os.pathsep))

    executable_name = "llama-server"
    if platform.system() == "Windows":
        executable_name += ".exe"

    for path in search_paths:
        if not path: continue
        full_path = os.path.join(path, executable_name)
        if os.path.exists(full_path) and os.path.isfile(full_path):
            logging.info(f"Found llama-server at: {full_path}")
            return full_path

    logging.warning("llama-server executable not found in search paths. Defaulting to 'llama-server' (assuming in PATH).")
    return "llama-server"

LLAMA_SERVER_PATH = find_llama_server()

@app.route('/start-server', methods=['POST'])
def start_server():
    global server_process, stop_event, log_thread
    if server_process and server_process.poll() is None:
        return jsonify({"error": "Server already running."}), 400
        
    data = request.json
    
    # Check for user-provided server path (V0.4 feature)
    custom_server_path = data.get("serverPath")
    server_path = custom_server_path if custom_server_path else LLAMA_SERVER_PATH
    
    if not server_path:
        return jsonify({"error": "llama-server executable not found. Please specify the path in settings."}), 500

    # Basic Parameters
    model_path = data.get("model", "")
    if not model_path:
        return jsonify({"error": "No model specified"}), 400
        
    threads = data.get("threads", os.cpu_count())
    gpu_layers = data.get("gpu_layers", 0)
    port = data.get("port", 8080)
    host = data.get("host", "127.0.0.1")
    
    # Advanced Parameters
    ctx_size = data.get("ctx_size", 4096)
    split_mode = data.get("split_mode", "none")
    parallel = data.get("parallel", 1)
    batch_size = data.get("batch_size", 512)
    no_mmap = data.get("no_mmap", False)
    mlock = data.get("mlock", False)
    flash_attn = data.get("flash_attn", False)
    jinja = data.get("jinja", False)
    cache_type_k = data.get("cache_type_k", "f16")
    cache_type_v = data.get("cache_type_v", "f16")
    
    # Sampling Parameters
    temp = data.get("temp", 0.8)
    top_k = data.get("top_k", 40)
    top_p = data.get("top_p", 0.9)
    min_p = data.get("min_p", 0.05)
    repeat_penalty = data.get("repeat_penalty", 1.1)
    
    # RoPE Parameters
    rope_freq_base = data.get("rope_freq_base", 0)
    rope_freq_scale = data.get("rope_freq_scale", 0)
    
    # Backend Selection Logic (V0.4 feature - improved)
    backend = data.get("backend", "auto")
    logging.info(f"User preferred backend: {backend}")
    
    # If CPU is forced, ensure ngl is 0
    if backend == "cpu":
        gpu_layers = 0

    # Construct Command Arguments (V0.3 logic - working)
    args = []
    
    # Handle model input
    model_args = []
    if "-hf" in model_path:
        parts = model_path.split("-hf")
        if len(parts) > 1:
            repo = parts[1].strip().split()[0]
            model_args = ["-hf", repo]
    elif "-m" in model_path:
         parts = model_path.split("-m")
         if len(parts) > 1:
             path = parts[1].strip().split()[0]
             model_args = ["-m", path]
    else:
        model_args = ["-m", model_path]

    args.extend(model_args)
    args.extend(["-t", str(threads)])
    args.extend(["-ngl", str(gpu_layers)])
    args.extend(["--port", str(port)])
    args.extend(["--host", host])
    args.extend(["-c", str(ctx_size)])
    args.extend(["-sm", split_mode])
    args.extend(["-np", str(parallel)])
    args.extend(["-b", str(batch_size)])
    
    if no_mmap: args.append("--no-mmap")
    if mlock: args.append("--mlock")
    if flash_attn: args.extend(["-fa", "on"])  # V0.6.1: Fixed to use value format
    if jinja: args.append("--jinja")
    
    args.extend(["--cache-type-k", cache_type_k])
    args.extend(["--cache-type-v", cache_type_v])
    
    args.extend(["--temp", str(temp)])
    args.extend(["--top-k", str(top_k)])
    args.extend(["--top-p", str(top_p)])
    args.extend(["--min-p", str(min_p)])
    args.extend(["--repeat-penalty", str(repeat_penalty)])
    
    if rope_freq_base != 0: args.extend(["--rope-freq-base", str(rope_freq_base)])
    if rope_freq_scale != 0: args.extend(["--rope-freq-scale", str(rope_freq_scale)])

    # Prepare Environment
    cache_path = data.get("cache_path", ".")
    current_env = os.environ.copy()
    current_env["LLAMA_CACHE"] = cache_path
    
    # V0.7.4: Correct backend forcing via environment variables
    # Backend selection happens based on which GPU backends are VISIBLE
    if backend == "vulkan":
        # Hide ROCm to force Vulkan (Vulkan has no env var control)
        current_env["HIP_VISIBLE_DEVICES"] = "-1"
        logging.info("Backend: Vulkan - hiding ROCm via HIP_VISIBLE_DEVICES=-1")
    elif backend == "rocm":
        # Hide CUDA to prefer ROCm (though you don't have NVIDIA GPU)
        current_env["CUDA_VISIBLE_DEVICES"] = "-1"
        logging.info("Backend: ROCm - hiding CUDA via CUDA_VISIBLE_DEVICES=-1")
    elif backend == "cuda":
        # Hide ROCm to prefer CUDA
        current_env["HIP_VISIBLE_DEVICES"] = "-1"
        logging.info("Backend: CUDA - hiding ROCm via HIP_VISIBLE_DEVICES=-1")
    elif backend == "cpu":
        # Hide all GPU backends to force CPU
        current_env["CUDA_VISIBLE_DEVICES"] = "-1"
        current_env["HIP_VISIBLE_DEVICES"] = "-1"
        logging.info("Backend: CPU - hiding all GPU backends")
    # For "auto" or unrecognized, don't set any env vars
    
    # Log command for debugging
    full_cmd = f'$env:LLAMA_CACHE="{cache_path}"; {server_path} ' + " ".join(args)
    logging.info(f"Executing command: {full_cmd}")

    try:
        # Configure startup info to hide window
        startupinfo = None
        creationflags = 0
        if platform.system() == "Windows":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            creationflags = subprocess.CREATE_NO_WINDOW

        # Use subprocess directly (V0.3 logic - working)
        final_args = [server_path] + args
        
        server_process = subprocess.Popen(
            final_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=current_env,
            startupinfo=startupinfo,
            creationflags=creationflags
        )
        
        stop_event.clear()
        log_thread = threading.Thread(target=read_logs, args=(server_process,), daemon=True)
        log_thread.start()
        
        return jsonify({"status": "started", "command": full_cmd})
    except Exception as e:
        logging.error(f"Error in start_server: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/stop-server", methods=["POST"])
def stop_server():
    try:
        global server_process
        if server_process:
            # We need to kill the process and its children
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(server_process.pid)], 
                           creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0)
            server_process = None
        return jsonify({"status": "stopped"})
    except Exception as e:
        logging.error(f"Error in stop_server: {e}")
        return jsonify({"error": str(e)})

def read_logs(process):
    """Read logs from the server process and put them in the log queue."""
    if process and process.stdout:
        for line in iter(process.stdout.readline, ""):
            if line:
                log_queue.put(line.strip())
            else:
                break

@app.route("/logs")
def logs():
    try:
        def generate():
            while True:
                try:
                    line = log_queue.get(timeout=1)
                    # Parse color
                    color = "blue" # Default system log
                    lower_line = line.lower()
                    
                    if "error" in lower_line or "failed" in lower_line:
                        color = "red"
                    elif "warning" in lower_line or "warn" in lower_line:
                        color = "yellow"
                    elif "token" in lower_line or "eval time" in lower_line or "prompt eval" in lower_line:
                        color = "green"
                    
                    yield f"data: {color}|{line}\n\n"
                except queue.Empty:
                    yield "data: \n\n"

        return Response(generate(), mimetype="text/event-stream")
    except Exception as e:
        logging.error(f"Error in logs: {e}")
        return "Internal Server Error", 500

def create_icon():
    try:
        img = Image.open("icons/LlamaForge_32.png")
        return img
    except FileNotFoundError:
        img = Image.new("RGB", (32, 32), color="blue")
        return img

def setup_tray():
    global tray_icon
    icon = create_icon()
    tray_icon = pystray.Icon("LlamaForge", icon, "LlamaForge: Stopped", get_menu())
    tray_icon.run()

if __name__ == "__main__":
    setup_tray()
