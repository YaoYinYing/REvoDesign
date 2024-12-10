import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
import uvicorn.server
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from REvoDesign import ConfigBus
from REvoDesign.basic.abc_singleton import SingletonAbstract
from REvoDesign.tools.ssl import SSLCertificateManager

from ...tools.package_manager import WorkerThread
from .config import ConfigStore

# FastAPI app

this_file_dir = os.path.dirname(os.path.abspath(__file__))


# Token management
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


# Token-based security
security = HTTPBearer()


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if credentials.credentials != get_token():
        raise HTTPException(status_code=401, detail="Unauthorized")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    config_store = ConfigStore()
    app.mount("/static", StaticFiles(directory=config_store.get("editor.backend.html_dir")), name="static")

    print("Application startup complete.")

    yield  # Application runs here

    # Shutdown logic
    config_store.reset()
    print("Application shutdown complete.")

app = FastAPI(lifespan=lifespan)


@app.get("/favicon.svg", include_in_schema=False)
async def favicon():
    return FileResponse(os.path.join(this_file_dir, '..', '..', 'meta/images/logo.svg'), media_type="image/svg+xml")


@app.get("/editor", response_class=HTMLResponse)
async def serve_editor(file_path: str, token: str = None):
    """
    Serve the Monaco Editor HTML, allowing for file-based editing.

    Args:
        file_path (str): The path of the file to be edited.
        token (str): Optional token for authentication.

    Returns:
        HTMLResponse: The Monaco Editor HTML page.
    """
    config_store = ConfigStore()
    expected_token = config_store.get("editor.token")
    use_ssl = config_store.get("editor.backend.use_ssl", default=False)

    # Validate token if use_ssl is enabled
    if use_ssl and token != expected_token:
        raise HTTPException(status_code=403, detail="Unauthorized")

    # Validate the file path
    target_file = Path(file_path)
    if not target_file.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")

    # Serve the editor HTML
    html_template_path = os.path.join(config_store.get("editor.backend.html_dir"), 'index.html')
    if not os.path.exists(html_template_path):
        raise HTTPException(status_code=500, detail=f"Editor HTML template not found: {html_template_path}.")

    with open(html_template_path) as html_file:
        editor_html = html_file.read()

    # Inject the file path into the editor's HTML template
    editor_html = editor_html.replace("{{file_path}}", str(target_file))

    return HTMLResponse(content=editor_html)


@app.get("/load_file", response_class=JSONResponse)
async def load_file(
    file_path: str,
    token: str = Query(None),
):
    config_store = ConfigStore()
    no_token = config_store.get("editor.backend.no_token", False)

    # Token validation
    if not no_token:
        expected_token = config_store.get("editor.token")
        if token != expected_token:
            raise HTTPException(status_code=403, detail="Unauthorized")

    # Validate file existence
    target_file = Path(file_path)
    if not target_file.exists():
        return JSONResponse(content={"error": "File not found"}, status_code=404)

    # Load file content
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
):
    config_store = ConfigStore()
    no_token = config_store.get("editor.backend.no_token", False)

    # Token validation
    if not no_token:
        expected_token = config_store.get("editor.token")
        if token != expected_token:
            raise HTTPException(status_code=403, detail="Unauthorized")

    # Validate the file path
    target_file = Path(data.file_path)
    if not target_file.parent.exists():
        return JSONResponse(content={"error": f"Directory does not exist: {target_file.parent}"}, status_code=400)

    # Save file content
    try:
        target_file.write_text(data.content)
        return {"status": "success"}
    except Exception as e:
        return JSONResponse(content={"error": f"Failed to save file: {str(e)}"}, status_code=500)


class ServerControl(SingletonAbstract):
    def __init__(self):
        if not hasattr(self, "initialized"):
            self.server_thread = None  # WorkerThread instance
            self.is_running = False
            self.server = None  # Uvicorn Server instance
            self.config_store = ConfigStore()

            # Mark the instance as initialized to prevent reinitialization
            self.initialized = True

    def start_server(self):
        if self.is_running:
            print("Server is already running.")
            return

        # Check if token authentication is required
        no_token = ConfigBus().get_value('editor.backend.no_token', bool, default_value=False)
        self.config_store.set('editor.backend.no_token', no_token)
        if not no_token:
            initialize_token()
        else:
            self.config_store.set('editor.token', None)  # Ensure no token is used

        HTML_DIR = self.config_store.get('editor.backend.html_dir')
        print(f'{HTML_DIR=}')

        # Determine if SSL is enabled
        use_ssl = ConfigBus().get_value('editor.backend.use_ssl', bool, default_value=False)
        self.config_store.set('editor.backend.use_ssl', use_ssl)
        ssl_certfile = None
        ssl_keyfile = None

        if use_ssl:
            # Configure SSL
            ssl_manager = SSLCertificateManager(role="server")
            ssl_manager.generate_ssl_context()
            ssl_certfile = ssl_manager.crt_path
            ssl_keyfile = ssl_manager.key_path

            # Store SSL paths in ConfigBus
            self.config_store.set('editor.backend.crt', ssl_certfile)
            self.config_store.set('editor.backend.key', ssl_keyfile)

        host = ConfigBus().get_value('editor.backend.host', str, reject_none=True)
        self.config_store.set('editor.backend.host', host)
        port = ConfigBus().get_value('editor.backend.port', int, reject_none=True)
        self.config_store.set('editor.backend.port', port)

        # Configure Uvicorn
        config = uvicorn.Config(
            app=app,
            host=self.config_store.get('editor.backend.host'),
            port=self.config_store.get('editor.backend.port'),
            ssl_certfile=ssl_certfile,
            ssl_keyfile=ssl_keyfile,
            log_level="info",
        )
        self.server = uvicorn.Server(config)

        # Start server in a WorkerThread
        self.server_thread = WorkerThread(func=self._run_server)
        self.server_thread.result_signal.connect(self._on_server_result)
        self.server_thread.finished_signal.connect(self._on_server_finished)
        self.server_thread.start()
        self.is_running = True
        print(
            f"Server started with {'SSL' if use_ssl else 'no SSL'} and {'no token' if no_token else 'token-based'} authentication.")
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

    def _run_server(self):
        """
        The function executed in the worker thread.
        """
        if self.server:
            self.server.run()

    def _on_server_result(self, result):
        """
        Handle results from the WorkerThread.
        """
        print(f"Server result: {result}")

    def _on_server_finished(self):
        """
        Handle the completion of the WorkerThread.
        """
        self.is_running = False
        print("Server thread finished.")
