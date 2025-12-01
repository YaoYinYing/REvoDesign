import os
import shutil
import tarfile

from platformdirs import user_data_dir

from REvoDesign import issues

from ...driver.ui_driver import ConfigBus, StoresWidget
from ...logger import ROOT_LOGGER
from ...tools.download_registry import DownloadedFile, FileDownloadRegistry
from ...tools.package_manager import get_github_repo_tags, notify_box
from ...tools.utils import run_worker_thread_with_progress
from .config import ConfigStore

logging = ROOT_LOGGER.getChild(__name__)


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

        # must be a valid un-tarballed directory
        installed_monaco = [
            dirname
            for dirname in os.listdir(self.editor_path)
            if dirname.startswith("monaco-editor-") and os.path.isdir(os.path.join(self.editor_path, dirname))
        ]
        if installed_monaco and no_upgrade:
            logging.info(f"Monaco Editor already installed: {installed_monaco[0]}.")
            version_dir = os.path.join(self.editor_path, installed_monaco[0])
            self.copy_html_template(version_dir)
            self.config_store.set("editor.backend.html_dir", version_dir)

            return

        # Fetch available tags
        tags = get_github_repo_tags("https://github.com/microsoft/monaco-editor")
        tags = [tag for tag in tags if not ("rc" in tag or 'dev' in tag)]
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
            raise RuntimeError(f"Failed to set up Monaco Editor: {e}") from e

    def download_monaco_editor(self, version="latest"):
        """
        Downloads and extracts the specified version of Monaco Editor.

        Args:
            version (str): The version to download, or "latest" for the latest version.
        """
        # https://registry.npmjs.org/monaco-editor/-/monaco-editor-0.55.1.tgz
        cdn_base_url = "https://registry.npmjs.org/monaco-editor/-/"
        extract_path = os.path.join(self.editor_path, f"monaco-editor-{version}")

        down_registry = FileDownloadRegistry(
            name="monaco-editor",
            base_url=cdn_base_url,
            registry={
                f'monaco-editor-{version}.tgz': None
            },
            version=version,
            customized_directory=self.editor_path,
            # https://github.com/amio/npm-mirrors/blob/master/index.js
            alternative_base_urls=[
                "https://skimdb.npmjs.com/registry/monaco-editor/-/",
                "https://r.cnpmjs.org/monaco-editor/-/",
                "https://registry.npm.taobao.org/monaco-editor/-/",
                "https://registry.yarnpkg.com/monaco-editor/-/"

            ]
        )

        # Download tarball
        try:
            logging.info(f"Downloading tarball from {down_registry}")
            downloaded_file: DownloadedFile = down_registry.setup(f'monaco-editor-{version}.tgz')
        except issues.NetworkError as e:
            logging.error(f"Error downloading tarball: {e}, cleaning up...")
            # os.remove(tarball_path)
            raise issues.NetworkError from e

        # Extract tarball
        logging.info(f"Extracting tarball to {extract_path}")
        with tarfile.open(downloaded_file.downloaded, "r:gz") as tar_ref:
            tar_ref.extractall(extract_path)

        # Move the `vs` directory to the expected location
        shutil.move(os.path.join(extract_path, "package", "min", "vs"), os.path.join(extract_path, "vs"))

        # Clean up tarball
        os.remove(downloaded_file.downloaded)
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


def ensure_monaco() -> bool:
    """
    Ensures that the Monaco Editor is set up and ready to use.

    Returns:
        bool: True if the Monaco Editor is successfully set up, False otherwise.
    """

    # Initialize Monaco Editor Manager
    monaco_manager = MonacoEditorManager(app_name="REvoDesign.MonacoEditor", app_author="REvoDesignUser")

    try:
        # Step 1: Ensure Monaco Editor is ready
        logging.info("Ensuring Monaco Editor is set up...")
        monaco_manager.ensure_editor_downloaded()
        return True
    except issues.NetworkError as e:
        # Log the network error and return False
        logging.error("Network error occurred while setting up Monaco Editor. Please check your network connection.")
        return False


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

    config_store = ConfigStore()

    # Step 2: Ensure the server is running
    server_monitor = StoresWidget().server_switches['Editor_Backend']
    logging.info(f"Server launch status: {server_monitor.controller.is_running}")
    if not server_monitor.controller.is_running:
        server_monitor._start_server()

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
    """
    Edit the specified file using Monaco Editor.

    Args:
        file_path (str): The path to the file that needs to be edited.

    Returns:
        None
    """
    # Check if Monaco Editor is available
    has_monaco = run_worker_thread_with_progress(
        worker_function=ensure_monaco,
        progress_bar=ConfigBus().ui.progressBar,
    )
    if not has_monaco:
        notify_box(
            message='Monaco Editor is not available. Please check your network connection '
            'or set `https_proxy` as environment variables (Menu->Edit->Environment Variables->Add) and try again.',
            error_type=issues.DependencyError
        )

    # Edit the file using Monaco Editor
    run_worker_thread_with_progress(
        worker_function=edit_file_with_monaco,
        file_path=file_path,
    )
