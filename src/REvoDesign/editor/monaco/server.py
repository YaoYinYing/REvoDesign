import os
import secrets
import time
import warnings
from collections import defaultdict
from contextlib import asynccontextmanager
from html import escape
from pathlib import Path
import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.security import HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from REvoDesign import ConfigBus, issues
from REvoDesign.basic.server_monitor import ServerControlAbstract
from REvoDesign.editor.monaco.monaco import ensure_monaco
from REvoDesign.tools.ssl_certificates import SSLCertificateManager
from ...logger import ROOT_LOGGER
from ...tools.package_manager import WorkerThread
from .config import ConfigStore
logging = ROOT_LOGGER.getChild(__name__)
def get_file_whitelist():
    from platformdirs import user_log_path
    from REvoDesign.bootstrap import REVODESIGN_CONFIG_FILE
    bus = ConfigBus()
    logfile = bus.cfg.log.handlers.file.filename
    notebookfile = bus.cfg.log.handlers.notebook.filename
    if logfile == "AUTO":
        logfile_dir = user_log_path("REvoDesign", ensure_exists=True)
        logfile = os.path.join(
            logfile_dir, "REvoDesign.runtime.log"
        )
    if notebookfile == "AUTO":
        notebookfile_dir = user_log_path("REvoDesign", ensure_exists=True)
        notebookfile = os.path.join(
            notebookfile_dir, "REvoDesign.notebook.log"
        )
    editable_files = (
        REVODESIGN_CONFIG_FILE,
    )
    readonly_files = (
        logfile,
        notebookfile,
    )
    print(f"Editable files: {editable_files}")
    print(f"Readonly files: {readonly_files}")
    return editable_files, readonly_files
def is_file_allowed(file_path: Path, require_editable=False):
    config_store = ConfigStore()
    editable_files = config_store.get("monaco.file_whitelist.editable", default=())
    readonly_files = config_store.get("monaco.file_whitelist.readonly", default=())
    abs_path = str(file_path.resolve())
    if require_editable:
        return abs_path in editable_files
    return abs_path in editable_files or abs_path in readonly_files
failed_attempts = defaultdict(list)
MAX_FAILURES = 5
TIME_WINDOW = 60  
def record_failure(request: Request):
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    failed_attempts[ip].append(now)
    failed_attempts[ip] = [t for t in failed_attempts[ip] if now - t < TIME_WINDOW]
def should_block(request: Request):
    ip = request.client.host if request.client else "unknown"
    return len(failed_attempts[ip]) >= MAX_FAILURES
def initialize_token() -> str:
    config_store = ConfigStore()
    SECRET_TOKEN = secrets.token_urlsafe(32)
    config_store.set("editor.token", SECRET_TOKEN)
    print(f"Generated SECRET_TOKEN: {SECRET_TOKEN}")
    return SECRET_TOKEN
def get_token() -> str:
    config_store = ConfigStore()
    return config_store.get('editor.token')
def distruct_token() -> None:
    config_store = ConfigStore()
    config_store.reset()
