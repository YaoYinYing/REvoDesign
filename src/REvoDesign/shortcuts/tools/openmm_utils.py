'''
OpenMM Setup Server Control
'''
import webbrowser

import uvicorn

from REvoDesign.basic import ServerControlAbstract, ThirdPartyModuleAbstract
from REvoDesign.bootstrap.set_config import is_package_installed
from REvoDesign.driver.ui_driver import ConfigBus
from REvoDesign.tools.package_manager import (WorkerThread,
                                              run_worker_thread_with_progress)
from REvoDesign.tools.utils import require_installed


# TODO: OpenMM with espaloma/TorchMD
@require_installed
class OpenmmSetupServerControl(ThirdPartyModuleAbstract, ServerControlAbstract):
    # Module name
    name: str = 'openmmsetup'
    # Check if the module is installed
    installed: bool = is_package_installed(name)

    def singleton_init(self):
        """
        Initialize the singleton instance.

        This method initializes the server thread, running status, and server instance.
        """
        # Initialize the server thread as None
        self.server_thread: WorkerThread = None  # type: ignore # WorkerThread instance
        # Initialize the running status as False
        self.is_running = False
        # Initialize the server as None
        self.server: uvicorn.Server = None  # type: ignore # Uvicorn Server instance

    def open_url(self, url):

        # Run the browser opening operation in a separate thread with progress dialog
        run_worker_thread_with_progress(
            webbrowser.open, url
        )

        # Call the citation method
        self.cite()

    def start_server(self):
        """
        Start the OpenMMSetup server.

        This method extends the start_server method of the parent class, configures and starts the Uvicorn server in a separate thread, and attempts to open the server URL in the default browser.
        """
        '''
        Behavior of the server start action.
        '''
        # Create a ConfigBus instance to read configuration information
        bus = ConfigBus()

        # Get server host and port configuration
        host = bus.get_value('openmmsetup.host', str)
        port = bus.get_value('openmmsetup.port', int)

        # Construct the server access URL
        url = f'http://{host}:{port}'

        if self.is_running:
            print("Server is already running.")
            return self.open_url(url=url)

        # a modified main function from openmmsetup
        # Import WsgiToAsgi to convert the Flask app to ASGI
        from asgiref.wsgi import WsgiToAsgi  # Add this line
        # Import the Flask app from openmmsetup
        from openmmsetup.openmmsetup import app

        # Wrap the Flask app as ASGI
        asgi_app = WsgiToAsgi(app)

        # Configure the Uvicorn server
        config = uvicorn.Config(
            app=asgi_app,
            host=host,
            port=port,
            log_level="info",
        )
        # Initialize the Uvicorn server instance
        self.server = uvicorn.Server(config)

        # Start server in a WorkerThread
        self.server_thread = WorkerThread(func=self._run_server)
        # Connect the result signal of the server thread to the handling method
        self.server_thread.result_signal.connect(self._on_server_result)
        # Connect the finished signal of the server thread to the handling method
        self.server_thread.finished_signal.connect(self._on_server_finished)
        # Start the server thread
        self.server_thread.start()
        # Set the running status to True
        self.is_running = True

        # Print the server start information
        print(f"Server started in {url}")
        return self.open_url(url=url)

    __bibtex__ = {
        'OpenMM': """@article{doi:10.1021/acs.jpcb.3c06662,
author = {Eastman, Peter and Galvelis, Raimondas and Peláez, Raúl P. and Abreu, Charlles R. A. and Farr, Stephen E. and Gallicchio, Emilio and Gorenko, Anton and Henry, Michael M. and Hu, Frank and Huang, Jing and Krämer, Andreas and Michel, Julien and Mitchell, Joshua A. and Pande, Vijay S. and Rodrigues, João PGLM and Rodriguez-Guerra, Jaime and Simmonett, Andrew C. and Singh, Sukrit and Swails, Jason and Turner, Philip and Wang, Yuanqing and Zhang, Ivy and Chodera, John D. and De Fabritiis, Gianni and Markland, Thomas E.},
title = {OpenMM 8: Molecular Dynamics Simulation with Machine Learning Potentials},
journal = {The Journal of Physical Chemistry B},
volume = {128},
number = {1},
pages = {109-116},
year = {2024},
doi = {10.1021/acs.jpcb.3c06662},
    note ={PMID: 38154096},
URL = { https://doi.org/10.1021/acs.jpcb.3c06662 },
eprint = { https://doi.org/10.1021/acs.jpcb.3c06662 }
}"""
    }
