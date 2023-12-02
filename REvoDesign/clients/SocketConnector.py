import asyncio
import ssl
from typing import Union
import websockets

import socket
import json
import base64
import pickle
import traceback
from absl import logging

from REvoDesign.common.MutantTree import MutantTree


class REvoDesignWebSocketServer:
    def __init__(self, port=7890):
        self.host = ''
        self.port = port
        self.use_authentication = False
        self.authentication_key = None
        self.do_broadcast_view = False
        # store client with its greeting message
        self.clients: dict[websockets.WebSocketClientProtocol : dict] = dict()
        self.wait_room = set()
        self.is_running = False  # Flag to indicate server status
        self.server: Union[None, websockets.WebSocketServer] = None

        # Other initialization

    def is_port_available(self, port):
        """
        Check if the specified port is available for use.

        Args:
        port (int): The port number to check.

        Returns:
        bool: True if the port is available, False otherwise.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind(('localhost', port))
            return True
        except OSError:
            return False
        finally:
            sock.close()

    def setup_ws_server(
        self,
        checkBox_ws_duplex_mode,
        spinBox_ws_server_port,
        checkBox_ws_server_use_key,
        lineEdit_ws_server_key,
        checkBox_ws_broadcast_view,
        doubleSpinBox_ws_view_broadcast_interval,
    ):
        self.deplex_mode = checkBox_ws_duplex_mode.isChecked()

        self.use_authentication = checkBox_ws_server_use_key.isChecked()
        self.authentication_key = lineEdit_ws_server_key.text()
        if self.use_authentication and not self.authentication_key:
            raise ValueError(f'Key for authentication is empty!')

        requested_port = spinBox_ws_server_port.value()

        if not requested_port:
            raise ValueError(f'Port {requested_port} not valid')
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

    async def start_server(self):
        from REvoDesign.tools.client_tools import generate_ssl_context

        self.is_running = True  # Set flag when server starts
        ssl_context = generate_ssl_context(
            role='server'
        )  # Generate SSL context
        
        logging.info('Server starting....')

        # Keep the server running indefinitely using the event loop's run_forever() method
        try:
            self.server = await websockets.serve(
                self.handler,
                self.host,
                self.port,
                #ssl=ssl_context,
            )

            await self.server.start_serving()
            await asyncio.sleep(0)  # yield control to the event loop

            logging.info(f'Server runs on {self.host}:{self.port}')

        except:
            traceback.print_exc()
            logging.error('Server initialization failed.')
            self.is_running = False

            # Perform any cleanup or shutdown operations here

    async def stop_server(self):
        # Close all WebSocket connections
        self.is_running = False  # Set flag when server stops
        logging.info('Server is stopped.')
        for client in self.clients.keys():
            await client.close()

        try:
            assert self.server is not None

            self.server.close()

            logging.warning('Server closed.')
        except:
            traceback.print_exc()
            logging.error('Server closing failed.')

        # Perform any additional cleanup or shutdown operations if needed
        # ...

        logging.info("Server shutting down...")

    async def handle_client_double_click(self, row_index):
        client_list = list(self.clients.keys())
        if row_index < len(client_list):
            selected_client = client_list[row_index]
            await self.kick_out_client(selected_client)

    async def kick_out_client(self, client):
        # Close the WebSocket connection of the selected client
        await client.close()
        # Update the client list if needed

    async def handler(self, client):
        self.wait_room.add(client)
        logging.warning(f'A new client has come: {client}')

        try:
            async for message in client:
                await self.process_message(client, message)
                
        except:
            traceback.print_exc()
        # finally:
        #     self.clients.pop(client)
        #     client.close()

    async def process_message(self, client, message):
        if type(message) == dict:
            logging.info(f'>>>{self.clients[client]["user"]}: {message}')
            return
        data = json.loads(message)

        if (
            client in self.wait_room
            and self.use_authentication
            and 'auth_key' in data
        ):
            authenticated = self.authenticate_client(data['auth_key'])

            if not authenticated:
                # kick it out after a failed try.
                self.wait_room.remove(client)
                if client in self.clients:
                    self.clients.pop(client)
                logging.info(
                    f'User {data["user"]} from {data["node"]} is reject due to failed authentication.'
                )
                return  # Unauthorized client
            else:
                
                self.clients[client] = data
                self.wait_room.remove(client)
                logging.info(
                    f'User {self.clients[client]["user"]} from {self.clients[client]["node"]} is joined.'
                )
                return

        if client in self.wait_room and (
            not self.use_authentication or not self.authentication_key
        ):
            logging.info(f'Client {client} is joined without authentication.')
            self.clients[client] = data
            self.wait_room.remove(client)
            return

        logging.info(f'Client {client} has new message: {data}')
        # other message processing policy

    def authenticate_client(self, key) -> bool:
        return key == self.authentication_key  # Successful authentication

    async def broadcast_object(self, obj, data_type):
        if not self.clients:
            return
        logging.info(f'Broadcasting {data_type} ...')

        serialized_obj = self.serialize_object(obj, data_type)
        serialized_json = json.dumps(serialized_obj)
        websockets.broadcast(
            set(self.clients.keys()), serialized_json.encode()
        )

        # await asyncio.wait([client.send(serialized_json.encode()) for client in self.clients])

    def serialize_object(self, obj, data_type):
        serialized_data = {
            'data_type': data_type,
            'data': self.encode_object(obj),
        }
        return serialized_data

    def encode_object(self, obj):
        pickled_obj = pickle.dumps(obj)
        return base64.b64encode(pickled_obj).decode()


class REvoDesignWebSocketClient:
    def __init__(
        self,
    ):
        self.server_url = 'localhost'
        self.server_port = 7890
        self.authentication_key = None
        self.receive_view_broadcast = False
        # Other initialization

        self.receive_mutagenesis_broadcast = True

        self.design_molecule = ''
        self.design_chain_id = 'A'
        self.design_sequence = ''

        self.cmap = 'bwr_r'
        self.nproc = 1

        self.connected = False
        self.client = None

    def setup_ws_client(
        self,
        comboBox_design_molecule,
        comboBox_chain_id,
        comboBox_cmap,
        spinBox_nproc,
        lineEdit_ws_server_url_to_connect,
        spinBox_ws_server_port_to_connect,
        lineEdit_ws_server_key_to_connect,
        checkBox_ws_receive_mutagenesis_broadcast,
        checkBox_ws_receive_view_broadcast,
    ):
        self.design_molecule = comboBox_design_molecule.currentText()
        self.design_chain_id = comboBox_chain_id.currentText()
        self.cmap = comboBox_cmap.currentText()
        self.nproc = spinBox_nproc.value()


        if not self.design_molecule or not self.design_chain_id:
            raise ValueError(f'Invalid design moleculre/chain id!')

        self.server_url = lineEdit_ws_server_url_to_connect.text()

        server_port = spinBox_ws_server_port_to_connect.value()
        if not server_port:
            raise ValueError(f'Invalid server port {server_port}')
        self.server_port = server_port

        if not self.server_url or not self.server_port:
            raise ValueError(f'Invalid server configurations!')

        self.authentication_key = lineEdit_ws_server_key_to_connect.text()
        self.receive_mutagenesis_broadcast = (
            checkBox_ws_receive_mutagenesis_broadcast.isChecked()
        )
        self.receive_view_broadcast = (
            checkBox_ws_receive_view_broadcast.isChecked()
        )

        logging.info(
            'Setting up of client is done. Get prepared to connect to server.'
        )

    async def connect_to_server(self):
        from REvoDesign.tools.client_tools import generate_ssl_context


        # Check network accessibility before attempting to connect
        if not self.check_server_reachable():
            logging.error("Server unreachable or network issue.")
            return
        logging.info("Server is reachable.")

        ssl_context = generate_ssl_context(role='client')
        
        self.connected = True
        server_uri=f"ws://{self.server_url}:{self.server_port}"
        logging.info(f'Connecting to server ....\n\t\t{server_uri}')
        try:
            self.client= await websockets.connect(
                server_uri,
                #ssl=ssl_context
            ) 
            await self.authenticate_client()
            await self.client.send({'hello':'world'})

            logging.info('Connection established.')

            async for message in self.client:
                await self.process_message(message)
                

        except Exception:
            logging.error(f"Unexpected error during connection: ")
            traceback.print_exc()
            self.connected = False

    async def close_connection(self):
        if not self.connected:
            logging.warning(
                'Client is not connected to any server. Do nothing.'
            )
            return

        try:
            self.client.close_connection()
            self.client.close()
        except:
            traceback.print_exc()
            logging.error(f'Client disconnecting failed.')

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

    async def authenticate_client(
        self
    ):
        from REvoDesign.tools.system_tools import OS_INFO
        from REvoDesign.tools.pymol_utils import PYMOL_VERSION
        import os

        greeting_message = {
            'node': OS_INFO.node,
            'user': os.getlogin(),
            'os': OS_INFO.system,
            'pymol_version': PYMOL_VERSION,
        }

        if self.authentication_key:
            greeting_message['auth_key'] = self.authentication_key

        logging.info(f'Authentication is sent: {greeting_message}')
        await self.client.send(json.dumps(greeting_message))

    async def process_message(self, message):
        data = json.loads(message)
        if 'data' in data and 'data_type' in data:
            obj = self.deserialize_object(data['data'], data['data_type'])
            # Use the received 'obj' and 'data_type' as needed
            if data['data_type'] == 'MutantTree' and obj and not obj.empty:
                from REvoDesign.tools.mutant_tools import existed_mutant_tree

                received_mutant_tree = obj.__deepcopy__()
                diff_mutant_tree = received_mutant_tree.diff_tree_from(
                    existed_mutant_tree()
                )
                if self.receive_mutagenesis_broadcast:
                    logging.info(
                        'Building Mutagenesis from differential mutant tree: \n '
                        f'{len(diff_mutant_tree.all_mutant_branch_ids)} branches, {len(diff_mutant_tree.all_mutant_ids)} mutants'
                    )
                    # self.mutagenesis_from_mutant_tree(
                    #     mutant_tree=diff_mutant_tree
                    # )
                    

    def deserialize_object(
        self, serialized_data, data_type
    ) -> Union[MutantTree, tuple, None]:
        if data_type == 'MutantTree':
            logging.info('Deserializing object is a MutantTree.')
            decoded_data = base64.b64decode(serialized_data)
            mutant_tree = pickle.loads(decoded_data)
            return mutant_tree
        # Handle other data types if needed
        else:
            # Handle unrecognized data types or return None
            return None

    def mutagenesis_from_mutant_tree(self, mutant_tree: MutantTree):
        if not mutant_tree or not mutant_tree.empty:
            return

        from REvoDesign.tools.mutant_tools import quick_mutagenesis

        quick_mutagenesis(
            mutant_tree=mutant_tree,
            molecule=self.design_molecule,
            chain_id=self.design_chain_id,
            sequence=self.design_sequence,
            cmap=self.cmap,
            nproc=self.nproc,
        )
