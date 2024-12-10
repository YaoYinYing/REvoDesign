import os
import gc
import threading
from typing import Optional
from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import JSONResponse
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


# Token management
def initialize_token() -> str:
    SECRET_TOKEN = secrets.token_urlsafe(32)
    ConfigBus().cfg.editor.token = SECRET_TOKEN
    print(f"Generated SECRET_TOKEN: {SECRET_TOKEN}")
    return SECRET_TOKEN

def get_token() -> str:
    return ConfigBus().cfg.editor.token

# Token-based security
security = HTTPBearer()

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if credentials.credentials != get_token():
        raise HTTPException(status_code=401, detail="Unauthorized")

# Endpoints
@app.get("/load_file", response_class=JSONResponse, dependencies=[Depends(verify_token)])
async def load_file(file_path: str):
    if not os.path.exists(file_path):
        return JSONResponse(content={"error": "File not found"}, status_code=404)
    with open(file_path, "r") as file:
        content = file.read()
    return {"content": content}

class SaveFileRequest(BaseModel):
    file_path: str
    content: str

@app.post("/save_file", response_class=JSONResponse, dependencies=[Depends(verify_token)])
async def save_file(data: SaveFileRequest):
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

        # Configure SSL
        ssl_manager = SSLCertificateManager(role="server")
        ssl_context = ssl_manager.generate_ssl_context()
        ConfigBus().cfg.editor.backend.crt = ssl_manager.crt_path
        ConfigBus().cfg.editor.backend.key = ssl_manager.key_path

        # Configure Uvicorn
        config = uvicorn.Config(
            app=app,
            host=ConfigBus().cfg.editor.backend.host,
            port=ConfigBus().cfg.editor.backend.port,
            ssl_certfile=ssl_manager.crt_path,
            ssl_keyfile=ssl_manager.key_path,
            log_level="info",
        )
        self.server = uvicorn.Server(config)

        # Start server in a WorkerThread
        self.server_thread = WorkerThread(func=self._run_server)
        self.server_thread.result_signal.connect(self._on_server_result)
        self.server_thread.finished_signal.connect(self._on_server_finished)
        self.server_thread.start()
        self.is_running = True
        print("Server started.")

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