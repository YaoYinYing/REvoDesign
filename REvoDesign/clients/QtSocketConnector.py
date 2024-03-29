import base64
from functools import partial
import json
import pickle
import socket
import time
import traceback
from types import MappingProxyType

import msgpack
from dataclasses import dataclass, field
from typing import (
    Any,
    Callable,
    Iterable,
    Literal,
    Mapping,
    TypeAlias,
    Union,
    Sequence,
)
from PyQt5 import QtWebSockets, QtNetwork, QtCore
from REvoDesign import ConfigBus, root_logger
from REvoDesign.application.ui_driver import SingletonAbstract
from REvoDesign.tools.utils import run_worker_thread_with_progress

logging = root_logger.getChild(__name__)

from REvoDesign.common.MutantTree import MutantTree
from pymol import cmd

from REvoDesign.tools.customized_widgets import refresh_tree_widget

import warnings
from REvoDesign import issues


'''
helpful:
https://stackoverflow.com/questions/15092076/pyqt-and-websocket-client-listen-websocket-in-background
https://stackoverflow.com/questions/26270681/can-an-asyncio-event-loop-run-in-the-background-without-suspending-the-python-in
'''


@dataclass
class Client:
    uuid: str
    client: QtWebSockets.QWebSocket
    client_info: dict
    crt: str = None


@dataclass
class MeetingRoom:
    host_id: str
    host: Client
    clients: dict[str, Client]

    def get_user_by_uuid(self, uuid: str):
        if self.empty:
            return None
        user = self.clients.get(uuid)
        if user:
            return user

    def does_user_exist(self, uuid: str) -> bool:
        return uuid in self.clients

    def let_user_join(self, uuid: str, user: Client):
        if uuid in self.clients:
            warnings.warn(
                issues.SocketUserAlreadyExists('user already joined.')
            )
            return
        self.clients[uuid] = user

    def get_user_uuid(self, client: QtWebSockets.QWebSocket):
        return [u for u, c in self.clients.items() if c.client == client][0]

    def kickout(self, uuid: str) -> Client:
        client = self.get_user_by_uuid(uuid=uuid)
        self.clients.pop(uuid)
        client.client.close()
        return

    @property
    def user_tree(self):
        return {
            uuid: {
                k: v for k, v in client.client_info.items() if k != 'client'
            }
            for uuid, client in self.clients.items()
        }

    @property
    def current_clients(self) -> list[QtWebSockets.QWebSocket]:
        return [client.client for uuid, client in self.clients.items()]

    def is_logged_in(self, client) -> bool:
        return client in self.current_clients

    @property
    def peer_table(self) -> dict[dict]:
        if self.empty:
            return {}

        from REvoDesign.tools.system_tools import CLIENT_INFO

        user_tree = self.user_tree
        user_tree['Host'] = CLIENT_INFO().__dict__
        return user_tree

    @property
    def empty(self) -> bool:
        return not bool(self.current_clients)


