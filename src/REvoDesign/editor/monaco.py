import os
import shutil
import sys
import tarfile
import urllib.request

from PyQt5.QtCore import QTimer, QUrl
from PyQt5.QtWebEngineWidgets import QWebEngineSettings, QWebEngineView
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget

from REvoDesign.tools.package_manager import get_github_repo_tags
from REvoDesign.tools.utils import timing

script_path = os.path.dirname(__file__)


class MonacoEditorWidget(QWebEngineView):
    def __init__(self, parent=None, version="latest"):
        super().__init__(parent)
        self.version = version
        self.editor_path = os.path.join(script_path, "static", "monaco")  # Directory to store the editor
        # Enable developer tools for debugging
        settings = self.settings()
        settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        if hasattr(QWebEngineSettings, "DeveloperExtrasEnabled"):
            settings.setAttribute(QWebEngineSettings.DeveloperExtrasEnabled, True)
        else:
            print("DeveloperExtrasEnabled is not supported in this version of PyQt.")

        self.ensure_editor_downloaded()
        self.load_editor()

    def ensure_editor_downloaded(self):
        """Ensure the specified version of Monaco Editor is downloaded."""
        if not os.path.exists(self.editor_path):
            os.makedirs(self.editor_path)

        tags = get_github_repo_tags("https://github.com/microsoft/monaco-editor")

        tags = [tag for tag in tags if not tag.endswith("rc") or 'dev' in tag]
        print(tags)

        if self.version == "latest":
            if not tags:
                raise ValueError("Could not fetch latest version from GitHub. Check network connection.")
            self.version = tags[0]  # Use the latest available tag

        self.version = self.version.lstrip("v")

        version_dir = os.path.join(self.editor_path, f"monaco-editor-{self.version}")
        os.path.join(version_dir, "index.html")

        if os.path.exists(version_dir):
            print(f"Monaco Editor v{self.version} is already set up at {version_dir}.")
            self.generate_index_html(version_dir)  # get html the latest also
            return

        print(f"Downloading Monaco Editor v{self.version}...")
        try:
            self.download_monaco_editor(version=self.version)
            self.generate_index_html(version_dir)
        except Exception as e:
            raise RuntimeError(f"Failed to set up Monaco Editor: {e}")

    def download_monaco_editor(self, version="latest"):
        """
        Downloads the specified version of Monaco Editor.
        Args:
            version (str): The version to download, or "latest" for the latest version.
        """
        # GitHub CDN URL for Monaco Editor releases
        cdn_base_url = "https://registry.npmjs.org/monaco-editor/-/monaco-editor-"

        tarball_url = f"{cdn_base_url}{version}.tgz"
        tarball_path = os.path.join(self.editor_path, f"monaco-editor-{version}.tgz")
        extract_path = os.path.join(self.editor_path, f"monaco-editor-{version}")

        # Download tarball
        with timing(f'Downloading tarball from {tarball_url}'):
            urllib.request.urlretrieve(tarball_url, tarball_path)

        # Extract tarball
        with tarfile.open(tarball_path, "r:gz") as tar_ref:
            tar_ref.extractall(extract_path)

        shutil.move(os.path.join(extract_path, "package/dev/vs"), os.path.join(extract_path, "vs"))

        # Clean up tarball
        os.remove(tarball_path)

    def generate_index_html(self, version_dir):
        """Generate the index.html file required for Monaco Editor."""
        index_path = os.path.join(version_dir, "index.html")
        vs_path = os.path.join(version_dir, "vs")

        if not os.path.exists(vs_path):
            raise RuntimeError(f"Monaco Editor 'vs' directory not found in {version_dir}.")

        # Properly formatted HTML and JavaScript
        index_content = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Monaco Editor</title>
            <script src="./vs/loader.js"></script>
            <style>
                html, body, #container {
                    margin: 0;
                    padding: 0;
                    width: 100%;
                    height: 100%;
                }
            </style>
        </head>
        <body>
            <div id="container"></div>
            <script>
    console.log('Initializing Monaco Editor...');
    var isEditorReady = false;

    require.config({ paths: { 'vs': './vs' } });
    require(['vs/editor/editor.main'], function () {
        console.log('Monaco Editor initialized.');
        window.editor = monaco.editor.create(document.getElementById('container'), {
            value: '',
            language: 'python',
            theme: 'vs-dark',
            automaticLayout: true,
            lineNumbers: 'on',
            indentGuides: true
        });
        isEditorReady = true;
        console.log('Editor is ready.');
    });

    window.setEditorContent = function(content) {
        if (isEditorReady && window.editor) {
            console.log('Setting editor content:', content);
            window.editor.setValue(content);
        } else {
            console.warn('Editor is not ready yet.');
        }
    };

    window.getEditorContent = function() {
        if (isEditorReady && window.editor) {
            console.log('Getting editor content.');
            return window.editor.getValue();
        }
        console.warn('Editor is not ready yet.');
        return '';
    };
</script>



        </body>
        </html>
        """
        with open(index_path, "w") as index_file:
            index_file.write(index_content)

        print('HTML file refreshed successfully.')

    def load_editor(self):
        """Load the Monaco Editor's index.html into the QWebEngineView."""
        version_dir = os.path.join(self.editor_path, f"monaco-editor-{self.version}")
        index_path = os.path.join(version_dir, "index.html")
        if not os.path.exists(index_path):
            raise RuntimeError(f"Could not find index.html in {version_dir}.")

        # Print the absolute path for debugging
        abs_path = os.path.abspath(index_path)
        print(f"Loading index.html from: {abs_path}")

        # Load the file into the QWebEngineView
        self.setUrl(QUrl.fromLocalFile(abs_path))

    def set_content(self, content: str):
        """Set the content of the Monaco Editor."""
        def try_set_content():
            js_code = f"window.setEditorContent({repr(content)});"
            self.page().runJavaScript(js_code)

        # Delay by 2 seconds to ensure editor readiness
        QTimer.singleShot(2000, try_set_content)

    def get_content(self, callback):
        """Get the content of the Monaco Editor."""
        js_code = "getEditorContent();"
        self.page().runJavaScript(js_code, callback)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Monaco Editor")
        self.setGeometry(100, 100, 1024, 768)

        # Monaco Editor Widget
        self.editor = MonacoEditorWidget(self)
        self.setCentralWidget(self.editor)

        # Set initial content
        self.editor.set_content("print('Hello, Monaco Editor!')")

        # Get content after 3 seconds (example)
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(3000, self.get_editor_content)

    def get_editor_content(self):
        def callback(content):
            print("Editor Content:", content)

        self.editor.get_content(callback)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec_())