security = HTTPBearer()
def verify_token(token: str, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    config_store = ConfigStore()
    expected_token = config_store.get("editor.token")
    no_token = config_store.get("editor.backend.no_token", default=False)
    if should_block(request):
        print(f"Blocked IP: {client_ip}")
        raise HTTPException(status_code=429, detail="Too many failed attempts. Please try again later.")
    if (not no_token) and token != expected_token:
        record_failure(request)
        raise HTTPException(status_code=401, detail="Unauthorized")
@asynccontextmanager
async def lifespan(app: FastAPI):
    config_store = ConfigStore()
    html_dir = config_store.get("editor.backend.html_dir")
    if not html_dir:
        warnings.warn(issues.MissingExternalTool("Monaco Editor is not ready."))
        ensure_monaco()
        html_dir = config_store.get("editor.backend.html_dir")
    app.mount("/static", StaticFiles(directory=html_dir), name="static")
    editable_files, readonly_files = get_file_whitelist()
    config_store.set("monaco.file_whitelist.editable", editable_files)
    config_store.set("monaco.file_whitelist.readonly", readonly_files)
    print("Application startup complete.")
    yield
    config_store.reset()
    print("Application shutdown complete.")
app = FastAPI(lifespan=lifespan)
@app.get("/favicon.svg", include_in_schema=False)
async def favicon():
    this_file_dir = os.path.dirname(os.path.abspath(__file__))
    return FileResponse(os.path.join(this_file_dir, '..', '..', 'meta/images/logo.svg'), media_type="image/svg+xml")
@app.get("/editor", response_class=HTMLResponse)
async def serve_editor(file_path: str, token: str = None, request: Request = None):
    verify_token(token, request)
    config_store = ConfigStore()
    target_file = Path(file_path)
    if not is_file_allowed(target_file, require_editable=False):
        record_failure(request)
        raise HTTPException(status_code=403, detail="Access to this file is not allowed.")
    if not target_file.exists():
        record_failure(request)
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    html_template_path = os.path.join(config_store.get("editor.backend.html_dir"), 'index.html')
    if not os.path.exists(html_template_path):
        raise HTTPException(status_code=500, detail=f"Editor HTML template not found: {html_template_path}.")
    with open(html_template_path) as html_file:
        editor_html = html_file.read()
    safe_file_path = escape(str(target_file.resolve()))
    editor_html = editor_html.replace("{{file_path}}", safe_file_path)
    return HTMLResponse(content=editor_html)
@app.get("/load_file", response_class=JSONResponse)
async def load_file(
    file_path: str,
    token: str = Query(None),
    request: Request = None
):
    verify_token(token, request)
    target_file = Path(file_path)
    if not is_file_allowed(target_file, require_editable=False):
        record_failure(request)
        raise HTTPException(status_code=403, detail=f"Loading this file is not allowed: Permission denied.")
    if not target_file.exists():
        record_failure(request)
        return JSONResponse(content={"error": "File not found"}, status_code=404)
    try:
        content = target_file.read_text()
        return {"content": content}
    except Exception as e:
        return JSONResponse(content={"error": f"Failed to load file: {str(e)}"}, status_code=500)
class SaveFileRequest(BaseModel):
    file_path: str
    content: str
@app.post("/save_file", response_class=JSONResponse)
async def save_file(
    data: SaveFileRequest,
    token: str = Query(None),
    request: Request = None
):
    verify_token(token, request)
    target_file = Path(data.file_path).resolve()
    if not is_file_allowed(target_file, require_editable=True):
        record_failure(request)
        raise HTTPException(status_code=403, detail="Writing into this file is not allowed.")
    if not target_file.parent.exists():
        record_failure(request)
        return JSONResponse(content={"error": f"Directory does not exist: {target_file.parent}"}, status_code=400)
    try:
        target_file.write_text(data.content)
        return {"status": "success"}
    except Exception as e:
        return JSONResponse(content={"error": f"Failed to save file: {str(e)}"}, status_code=500)
class ServerControl(ServerControlAbstract):
    def singleton_init(self):
        self.server_thread: WorkerThread = None  
        self.is_running = False
        self.server: uvicorn.Server = None  
        self.config_store = ConfigStore()
    def start_server(self):
        if self.is_running:
            print("Server is already running.")
            return
        no_token = ConfigBus().get_value('editor.backend.no_token', bool, default_value=False)
        self.config_store.set('editor.backend.no_token', no_token)
        if not no_token:
            initialize_token()
        else:
            self.config_store.set('editor.token', None)  
        HTML_DIR = self.config_store.get('editor.backend.html_dir')
        print(f'{HTML_DIR=}')
        use_ssl = ConfigBus().get_value('editor.backend.use_ssl', bool, default_value=False)
        self.config_store.set('editor.backend.use_ssl', use_ssl)
        ssl_certfile = None
        ssl_keyfile = None
        if use_ssl:
            ssl_manager = SSLCertificateManager(role="server")
            ssl_manager.generate_ssl_context()
            ssl_certfile = ssl_manager.crt_path
            ssl_keyfile = ssl_manager.key_path
            self.config_store.set('editor.backend.crt', ssl_certfile)
            self.config_store.set('editor.backend.key', ssl_keyfile)
        host = ConfigBus().get_value('editor.backend.host', str, reject_none=True)
        self.config_store.set('editor.backend.host', host)
        port = ConfigBus().get_value('editor.backend.port', int, reject_none=True)
        self.config_store.set('editor.backend.port', port)
        config = uvicorn.Config(
            app=app,
            host=self.config_store.get('editor.backend.host'),
            port=self.config_store.get('editor.backend.port'),
            ssl_certfile=ssl_certfile,
            ssl_keyfile=ssl_keyfile,
            log_level="info",
        )
        self.server = uvicorn.Server(config)
        self.server_thread = WorkerThread(func=self._run_server)
        self.server_thread.result_signal.connect(self._on_server_result)
        self.server_thread.finished_signal.connect(self._on_server_finished)
        self.server_thread.start()
        self.is_running = True
        print(f"Server started with {'SSL' if use_ssl else 'no SSL'} and "
              f"{'no token' if no_token else 'token-based'} authentication.")
        print(f'ServerControl::Config:{self.config_store.cfg}')
    def stop_server(self):
        if not self.is_running:
            print("Server is not running.")
            return
        print("Stopping server...")
        if self.server:
            self.server.should_exit = True
        if self.server_thread:
            self.server_thread.interrupt()
        self.is_running = False
        distruct_token()