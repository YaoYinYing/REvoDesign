import asyncio
import base64
from functools import partial
import json
import pickle
import socket
import time
import traceback
from typing import Union
from PyQt5 import QtWebSockets, QtNetwork, QtCore
from absl import logging
from REvoDesign.common.MutantTree import MutantTree
from pymol import cmd

from REvoDesign.tools.customized_widgets import WorkerThread, refresh_window


'''
helpful:
https://stackoverflow.com/questions/15092076/pyqt-and-websocket-client-listen-websocket-in-background
https://stackoverflow.com/questions/26270681/can-an-asyncio-event-loop-run-in-the-background-without-suspending-the-python-in
'''


class REvoDesignWebSocketServer:
    def __init__(self):
        super().__init__()
        self.clients = {}
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

    def onAcceptError(self, accept_error):
        logging.error(f"Accept Error: {accept_error}")

    def onNewConnection(self):
        client_connection = self.server.nextPendingConnection()
        # client_connection.connected.connect(lambda client=client_connection: self.askUserAuthentication(client))
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
        # self.clients[client_connection] = {}

    def askUserAuthentication(self, client):
        if client in self.clients:
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

    def processTextMessage(self, client, message):
        logging.info(f">>> {message}")

        # a new client who has not joined yet
        if client not in self.waiting_room and client not in self.clients:
            # by asking the authentication, this client will be added to the waiting room
            self.askUserAuthentication(client)
            return
        try:
            # try to load message, treating as a json-loadable string
            data = json.loads(message)
        except:
            # if json fails to load it, we treat it as a normal text
            data = message
            logging.info(
                f'>>> {self.clients[client]["user"] if client in self.clients else client}: {message}'
            )
            return

        if client in self.waiting_room:
            from REvoDesign.tools.system_tools import OS_INFO

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
                self.clients[client] = data
                logging.info(
                    f'Client  {data["user"]} from {data["node"]} is join.'
                )
                client.sendTextMessage(
                    f'Key authentication is successful. Wellcome to {OS_INFO.node}, {data["user"]}.'
                )
            # once the authentcation finished, the client should be removed from waiting room
            self.waiting_room.remove(client)
            return

        if client in self.clients:
            pass

    def processBinaryMessage(self, client, message):
        logging.info("Binary Message:", message)
        if client:
            client.sendBinaryMessage(message)

    def socketDisconnected(self, client):
        logging.info("Socket Disconnected")
        if client in self.clients:
            del self.clients[client]
            client.deleteLater()

    def stop_server(self):
        logging.info("Stopping Server")
        for client in list(self.clients.keys()):
            client.close()
        if self.server:
            self.server.close()
            self.server = None
        self.is_running = False

    def authenticate_client(self, key):
        return key == self.authentication_key

    async def broadcast_object(self, obj, data_type):
        serialized_obj = self.serialize_object(obj, data_type)
        serialized_json = json.dumps(serialized_obj)

        for client in self.clients.keys():
            client.sendTextMessage(serialized_json)

    def serialize_object(self, obj, data_type: str):
        serialized_data = {
            'data_type': data_type,
            'data': self.encode_object(obj),
        }
        return serialized_data

    def encode_object(self, obj):
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
    ):
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

    def check_broadcast_interval(self) -> float:
        return self.view_broadcast_interval

    def check_broadcast_enabled_flag(self) -> bool:
        return self.view_broadcast_enabled == True

    def broadcast_view(self):
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

            for client in self.clients.keys():
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

        self.connected = False
        self.client = None
        self.progress_bar = None

    def setup_ws_client(
        self,
        lineEdit_ws_server_url_to_connect,
        spinBox_ws_server_port_to_connect,
        lineEdit_ws_server_key_to_connect,
        checkBox_ws_receive_mutagenesis_broadcast,
        checkBox_ws_receive_view_broadcast,
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

        if 'data' in data and 'data_type' in data:
            from REvoDesign.tools.utils import run_worker_thread_with_progress

            obj = self.deserialize_object(data['data'], data['data_type'])
            # Use the received 'obj' and 'data_type' as needed
            if data['data_type'] == 'MutantTree' and obj and not obj.empty:
                from REvoDesign.tools.mutant_tools import existed_mutant_tree

                received_mutant_tree = obj.__deepcopy__()
                diff_mutant_tree = received_mutant_tree.diff_tree_from(
                    existed_mutant_tree(sequence=self.design_sequence)
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
            if data['data_type'] == 'ViewUpdate' and type(obj) == tuple:
                if not self.receive_view_broadcast:
                    logging.warning(f'View update is disabled.')
                    return

                # logging.debug('update pymol view')
                cmd.set_view(obj)
                return

            logging.warning(
                f'Unknow data in type {data["data_type"]}: {obj} (type {type(obj)})'
            )

    def deserialize_object(
        self, serialized_data, data_type
    ) -> Union[MutantTree, tuple, None]:
        if data_type == 'MutantTree' or data_type == 'ViewUpdate':
            decoded_data = base64.b64decode(serialized_data)
            return pickle.loads(decoded_data)

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
