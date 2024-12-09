import os
import sys

from PyQt5.QtCore import QRegularExpression, Qt
from PyQt5.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat
from PyQt5.QtWidgets import (QAction, QApplication, QFileDialog, QHBoxLayout,
                             QMainWindow, QMessageBox, QPlainTextEdit,
                             QVBoxLayout, QWidget)


class SyntaxHighlighter(QSyntaxHighlighter):
    """Syntax Highlighter to support different file types."""

    def __init__(self, document, file_extension):
        super().__init__(document)
        self.file_extension = file_extension
        self.highlighting_rules = []

        # Define highlighting rules based on the file extension
        self.setup_highlighting_rules()

    def setup_highlighting_rules(self):
        """Set up syntax highlighting rules based on file type."""
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#0000FF"))
        keyword_format.setFontWeight(QFont.Bold)

        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#008000"))

        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#808080"))
        comment_format.setFontItalic(True)

        # YAML/JSON
        if self.file_extension in {".yaml", ".yml", ".json"}:
            self.highlighting_rules.append((QRegularExpression(r'".*?"|\'.*?\''), string_format))  # Strings
            self.highlighting_rules.append((QRegularExpression(r"\b(true|false|null)\b"), keyword_format))  # Keywords
            self.highlighting_rules.append((QRegularExpression(r"#.*"), comment_format))  # Comments

        # INI
        elif self.file_extension == ".ini":
            self.highlighting_rules.append((QRegularExpression(r"^\[.*\]"), keyword_format))  # Section Headers
            self.highlighting_rules.append((QRegularExpression(r"=.*"), string_format))  # Values
            self.highlighting_rules.append((QRegularExpression(r";.*"), comment_format))  # Comments

        # CSV
        elif self.file_extension == ".csv":
            self.highlighting_rules.append((QRegularExpression(r",|;"), keyword_format))  # Delimiters
            self.highlighting_rules.append((QRegularExpression(r"\".*?\""), string_format))  # Quoted strings

    def highlightBlock(self, text):
        """Apply highlighting rules to a block of text."""
        for pattern, fmt in self.highlighting_rules:
            match_iterator = pattern.globalMatch(text)
            while match_iterator.hasNext():
                match = match_iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), fmt)


class TextEditor(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("Type here...")
        self.syntax_highlighter = None
        self.file_extension = ""

    def set_syntax_highlighting(self, file_extension):
        """Enable syntax highlighting based on the file extension."""
        self.file_extension = file_extension
        self.syntax_highlighter = SyntaxHighlighter(self.document(), file_extension)


class TextEditorWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Advanced Text Editor")
        self.setGeometry(100, 100, 800, 600)

        # Create main editor
        self.editor = TextEditor(self)

        # Central widget
        central_widget = QWidget(self)
        layout = QHBoxLayout(central_widget)
        layout.addWidget(self.editor)
        layout.setContentsMargins(0, 0, 0, 0)
        central_widget.setLayout(layout)
        self.setWig(central_widget)

        # Menu bar actions
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("File")

        open_action = QAction("Open", self)
        open_action.triggered.connect(self.open_file)
        file_menu.addAction(open_action)

        edit_action = QAction("Edit Config", self)
        edit_action.triggered.connect(lambda: self.edit_configure("src/REvoDesign/config/global_config.yaml"))
        file_menu.addAction(edit_action)

        save_action = QAction("Save", self)
        save_action.triggered.connect(self.save_file)
        file_menu.addAction(save_action)

        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

    def open_file(self):
        """Open a file and load its content into the editor."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open File", "", "All Files (*);;Text Files (*.txt);;JSON Files (*.json);;YAML Files (*.yaml *.yml);;INI Files (*.ini);;CSV Files (*.csv)")
        if file_path:
            self.load_file(file_path)

    def edit_configure(self, file_path):
        """Open and edit a predefined configuration file."""
        if os.path.exists(file_path):
            self.load_file(file_path)
        else:
            QMessageBox.critical(self, "Error", f"File not found: {file_path}")

    def load_file(self, file_path):
        """Load the file into the editor and set syntax highlighting."""
        try:
            with open(file_path) as file:
                content = file.read()
                self.editor.setPlainText(content)

            # Set syntax highlighting based on file extension
            _, ext = os.path.splitext(file_path)
            self.editor.set_syntax_highlighting(ext)

            self.statusBar().showMessage(f"Opened: {file_path}", 5000)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open file:\n{str(e)}")

    def save_file(self):
        """Save the current content to a file."""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save File", "", "All Files (*);;Text Files (*.txt);;JSON Files (*.json);;YAML Files (*.yaml *.yml);;INI Files (*.ini);;CSV Files (*.csv)")
        if file_path:
            try:
                with open(file_path, "w") as file:
                    file.write(self.editor.toPlainText())
                self.statusBar().showMessage(f"Saved: {file_path}", 5000)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save file:\n{str(e)}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TextEditorWindow()
    window.show()
    sys.exit(app.exec_())