@dataclass(frozen=True)
class Broadcaster:
    supported_datatypes_mapping: Mapping = field(
        default_factory=lambda: MappingProxyType(
            {
                'MutantTree': MutantTree,
                'PyMOL_prompt': str,
                'PyMOL_selection': Iterable,
                'ViewUpdate': tuple,
                'ConfigItem': dict,
                'ClientInfo': dict,
                'Text': str,
                'Key': str,
                'RequireKey': str,
                "UserTree": dict,
                "UUID": str,
            }
        )
    )

    supported_datatypes: TypeAlias = Literal[
        'MutantTree',
        'PyMOL_prompt',
        'PyMOL_selection',
        'ViewUpdate',
        'ConfigItem',
        'ClientInfo',
        'Text',
        'RequireKey',
        "UserTree",
        "UUID",
    ]

    readble_type: tuple = tuple(
        [
            'MutantTree',
            'PyMOL_prompt',
            'ConfigItem',
            'ClientInfo',
            'Text',
            'RequireKey',
            "UUID",
        ]
    )

    @staticmethod
    def encode(obj):
        pickled_obj = pickle.dumps(obj)
        return base64.b64encode(pickled_obj).decode()

    @staticmethod
    def decode(serialized_data) -> Any:
        decoded_data = base64.b64decode(serialized_data)
        return pickle.loads(decoded_data)

    def compose_dict(
        self, obj: Any, datatype: supported_datatypes, final: bool = True
    ):
        if not datatype in self.supported_datatypes_mapping:
            raise issues.FobbidenDataTypeError(f'{datatype=} is not allowed.')
        return {'datatype': datatype, 'obj': self.encode(obj), 'final': final}

    @staticmethod
    def pack(msg_dict: dict[str, str]) -> bytes:
        return msgpack.packb(msg_dict, use_bin_type=True)

    @staticmethod
    def unpack(package: bytes) -> dict[str, str]:
        return msgpack.unpackb(package, raw=False)

    def digest_dict(
        self, unpacked_msg_dict: dict[str, str]
    ) -> tuple[supported_datatypes, Any]:
        datatype: self.supported_datatypes = unpacked_msg_dict.get('datatype')
        if not datatype:
            warnings.warn(
                issues.BadDataWarning(
                    f'bad data {datatype=} has been discarded'
                )
            )
            return None, None

        obj = self.decode(unpacked_msg_dict.get('obj'))
        expected_obj_type = self.supported_datatypes_mapping.get(datatype)
        if not isinstance(obj, expected_obj_type):
            warnings.warn(
                issues.BadDataWarning(
                    f'Bad data type mismatch: {datatype=}: {expected_obj_type=}'
                )
            )
            return None, None
        return (datatype, obj)

    def broadcast(
        self,
        meetingroom: MeetingRoom,
        obj_type: supported_datatypes = 'Text',
        obj: Any = None,
        final=True,
    ):
        if meetingroom.empty:
            warnings.warn(
                issues.SocketMeetingRoomIsEmpty(f'Empty meeting room.')
            )
            return
        msg_dict = self.compose_dict(obj=obj, datatype=obj_type, final=final)
        packed_msg = self.pack(msg_dict=msg_dict)

        for client in meetingroom.current_clients:
            client.sendBinaryMessage(packed_msg)

    def wisper(
        self,
        client: Union[Client, QtWebSockets.QWebSocket],
        obj_type: supported_datatypes = 'Text',
        obj: Any = None,
        final: bool = True,
    ):
        msg_dict = self.compose_dict(obj=obj, datatype=obj_type, final=final)
        packed_msg = self.pack(msg_dict=msg_dict)
        if isinstance(client, Client):
            c = client.client
        else:
            c = client

        c.sendBinaryMessage(packed_msg)

    def typing_check(self, msg_type, msg_content):
        expected_type = self.supported_datatypes_mapping.get(msg_type)
        pass_check = isinstance(msg_content, expected_type)

        logging.debug(f"Typing check: {expected_type=}: {pass_check=}")

        return expected_type and pass_check

    def received(self, packed_msg: bytes):
        unpacked_msg = self.unpack(packed_msg)
        (datatype, obj) = self.digest_dict(unpacked_msg_dict=unpacked_msg)
        if datatype:
            return (datatype, obj)
        else:
            warnings.warn(
                issues.BadDataWarning(
                    f'Bad data received with unexpected none datatype.'
                )
            )
            return None, None


