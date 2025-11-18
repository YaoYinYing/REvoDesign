from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl, QObject, pyqtSlot
import plotly.graph_objects as go

class PlotlyHandler(QObject):
    @pyqtSlot(str, int)
    def handle_plotly_click(self, point_name, index):
        print(f"Plotly point '{point_name}' clicked at index {index}!")
        # Perform actions in your Python app based on the click event

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.browser = QWebEngineView()
        self.setCentralWidget(self.browser)

        # Create a Plotly figure
        fig = go.Figure(data=go.Scatter(y=[1, 3, 2]))

        # Convert Plotly figure to HTML
        html_content = fig.to_html(include_plotlyjs='cdn')

        # Inject JavaScript to handle clicks and call Python
        js_injection = """
        <script>
            document.addEventListener('DOMContentLoaded', function() {
                var plotDiv = document.getElementsByClassName('js-plotly-plot')[0];
                if (plotDiv) {
                    plotDiv.on('plotly_click', function(data) {
                        if (data.points && data.points.length > 0) {
                            var point = data.points[0];
                            var pointName = point.data.name || 'Unnamed Point';
                            var pointIndex = point.pointIndex;
                            // Call the exposed Python method
                            if (window.plotlyHandler) {
                                window.plotlyHandler.handle_plotly_click(pointName, pointIndex);
                            }
                        }
                    });
                }
            });
        </script>
        """
        html_content = html_content.replace('</head>', js_injection + '</head>')


        # Load the HTML content into QWebEngineView
        self.browser.setHtml(html_content)

        # Expose Python object to JavaScript
        self.plotly_handler = PlotlyHandler()
        self.browser.page().profile().setPersistentCookiesPolicy(QWebEngineProfile.NoPersistentCookies) # Needed for setWebChannel to work reliably
        self.browser.page().setWebChannel(self.plotly_handler, "plotlyHandler") # Expose 'plotlyHandler' to JS


if __name__ == '__main__':
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec_()