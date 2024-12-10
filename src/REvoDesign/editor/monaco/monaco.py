import os
import shutil
import tarfile
import urllib.request

from platformdirs import user_data_dir

from ...logger import root_logger
from ...tools.package_manager import get_github_repo_tags
from ...tools.utils import run_worker_thread_with_progress
from .config import ConfigStore
from .server import ServerControl

logging = root_logger.getChild(__name__)


class MonacoEditorManager:
    def __init__(self, app_name="YourAppName", app_author="YourCompany", version="latest"):
        """
        Initialize MonacoEditorManager.

        Args:
            app_name (str): The application name for `user_data_dir`.
            app_author (str): The application author or company name.
            version (str): The version of the Monaco Editor to download. Defaults to "latest".
        """
        self.editor_path = os.path.join(user_data_dir(app_name, app_author), "monaco")
        self.html_template_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
        self.config_store = ConfigStore()

        self.version = version

    def ensure_editor_downloaded(self, no_upgrade: bool = True):
        """
        Ensure the specified version of Monaco Editor is downloaded and the HTML template is copied.
        """
        if not os.path.exists(self.editor_path):
            os.makedirs(self.editor_path)

        installed_monaco = [dirname for dirname in os.listdir(self.editor_path) if dirname.startswith("monaco-editor-")]
        if installed_monaco and no_upgrade:
            logging.info(f"Monaco Editor already installed: {installed_monaco[0]}.")
            version_dir = os.path.join(self.editor_path, installed_monaco[0])
            self.copy_html_template(version_dir)
            self.config_store.set("editor.backend.html_dir", version_dir)

            return

        # Fetch available tags
        tags = get_github_repo_tags("https://github.com/microsoft/monaco-editor")
        tags = [tag for tag in tags if not tag.endswith("rc") and 'dev' not in tag]
        logging.info(f"Available Monaco Editor tags: {tags}")

        if self.version == "latest":
            if not tags:
                raise ValueError("Could not fetch latest version from GitHub. Check network connection.")
            self.version = tags[0]  # Use the latest available tag

        self.version = self.version.lstrip("v")

        version_dir = os.path.join(self.editor_path, f"monaco-editor-{self.version}")
        if os.path.exists(version_dir):
            logging.info(f"Monaco Editor v{self.version} is already set up at {version_dir}.")
            self.copy_html_template(version_dir)
            self.config_store.set("editor.backend.html_dir", version_dir)
            return

        # Download and setup the editor
        logging.info(f"Downloading Monaco Editor v{self.version}...")
        try:
            self.download_monaco_editor(version=self.version)
            self.copy_html_template(version_dir)
            self.config_store.set("editor.backend.html_dir", version_dir)
        except Exception as e:
            raise RuntimeError(f"Failed to set up Monaco Editor: {e}")

    def download_monaco_editor(self, version="latest"):
        """
        Downloads and extracts the specified version of Monaco Editor.

        Args:
            version (str): The version to download, or "latest" for the latest version.
        """
        cdn_base_url = "https://registry.npmjs.org/monaco-editor/-/monaco-editor-"
        tarball_url = f"{cdn_base_url}{version}.tgz"
        tarball_path = os.path.join(self.editor_path, f"monaco-editor-{version}.tgz")
        extract_path = os.path.join(self.editor_path, f"monaco-editor-{version}")

        # Download tarball
        logging.info(f"Downloading tarball from {tarball_url}")
        urllib.request.urlretrieve(tarball_url, tarball_path)

        # Extract tarball
        logging.info(f"Extracting tarball to {extract_path}")
        with tarfile.open(tarball_path, "r:gz") as tar_ref:
            tar_ref.extractall(extract_path)

        # Move the `vs` directory to the expected location
        shutil.move(os.path.join(extract_path, "package", "min", "vs"), os.path.join(extract_path, "vs"))

        # Clean up tarball
        os.remove(tarball_path)
        logging.info("Monaco Editor downloaded and extracted successfully.")

    def copy_html_template(self, version_dir):
        """
        Copies the standalone HTML template file to the version directory.

        Args:
            version_dir (str): The directory where the Monaco Editor version is stored.
        """
        index_path = os.path.join(version_dir, "index.html")
        if not os.path.exists(self.html_template_path):
            raise FileNotFoundError(f"HTML template file not found at {self.html_template_path}")

        shutil.copy(self.html_template_path, index_path)
        logging.info(f"HTML template copied to {index_path}.")


def edit_file_with_monaco(file_path: str):
    """
    Function to invoke the Monaco Editor for editing a specified file.
    Uses `editor.backend.no_token` to determine if authentication is required.

    Args:
        file_path (str): The path of the file to edit.

    Raises:
        FileNotFoundError: If the specified file does not exist.
    """
    import webbrowser
    from pathlib import Path

    # Initialize Monaco Editor Manager
    monaco_manager = MonacoEditorManager(app_name="REvoDesign.MonacoEditor", app_author="REvoDesignUser")
    config_store = ConfigStore()

    # Step 1: Ensure Monaco Editor is ready
    logging.info("Ensuring Monaco Editor is set up...")
    monaco_manager.ensure_editor_downloaded()

    # Step 2: Ensure the server is running
    server_control = ServerControl()
    if not server_control.is_running:
        logging.info("Starting the server for Monaco Editor...")
        server_control.start_server()

    logging.info(f"Server launch status: {server_control.is_running}")

    # Step 3: Validate the file path
    target_file = Path(file_path)
    if not target_file.exists():
        raise FileNotFoundError(f"The file '{file_path}' does not exist.")
    logging.info(f"Validated file path: {file_path}")

    # Step 4: Construct the editor URL
    use_ssl = config_store.get('editor.backend.use_ssl', default=False)
    protocol = "https" if use_ssl else "http"
    host = config_store.get('editor.backend.host')
    port = config_store.get('editor.backend.port')
    token = config_store.get('editor.token', default=None)
    no_token = config_store.get('editor.backend.no_token', default=False)

    # Build the editor URL
    base_url = f"{protocol}://{host}:{port}"
    editor_url = f"{base_url}/editor?file_path={file_path}"
    if not no_token and token:
        editor_url += f"&token={token}"

    logging.info(f"Editor URL constructed: {editor_url}")

    # Open the editor in the browser
    logging.info(f"Opening Monaco Editor for file: {file_path}")
    webbrowser.open(editor_url)


def menu_edit_file(file_path):
    run_worker_thread_with_progress(
        worker_function=edit_file_with_monaco,
        file_path=file_path,
    )