class REvoDesignWebSocketServer(SingletonAbstract):
    """
    Class for managing a WebSocket server in REvoDesign.

    Attributes:
    - clients: Dictionary to store connected clients.
    - waiting_room: Set to hold clients waiting for authentication.
    - server: WebSocket server object.
    - server_url: URL for the server (default: 'localhost').
    - port: Port number for the server (default: 7890).


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
        # Check if the instance has already been initialized
        if not hasattr(self, 'initialized'):
            # If not, set the instance attributes

            self.bus: ConfigBus = ConfigBus()
            self.meetingroom: MeetingRoom = None
            self.waiting_room = set()

            self.server = None  # Initialize server as None
            self.server_url = self.bus.get_value(
                'ui.socket.server_url',
                converter=str,
                default_value='localhost',
            )
            self.port = self.bus.get_value(
                'ui.socket.server_port', converter=int, default_value=7890
            )

            self.use_authentication = self.bus.get_value(
                'ui.socket.use_key', converter=bool
            )
            self.authentication_key = self.bus.get_value(
                'ui.socket.input.key', converter=str
            )

            self.bc_worker: Broadcaster = Broadcaster()
            self.view_broadcast_enabled = False
            self.view_broadcast_on_air = False
            self.view_broadcast_worker = None
            self.view_broadcast_interval = self.bus.get_value(
                'ui.socket.broadcast.interval',
                converter=float,
                default_value=0.1,
            )

            self.treeWidget_ws_peers = self.bus.ui.treeWidget_ws_peers

            # Mark the instance as initialized to prevent reinitialization
            self.initialized = True

    @classmethod
    def initialize(cls):
        if not cls._instance:
            cls()
        else:
            ...

    @property
    def is_running(self):
        return self.server is not None and self.server.isListening()

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

        logging.info(f'Asking {client} for authentication...')
        self.bc_worker.wisper(
            obj_type='RequireKey', obj='Key please.', client=client
        )

        return

    def get_client_uuid(self, client):
        assert self.meetingroom.is_logged_in(client=client)
        return self.meetingroom.get_user_uuid(client)

    def processTextMessage(
        self, client: QtWebSockets.QWebSocket, message: Union[str, Any]
    ):
        """
        Processes incoming text messages from clients.

        Args:
        - client: Client connection object.
        - message: Incoming text message.

        Returns:
        None
        """

    def processBinaryMessage(self, client, message: QtCore.QByteArray):
        """
        Processes incoming binary messages from clients.

        Args:
        - client: Client connection object.
        - message: Incoming binary message.

        Returns:
        None
        """
        message: bytes = message.data()
        # logging.info("Binary Message:", message)
        msg_type, msg_content = self.bc_worker.received(packed_msg=message)

        if not msg_type:
            return

        if not self.bc_worker.typing_check(
            msg_type=msg_type, msg_content=msg_content
        ):
            warnings.warn(
                issues.BadDataWarning(
                    f'Bad data from socket discarded: {msg_type=},{msg_content=}'
                )
            )
            return

        username, node, user_id = self.client_name_and_node(client=client)

        # printout readable msgs
        if msg_type in Broadcaster.readble_type:
            logging.info(
                f'>>> {username}@{node}({user_id}): [{msg_type}] {msg_content}'
            )

        # matching msg_type
        if msg_type == 'ClientInfo':
            assert isinstance(msg_content, dict)
            if client in self.meetingroom.current_clients:
                logging.warning(
                    f'Client {client} has already joined in chat room.'
                )
                self.bc_worker.wisper(
                    obj_type='Text',
                    obj='You are already joined.',
                    client=client,
                )
                return
            logging.info(f'Authenticating... {client}')
            self.bc_worker.wisper(
                obj_type='Text',
                obj='Authenticating...',
                client=client,
            )
            self.handleAuthentication(
                client,
                message=msg_content,
            )
            return

        if client not in self.meetingroom.current_clients:
            if client not in self.waiting_room:
                self.waiting_room.add(client)
                logging.warning(f'Client {client} joins waiting room')
            self.askUserAuthentication(client)
            return

        ...

    def client_name_and_node(self, client):
        if self.meetingroom.is_logged_in(client=client):
            user_id = self.meetingroom.get_user_uuid(client=client)
            user_info = self.meetingroom.get_user_by_uuid(user_id).client_info
            user = user_info.get('user')
            user_node = user_info.get('node')

        else:
            user_id = 'Unautherized'
            user = client.peerName()
            user_node = client.peerAddress()

        return user, user_node, user_id

    def handleAuthentication(
        self,
        client,
        message: dict,
    ):
        # a new client who has not joined yet

        username, node, user_id = self.client_name_and_node(client=client)

        if client not in self.meetingroom.current_clients:
            from REvoDesign.tools.system_tools import CLIENT_INFO
            from REvoDesign.tools.client_tools import UUIDGenerator

            if not self.use_authentication or not self.authentication_key:
                authenticated = True
            elif self.use_authentication and (
                user_key := message.get('auth_key')
            ):
                authenticated = user_key == self.authentication_key
            else:
                authenticated = False

            if not authenticated:
                logging.info(f"Authentication failed for client:{client}")
                self.bc_worker.wisper(
                    client=client,
                    obj=f'Key authentication is failed. {username} from {node} is rejected.',
                )
                client.close()

                self.waiting_room.remove(client)
                return

            uuid = UUIDGenerator().generate_uuid()

            joined_time_stamp = time.time()
            joined_time_str = time.strftime(
                '%Y-%m-%d %H:%M:%S', time.localtime(joined_time_stamp)
            )

            message['joined_time_stamp'] = joined_time_stamp
            message['joined_time'] = joined_time_str

            message.pop('auth_key')

            self.meetingroom.let_user_join(
                uuid=uuid,
                user=Client(uuid=uuid, client_info=message, client=client),
            )

            logging.info(
                f'Client {message["user"]} from {message["node"]} is join.'
            )

            self.bc_worker.wisper(
                client=client,
                obj=f'Key authentication is successful.\nWellcome to {CLIENT_INFO().node}, {message["user"]}.',
            )

            self.bc_worker.wisper(
                obj=uuid, obj_type='UUID', client=client, final=True
            )

            # once the authentcation finished, the client should leave waiting room
            self.waiting_room.remove(client)

            logging.debug(self.meetingroom)
            self.synchronize_usertable()

            return

        if client in self.meetingroom.current_clients:
            pass

    def synchronize_usertable(self):
        if self.meetingroom.empty:
            peer_table = {}
        else:
            peer_table = self.meetingroom.peer_table

        self.bc_worker.broadcast(
            self.meetingroom, obj=peer_table, obj_type='UserTree'
        )

        refresh_tree_widget(
            user_tree=peer_table, treeWidget_ws_peers=self.treeWidget_ws_peers
        )

    def socketDisconnected(self, client):
        """
        Handles client disconnection.

        Args:
        - client: Client connection object.

        Returns:
        None
        """
        logging.info("Socket Disconnected")

        if client in self.meetingroom.current_clients:
            uuid = self.get_client_uuid(client=client)
            self.meetingroom.kickout(uuid)
            client.deleteLater()

        self.synchronize_usertable()

    def stop_server(self):
        """
        Stops the WebSocket server and closes client connections.

        Returns:
        None
        """
        self.bc_worker.broadcast(
            self.meetingroom, obj='Host is shutting down, bye-bye.'
        )

        for client in self.meetingroom.current_clients:
            uuid = self.get_client_uuid(client=client)
            self.meetingroom.kickout(uuid)

        if self.server:
            self.server.close()
            self.server = None
            self.meetingroom = None

        self.synchronize_usertable()

    async def broadcast_object(self, obj, data_type):
        """
        Broadcasts serialized objects to connected clients.

        Args:
        - obj: Object to be serialized and broadcasted.
        - data_type: Type of the data.

        Returns:
        None
        """
        self.bc_worker.broadcast(
            meetingroom=self.meetingroom, obj=obj, obj_type=data_type
        )

    def setup_ws_server(self):
        from REvoDesign.tools.system_tools import CLIENT_INFO

        self.use_authentication = self.bus.get_value('ui.socket.use_key')
        self.authentication_key = self.bus.get_value('ui.socket.input.key')
        if self.use_authentication and not self.authentication_key:
            raise ValueError('Key for authentication is empty!')

        requested_port = self.bus.get_value('ui.socket.server_port', int)

        if not requested_port:
            raise ValueError(f'Port {requested_port} is not valid')

        if not self.is_port_available(requested_port):
            raise ValueError(
                f'Port {requested_port} is already in use. Please choose another port.'
            )

        self.port = requested_port

        self.do_broadcast_view = self.bus.get_value('ui.socket.broadcast.view')
        self.view_broadcast_interval = self.bus.get_value(
            'ui.socket.broadcast.interval', float
        )
        logging.info(
            f'Server is reconfigured! \n ' f'Key: {self.authentication_key}\n'
        )

        if not self.server:
            self.server = QtWebSockets.QWebSocketServer(
                CLIENT_INFO.node, QtWebSockets.QWebSocketServer.NonSecureMode
            )

            if not self.server.listen(QtNetwork.QHostAddress.Any, self.port):
                self.meetingroom = None
                raise issues.SocketError('Unable to start the server.')

            logging.info(
                f'Listening: {self.server.serverAddress().toString()}:{str(self.server.serverPort())}'
            )

            self.meetingroom = MeetingRoom(
                host_id=CLIENT_INFO().node, host=self.server, clients={}
            )

            self.server.acceptError.connect(self.onAcceptError)
            self.server.newConnection.connect(self.onNewConnection)

        self.treeWidget_ws_peers = self.bus.ui.treeWidget_ws_peers

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
        return self.view_broadcast_enabled

    def broadcast_view(self):
        """
        Broadcasts view updates to clients.

        Returns:
        None
        """
        last_view = cmd.get_view()
        while True:
            run_worker_thread_with_progress(
                time.sleep,
                None,
                self.check_broadcast_interval(),
            )

            view_data = cmd.get_view()
            if view_data == last_view:
                # external sleep if view is not changed.
                # run_worker_thread_with_progress(time.sleep, None, 1)
                continue
            if not self.check_broadcast_enabled_flag():
                return

            self.bc_worker.broadcast(
                self.meetingroom, obj_type='ViewUpdate', obj=view_data
            )

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


class REvoDesignWebSocketClient(SingletonAbstract):
    @classmethod
    def initialize(cls):
        if not cls._instance:
            cls()
        else:
            ...

    def __init__(self, ui=None):
        # Check if the instance has already been initialized
        if not hasattr(self, 'initialized'):
            # If not, set the instance attributes
            self.bus: ConfigBus = ConfigBus()
            self.server_url = 'localhost'
            self.server_port = 7890

            self.bc_worker = Broadcaster()
            self.authentication_key = None
            self.receive_view_broadcast = False
            self.receive_mutagenesis_broadcast = True

            self.uuid = ''
            self.connected = False
            self.client = None
            self.treeWidget_ws_peers = None

            self.sidechain_solver = None
            # Mark the instance as initialized to prevent reinitialization
            self.initialized = True

    def setup_ws_client(self):
        self.server_url = self.bus.get_value('ui.socket.server_url')

        server_port = self.bus.get_value('ui.socket.server_port', int)
        if not server_port:
            raise ValueError(f'Invalid server port {server_port}')
        self.server_port = server_port

        if not self.server_url or not self.server_port:
            raise ValueError('Invalid server configurations!')

        self.authentication_key = self.bus.get_value('ui.socket.input.key')
        self.receive_mutagenesis_broadcast = self.bus.get_value(
            'ui.socket.receive.mutagenesis'
        )
        self.receive_view_broadcast = self.bus.get_value(
            'ui.socket.receive.view'
        )

        self.treeWidget_ws_peers = self.bus.ui.treeWidget_ws_peers

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
                partial(
                    self.bc_worker.wisper,
                    client=self.client,
                    obj='hello, server.',
                )
            )
            self.client.textMessageReceived.connect(self.handleTextMessage)
            self.client.binaryMessageReceived.connect(self.handleBinaryMessage)
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
            self.bc_worker.wisper(self.client, obj='Leaving, bye-bye.')
            self.client.close()
            self.connected = False
            refresh_tree_widget(
                user_tree={}, treeWidget_ws_peers=self.treeWidget_ws_peers
            )

        except Exception:
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
        from REvoDesign.tools.system_tools import CLIENT_INFO

        greeting_message = CLIENT_INFO().__dict__

        if self.authentication_key:
            greeting_message['auth_key'] = self.authentication_key

        logging.info(f'Authentication is sent: {greeting_message}')
        self.bc_worker.wisper(
            self.client, obj_type='ClientInfo', obj=greeting_message
        )

    def handleMutantTree(self, mutant_tree: MutantTree):
        if mutant_tree.empty:
            return
        from REvoDesign.tools.mutant_tools import existed_mutant_tree

        received_mutant_tree = mutant_tree.__deepcopy__
        diff_mutant_tree = received_mutant_tree.diff_tree_from(
            existed_mutant_tree(
                sequences=self.bus.get_value('designable_sequences')
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
            )

    def handleViewUpdate(self, view):
        if not self.receive_view_broadcast:
            logging.warning(f'View update is disabled.')
            return

        # logging.debug('update pymol view')
        cmd.set_view(view)
        return

    def handleTextMessage(self, message):
        logging.info(f'>>> Host: {message}')

    def handleBinaryMessage(self, message: QtCore.QByteArray):
        msg_bytes: bytes = message.data()
        msg_type, msg_content = self.bc_worker.received(packed_msg=msg_bytes)

        if not self.bc_worker.typing_check(
            msg_type=msg_type, msg_content=msg_content
        ):
            warnings.warn(
                issues.BadDataWarning(
                    f'Bad data from socket discarded: {msg_type=},{msg_content=}'
                )
            )
            return

        if msg_type in Broadcaster.readble_type:
            logging.info(f'>>> Host: [{msg_type}] {msg_content}')

        if msg_type == 'Text':
            return

        if msg_type == 'RequireKey':
            self.authenticate_client()
            return

        if msg_type == 'MutantTree':
            self.handleMutantTree(mutant_tree=msg_content)
            return
        if msg_type == 'ViewUpdate':
            self.handleViewUpdate(view=msg_content)
            return

        if msg_type == 'UserTree':
            refresh_tree_widget(
                user_tree=msg_content,
                treeWidget_ws_peers=self.treeWidget_ws_peers,
            )
            return

        if msg_type == 'UUID':
            logging.info(f'Get a new UUID: {msg_content}')
            self.uuid = msg_content
            return

        ...

        logging.warning(f'Unknow data in type {msg_type}: {msg_content}')
        return

        # process more data objects ....

    def get_sidechain_solver(self):
        from REvoDesign.sidechain_solver import (
            SidechainSolver,
        )

        return SidechainSolver().setup()

    def mutagenesis_from_mutant_tree(self, mutant_tree: MutantTree):
        from REvoDesign.tools.mutant_tools import quick_mutagenesis

        if not self.sidechain_solver:
            logging.warning(
                "No sidechain_solver is configured. Instantializing..."
            )
            self.sidechain_solver = self.get_sidechain_solver()

        self.sidechain_solver = self.sidechain_solver.refresh()

        quick_mutagenesis(
            mutant_tree=mutant_tree,
            sidechain_solver=self.sidechain_solver,
        )

    def error(self, error_code):
        logging.error(f"error code: {error_code}")
        logging.error(self.client.errorString())
