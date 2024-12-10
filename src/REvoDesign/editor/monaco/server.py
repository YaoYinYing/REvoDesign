import os
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import secrets
import uvicorn
import uvicorn.server
from REvoDesign.basic.abc_singleton import SingletonAbstract
from REvoDesign.tools.ssl import SSLCertificateManager
from ...driver.ui_driver import ConfigBus
from ...tools.package_manager import WorkerThread

# FastAPI app
app = FastAPI()

editor_html= open(os.path.join(os.path.dirname(__file__), "static", "index.html"), "r", encoding="utf-8").read()
# Token management
def initialize_token() -> str:
    SECRET_TOKEN = secrets.token_urlsafe(32)
    ConfigBus().set_value('editor.token',SECRET_TOKEN)
    print(f"Generated SECRET_TOKEN: {SECRET_TOKEN}")
    return SECRET_TOKEN

def get_token() -> str:
    return str(ConfigBus().get_value('editor.token'))

def distruct_token() -> None:
    ConfigBus().set_value('editor.token','')

# Token-based security
security = HTTPBearer()

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if credentials.credentials != get_token():
        raise HTTPException(status_code=401, detail="Unauthorized")
    
@app.post("/editor", response_class=HTMLResponse)
async def serve_editor(request: Request):
    """
    Serves the Monaco Editor page if the token is valid or no-token mode is enabled.

    Args:
        request (Request): The incoming request containing the token.

    Returns:
        HTMLResponse: The HTML content for the editor.
    """
    # Check if no-token mode is enabled
    no_token = ConfigBus().get_value('editor.backend.no_token', bool, default_value=False)
    if not no_token:
        # Token validation is required
        data = await request.json()
        token = data.get("token")
        if token != ConfigBus().get_value('editor.token'):
            raise HTTPException(status_code=403, detail="Unauthorized")

    # Serve the editor HTML
    html_template_path = os.path.join(ConfigBus().get_value('editor.backend.html_dir'), "index.html")
    if not os.path.exists(html_template_path):
        raise HTTPException(status_code=500, detail="Editor HTML template not found.")
    
    with open(html_template_path, "r") as html_file:
        editor_html = html_file.read()
    
    return HTMLResponse(content=editor_html)


# Endpoints
@app.get("/load_file", response_class=JSONResponse)
async def load_file(file_path: str, credentials: HTTPAuthorizationCredentials = Depends(security)):
    # Check if no-token mode is enabled
    no_token = ConfigBus().get_value('editor.backend.no_token', bool, default_value=False)
    if not no_token:
        token = credentials.credentials
        if token != ConfigBus().get_value('editor.token'):
            raise HTTPException(status_code=401, detail="Unauthorized")
    
    # Load the file content
    if not os.path.exists(file_path):
        return JSONResponse(content={"error": "File not found"}, status_code=404)
    with open(file_path, "r") as file:
        content = file.read()
    return {"content": content}

class SaveFileRequest(BaseModel):
    file_path: str
    content: str

@app.post("/save_file", response_class=JSONResponse)
async def save_file(data: SaveFileRequest, credentials: HTTPAuthorizationCredentials = Depends(security)):
    # Check if no-token mode is enabled
    no_token = ConfigBus().get_value('editor.backend.no_token', bool, default_value=False)
    if not no_token:
        token = credentials.credentials
        if token != ConfigBus().get_value('editor.token'):
            raise HTTPException(status_code=401, detail="Unauthorized")
    
    # Save the file content
    with open(data.file_path, "w") as file:
        file.write(data.content)
    return {"status": "success"}

class ServerControl(SingletonAbstract):
    def __init__(self):
        if not hasattr(self, "initialized"):
            self.server_thread = None  # WorkerThread instance
            self.is_running = False
            self.server = None  # Uvicorn Server instance

    def start_server(self):
        if self.is_running:
            print("Server is already running.")
            return

        # Check if token authentication is required
        no_token = ConfigBus().get_value('editor.backend.no_token', bool, default_value=False)
        if not no_token:
            initialize_token()
        else:
            ConfigBus().set_value('editor.token', None)  # Ensure no token is used


        # Determine if SSL is enabled
        use_ssl = ConfigBus().get_value('editor.backend.use_ssl', bool, default_value=False)
        ssl_certfile = None
        ssl_keyfile = None

        if use_ssl:
            # Configure SSL
            ssl_manager = SSLCertificateManager(role="server")
            ssl_context = ssl_manager.generate_ssl_context()
            ssl_certfile = ssl_manager.crt_path
            ssl_keyfile = ssl_manager.key_path

            # Store SSL paths in ConfigBus
            ConfigBus().set_value('editor.backend.crt', ssl_certfile)
            ConfigBus().set_value('editor.backend.key', ssl_keyfile)

        # Configure Uvicorn
        config = uvicorn.Config(
            app=app,
            host=ConfigBus().get_value('editor.backend.host', str, reject_none=True),
            port=ConfigBus().get_value('editor.backend.port', int, reject_none=True),
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
        print(f"Server started with {'SSL' if use_ssl else 'no SSL'}.")

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
