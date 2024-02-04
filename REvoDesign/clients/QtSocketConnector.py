import base64
from functools import partial
import json
import pickle
import socket
import time
import traceback
from typing import Union
from pymol.Qt import QtWidgets
from PyQt5 import QtWebSockets, QtNetwork, QtCore
from REvoDesign.tools.logger import logging as logger
logging=logger.getChild(__name__)

from REvoDesign.common.MutantTree import MutantTree
from pymol import cmd

from REvoDesign.tools.customized_widgets import (
    refresh_tree_widget,
    refresh_window,
)


'''
helpful:
https://stackoverflow.com/questions/15092076/pyqt-and-websocket-client-listen-websocket-in-background
https://stackoverflow.com/questions/26270681/can-an-asyncio-event-loop-run-in-the-background-without-suspending-the-python-in
'''


class REvoDesignWebSocketServer:
    """
    Class for managing a WebSocket server in REvoDesign.

    Attributes:
    - clients: Dictionary to store connected clients.
    - waiting_room: Set to hold clients waiting for authentication.
    - server: WebSocket server object.
    - server_url: URL for the server (default: 'localhost').
    - port: Port number for the server (default: 7890).
    - is_running: Flag indicating if the server is running.

    Methods:
    - onAcceptError: Handles accept errors.
    - onNewConnection: Manages new client connections.
    - askUserAuthentication: Asks client for authentication.
    - processTextMessage: Processes incoming text messages from clients.
    - processBinaryMessage: Processes incoming binary messages from clients.
    - socketDisconnected: Handles client disconnection.
    - stop_server: Stops the WebSocket server.
    - authenticate_client: Authenticates clients based on a key.
    - broadcast_object: Broadcasts serialized objects to connected clients.
    - serialize_object: Serializes objects for broadcasting.
    - encode_object: Encodes objects for serialization.
    - setup_ws_server: Sets up the WebSocket server with specified settings.
    - check_broadcast_interval: Checks the broadcast interval.
    - check_broadcast_enabled_flag: Checks if broadcast is enabled.
    - broadcast_view: Broadcasts view updates to clients.
    - is_port_available: Checks if a port is available for use.
    """

    def __init__(self):
        super().__init__()
        self.clients: dict[dict, None] = {}
        self.waiting_room = set()
        self.server = None  # Initialize server as None
        self.server_url = 'localhost'
        self.port = 7890
        self.is_running = False

        self.use_authentication = False
        self.authentication_key = None
        self.view_broadcast_enabled = False
        self.view_broadcast_on_air = False
        self.view_broadcast_worker = None
        self.view_broadcast_interval = 0.1

        self.treeWidget_ws_peers = None

    def onAcceptError(self, accept_error):
        """
        Handles accept errors when setting up the server.

        Args:
        - accept_error: Error encountered during accept.

        Returns:
        None
        """
        logging.error(f"Accept Error: {accept_error}")

    def onNewConnection(self):
        """
        Manages new client connections.

        Returns:
        None
        """
        client_connection = self.server.nextPendingConnection()
        client_connection.textMessageReceived.connect(
            lambda message, client=client_connection: self.processTextMessage(
                client, message
            )
        )
        client_connection.binaryMessageReceived.connect(
            lambda message, client=client_connection: self.processBinaryMessage(
                client, message
            )
        )
        client_connection.disconnected.connect(
            lambda client=client_connection: self.socketDisconnected(client)
        )

    def askUserAuthentication(self, client):
        """
        Asks the client for authentication.

        Args:
        - client: Client connection object.

        Returns:
        None
        """
        if self.is_logged_in_client(client=client):
            logging.warning(
                f'Client {client} has already joined in chat room.'
            )
            return

        if client not in self.waiting_room:
            logging.warning(f'Client {client} joins waiting room')
            self.waiting_room.add(client)

        logging.info(f'Asking {client} for authentication...')
        client.sendTextMessage('Require key')

        return

    def is_logged_in_client(self, client) -> bool:
        return any([_client == client for _client in self.current_clients()])

    def get_client_uuid(self, client):
        assert self.is_logged_in_client(client=client)
        _ = [
            uuid
            for uuid in self.clients.keys()
            if self.clients[uuid]['client'] == client
        ]
        return _[0]

    def current_clients(self) -> list:
        return [
            _client_info['client']
            for uuid, _client_info in self.clients.items()
        ]

    def refresh_user_tree(self) -> dict[dict]:
        from REvoDesign.tools.system_tools import get_client_info

        user_tree = {
            uuid: {k: v for k, v in data.items() if k != 'client'}
            for uuid, data in self.clients.items()
        }
        user_tree['Host'] = get_client_info()
        return user_tree

    def processTextMessage(self, client, message):
        """
        Processes incoming text messages from clients.

        Args:
        - client: Client connection object.
        - message: Incoming text message.

        Returns:
        None
        """
        logging.info(f">>> {message}")

        # a new client who has not joined yet
        if client not in self.waiting_room and not self.is_logged_in_client(
            client=client
        ):
            # by asking the authentication, this client will be added to the waiting room
            self.askUserAuthentication(client)
            return
        try:
            # try to load message, treating as a json-loadable string
            data: dict = json.loads(message)
        except:
            # if json fails to load it, we treat it as a normal text
            data = message
            logging.info(
                f'>>> {self.clients[self.get_client_uuid(client=client)]["user"] if self.is_logged_in_client(client=client) else client}: {message}'
            )
            return

        if client in self.waiting_room:
            from REvoDesign.tools.system_tools import OS_INFO
            from REvoDesign.tools.client_tools import UUIDGenerator

            if not self.use_authentication or not self.authentication_key:
                authenticated = True
            elif self.use_authentication and 'auth_key' in data:
                authenticated = self.authenticate_client(data['auth_key'])
            else:
                authenticated = False

            if not authenticated:
                logging.info(f"Authentication failed for client:{client}")
                client.sendTextMessage(
                    f'Key authentication is failed. {data["user"]} is rejected.'
                )
                client.close()
            else:
                uuid = UUIDGenerator().generate_uuid()

                joined_time_stamp = time.time()
                joined_time_str = time.strftime(
                    '%Y-%m-%d %H:%M:%S', time.localtime(joined_time_stamp)
                )

                data['joined_time_stamp'] = joined_time_stamp
                data['joined_time'] = joined_time_str
                data['client'] = client

                data.pop('auth_key')
                self.clients[uuid] = data
                logging.info(
                    f'Client  {data["user"]} from {data["node"]} is join.'
                )
                client.sendTextMessage(
                    f'Key authentication is successful.\nWellcome to {OS_INFO.node}, {data["user"]}.'
                )
                self._broadcast_object(
                    obj=uuid, data_type='UUID', client=client
                )
            # once the authentcation finished, the client should leave waiting room
            self.waiting_room.remove(client)

            logging.debug(self.clients)
            user_tree = self.refresh_user_tree()
            self._broadcast_object(obj=user_tree, data_type='UserTree')
            refresh_tree_widget(
                user_tree=user_tree,
                treeWidget_ws_peers=self.treeWidget_ws_peers,
            )

            return

        if client in self.current_clients():
            pass

    def processBinaryMessage(self, client, message):
        """
        Processes incoming binary messages from clients.

        Args:
        - client: Client connection object.
        - message: Incoming binary message.

        Returns:
        None
        """
        logging.info("Binary Message:", message)
        if client:
            client.sendBinaryMessage(message)

    def socketDisconnected(self, client):
        """
        Handles client disconnection.

        Args:
        - client: Client connection object.

        Returns:
        None
        """
        logging.info("Socket Disconnected")
        if client in self.current_clients():
            uuid = self.get_client_uuid(client=client)
            self.clients.pop(uuid)
            client.deleteLater()

        user_tree = self.refresh_user_tree()
        self._broadcast_object(obj=user_tree, data_type='UserTree')
        refresh_tree_widget(
            user_tree=user_tree, treeWidget_ws_peers=self.treeWidget_ws_peers
        )

    def stop_server(self):
        """
        Stops the WebSocket server and closes client connections.

        Returns:
        None
        """
        logging.info("Stopping Server")
        for client in self.current_clients():
            uuid = self.get_client_uuid(client=client)
            self.clients.pop(uuid)
            client.close()
        if self.server:
            self.server.close()
            self.server = None

        refresh_tree_widget(
            user_tree={}, treeWidget_ws_peers=self.treeWidget_ws_peers
        )

        self.is_running = False

    def authenticate_client(self, key):
        """
        Authenticates clients based on a provided key.

        Args:
        - key: Authentication key.

        Returns:
        bool: True if the key matches, False otherwise.
        """
        return key == self.authentication_key

    def _broadcast_object(self, obj, data_type: str, client=None):
        """
        Broadcasts serialized objects to connected clients.

        Args:
        - obj: Object to be serialized and broadcasted.
        - data_type: Type of the data.

        Returns:
        None
        """
        serialized_obj = self.serialize_object(obj, data_type)
        serialized_json = json.dumps(serialized_obj)

        if client:
            client.sendTextMessage(serialized_json)
            return

        for client in self.current_clients():
            client.sendTextMessage(serialized_json)

    async def broadcast_object(self, obj, data_type):
        """
        Broadcasts serialized objects to connected clients.

        Args:
        - obj: Object to be serialized and broadcasted.
        - data_type: Type of the data.

        Returns:
        None
        """
        self._broadcast_object(obj=obj, data_type=data_type)

    def serialize_object(self, obj, data_type: str):
        """
        Serializes objects for broadcasting.

        Args:
        - obj: Object to be serialized.
        - data_type: Type of the data.

        Returns:
        dict: Serialized object data.
        """
        serialized_data = {
            'data_type': data_type,
            'data': self.encode_object(obj),
        }
        return serialized_data

    def encode_object(self, obj):
        """
        Encodes objects for serialization.

        Args:
        - obj: Object to be encoded.

        Returns:
        str: Encoded object data.
        """
        pickled_obj = pickle.dumps(obj)
        return base64.b64encode(pickled_obj).decode()

    def setup_ws_server(
        self,
        checkBox_ws_duplex_mode,
        spinBox_ws_server_port,
        checkBox_ws_server_use_key,
        lineEdit_ws_server_key,
        checkBox_ws_broadcast_view,
        doubleSpinBox_ws_view_broadcast_interval,
        treeWidget_ws_peers,
    ):
        """
        Sets up the WebSocket server with specified settings.

        Args:
        (Arguments from previous implementation remain unchanged)

        Returns:
        None
        """
        from REvoDesign.tools.system_tools import OS_INFO

        self.use_authentication = checkBox_ws_server_use_key.isChecked()
        self.authentication_key = lineEdit_ws_server_key.text()
        if self.use_authentication and not self.authentication_key:
            raise ValueError('Key for authentication is empty!')

        requested_port = spinBox_ws_server_port.value()

        if not requested_port:
            raise ValueError(f'Port {requested_port} is not valid')

        if not self.is_port_available(requested_port):
            raise ValueError(
                f'Port {requested_port} is already in use. Please choose another port.'
            )

        self.port = requested_port

        self.do_broadcast_view = checkBox_ws_broadcast_view.isChecked()
        self.view_broadcast_interval = (
            doubleSpinBox_ws_view_broadcast_interval.value()
        )
        logging.info(
            f'Server is reconfigured! \n ' f'Key: {self.authentication_key}\n'
        )

        if not self.server:
            self.server = QtWebSockets.QWebSocketServer(
                OS_INFO.node, QtWebSockets.QWebSocketServer.NonSecureMode
            )

            if self.server.listen(QtNetwork.QHostAddress.Any, self.port):
                logging.info(
                    f'Listening: {self.server.serverAddress().toString()}:{str(self.server.serverPort())}'
                )
                self.is_running = True
            else:
                logging.error('Error: Unable to start the server.')
                self.is_running = False

            self.server.acceptError.connect(self.onAcceptError)
            self.server.newConnection.connect(self.onNewConnection)

        self.treeWidget_ws_peers = treeWidget_ws_peers

    def check_broadcast_interval(self) -> float:
        """
        Checks the broadcast interval.

        Returns:
        float: Broadcast interval value.
        """
        return self.view_broadcast_interval

    def check_broadcast_enabled_flag(self) -> bool:
        """
        Checks if broadcast is enabled.

        Returns:
        bool: True if broadcast is enabled, False otherwise.
        """
        return self.view_broadcast_enabled == True

    def broadcast_view(self):
        """
        Broadcasts view updates to clients.

        Returns:
        None
        """
        last_view = cmd.get_view()
        while True:
            for t in range(int(self.check_broadcast_interval() // 0.001)):
                time.sleep(0.001)
                refresh_window()

            view_data = cmd.get_view()
            if view_data == last_view:
                continue
            if not self.check_broadcast_enabled_flag():
                return

            serialized_obj = self.serialize_object(
                obj=view_data, data_type='ViewUpdate'
            )
            serialized_json = json.dumps(serialized_obj)
            last_view = view_data

            for client in self.current_clients():
                client.sendTextMessage(serialized_json)

    def is_port_available(self, port):
        """
        Check if the specified port is available for use.

        Args:
        port (int): The port number to check.

        Returns:
        bool: True if the port is available, False otherwise.
        """
        sock = QtNetwork.QTcpSocket()
        sock.bind(QtNetwork.QHostAddress.LocalHost, port)
        can_listen = sock.waitForConnected(
            500
        )  # Wait for 0.5 seconds to check connection
        sock.disconnectFromHost()
        return not can_listen


class REvoDesignWebSocketClient:
    def __init__(self):
        self.server_url = 'localhost'
        self.server_port = 7890
        self.authentication_key = None
        self.receive_view_broadcast = False
        self.receive_mutagenesis_broadcast = True
        self.design_molecule = ''
        self.design_chain_id = ''
        self.design_sequence = ''
        # Other initializations...
        self.cmap = 'bwr_r'
        self.nproc = 2

        self.uuid = ''
        self.connected = False
        self.client = None
        self.progress_bar = None
        self.treeWidget_ws_peers = None

    def setup_ws_client(
        self,
        lineEdit_ws_server_url_to_connect,
        spinBox_ws_server_port_to_connect,
        lineEdit_ws_server_key_to_connect,
        checkBox_ws_receive_mutagenesis_broadcast,
        checkBox_ws_receive_view_broadcast,
        treeWidget_ws_peers,
    ):
        if not self.design_molecule or not self.design_chain_id:
            raise ValueError('Invalid design molecule/chain ID!')

        self.server_url = lineEdit_ws_server_url_to_connect.text()

        server_port = spinBox_ws_server_port_to_connect.value()
        if not server_port:
            raise ValueError(f'Invalid server port {server_port}')
        self.server_port = server_port

        if not self.server_url or not self.server_port:
            raise ValueError('Invalid server configurations!')

        self.authentication_key = lineEdit_ws_server_key_to_connect.text()
        self.receive_mutagenesis_broadcast = (
            checkBox_ws_receive_mutagenesis_broadcast.isChecked()
        )
        self.receive_view_broadcast = (
            checkBox_ws_receive_view_broadcast.isChecked()
        )

        self.treeWidget_ws_peers = treeWidget_ws_peers

        logging.info(
            'Setting up client is done. Preparing to connect to the server.'
        )

    def connect_to_server(self):
        if not self.check_server_reachable():
            logging.error("Server unreachable or network issue.")
            return

        self.connected = True
        server_uri = f"ws://{self.server_url}:{self.server_port}"
        logging.info(f'Connecting to server: {server_uri}')
        try:
            self.client = QtWebSockets.QWebSocket(
                "", QtWebSockets.QWebSocketProtocol.Version13, None
            )
            self.client.error.connect(self.error)
            self.client.open(QtCore.QUrl(server_uri))
            self.client.connected.connect(
                partial(self.client.sendTextMessage, 'hello, server.')
            )
            self.client.textMessageReceived.connect(self.process_message)
            self.client.disconnected.connect(self.close_connection)

            logging.info('Connection established.')

        except Exception:
            logging.error("Unexpected error during connection:")
            traceback.print_exc()
            self.connected = False

    def close_connection(self):
        if not self.connected:
            logging.warning(
                'Client is not connected to any server. Doing nothing.'
            )
            return

        try:
            self.client.close()
            self.connected = False
            refresh_tree_widget(
                user_tree={}, treeWidget_ws_peers=self.treeWidget_ws_peers
            )

        except:
            traceback.print_exc()
            logging.error('Client disconnection failed.')

    def check_server_reachable(self):
        try:
            # Attempt a socket connection to the server
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(3)  # Set a timeout for the connection attempt
                s.connect((self.server_url, self.server_port))
            return True
        except socket.error as e:
            logging.error(f"Socket error: {e}")
            return False

    def authenticate_client(self):
        import json

        from REvoDesign.tools.system_tools import get_client_info

        greeting_message = get_client_info()

        if self.authentication_key:
            greeting_message['auth_key'] = self.authentication_key

        logging.info(f'Authentication is sent: {greeting_message}')
        self.client.sendTextMessage(json.dumps(greeting_message))

    def process_message(self, message):
        try:
            # try to load message, treating as a json-loadable string
            data = json.loads(message)
        except:
            data = message

        # process data if it is a text message
        if type(data) is str:
            logging.info(f'>>>  {data}')
            if message == 'Require key':
                self.authenticate_client()

            return

        # discard broken data objects
        if not 'data' in data or not 'data_type' in data:
            logging.warning('Uncomplete data object is discarded.')
            return

        from REvoDesign.tools.utils import run_worker_thread_with_progress

        deserialized_object = self.deserialize_object(
            data['data'], data['data_type']
        )

        # process Non-empty MutantTree
        if (
            data['data_type'] == 'MutantTree'
            and deserialized_object
            and not deserialized_object.empty
        ):
            from REvoDesign.tools.mutant_tools import existed_mutant_tree

            received_mutant_tree = deserialized_object.__deepcopy__()
            diff_mutant_tree = received_mutant_tree.diff_tree_from(
                existed_mutant_tree(
                    sequences={self.design_chain_id: self.design_sequence}
                )
            )
            if self.receive_mutagenesis_broadcast:
                logging.info(
                    'Building Mutagenesis from differential mutant tree: \n '
                    f'{len(diff_mutant_tree.all_mutant_branch_ids)} branches, {len(diff_mutant_tree.all_mutant_ids)} mutants'
                )

                run_worker_thread_with_progress(
                    worker_function=self.mutagenesis_from_mutant_tree,
                    mutant_tree=diff_mutant_tree,
                    progress_bar=self.progress_bar,
                )
            return

        # process ViewUpdates
        if (
            data['data_type'] == 'ViewUpdate'
            and type(deserialized_object) == tuple
        ):
            if not self.receive_view_broadcast:
                logging.warning(f'View update is disabled.')
                return

            # logging.debug('update pymol view')
            cmd.set_view(deserialized_object)
            return

        if (
            data['data_type'] == 'UserTree'
            and type(deserialized_object) == dict
        ):
            refresh_tree_widget(
                user_tree=deserialized_object,
                treeWidget_ws_peers=self.treeWidget_ws_peers,
            )
            return

        if data['data_type'] == 'UUID' and type(deserialized_object) == str:
            logging.info(f'Get a new UUID: {deserialized_object}')
            self.uuid = deserialized_object
            return

        # process more data objects ....

        logging.warning(
            f'Unknow data in type {data["data_type"]}: {deserialized_object} (type {type(deserialized_object)})'
        )
        return

    def deserialize_object(
        self, serialized_data, data_type
    ) -> Union[MutantTree, tuple, None, str, dict]:
        if data_type:
            decoded_data = base64.b64decode(serialized_data)
            return pickle.loads(decoded_data)

        # process more data objects ....

        else:
            # Handle unrecognized data types or return None
            return None

    def mutagenesis_from_mutant_tree(self, mutant_tree: MutantTree):
        from REvoDesign.tools.mutant_tools import quick_mutagenesis

        quick_mutagenesis(
            mutant_tree=mutant_tree,
            molecule=self.design_molecule,
            chain_id=self.design_chain_id,
            sequence=self.design_sequence,
            cmap=self.cmap,
            nproc=self.nproc,
        )

    def error(self, error_code):
        logging.error(f"error code: {error_code}")
        logging.error(self.client.errorString())
