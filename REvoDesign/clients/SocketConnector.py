import asyncio
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
        self.port = port
        self.use_authentication = False
        self.authentication_key = None
        self.do_broadcast_view = False
        # store client with its greeting message
        self.clients = dict()
        self.wait_room= set()
        self.is_running = False  # Flag to indicate server status
        self.server = None

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
                self.handler, "localhost", self.port, #ssl=ssl_context,
            )
        except:
            traceback.print_exc()
            logging.error('Server initialization failed.')
            self.is_running=False

            # Perform any cleanup or shutdown operations here

    async def stop_server(self):
        # Close all WebSocket connections
        self.is_running = False  # Set flag when server stops
        logging.info('Server is stopped.')
        for client in self.clients:
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

    async def handler(self, websocket, path):
        self.wait_room.add(websocket)

        # let the client join if no authentication requires
        try:
            async for message in websocket:
                await self.process_message(websocket, message)
        except:
            traceback.print_exc
        # finally:
        #     self.clients.pop(websocket)

    async def process_message(self, websocket, message):
        data = json.loads(message)

        if websocket in self.wait_room and self.use_authentication and 'auth_key' in data:
            authenticated = await self.authenticate_client(data['auth_key'])
            
            if not authenticated:
                self.wait_room.remove(websocket)
                if websocket in self.clients:
                    self.clients.pop(websocket) 
                logging.info(
                    f'Client {websocket} is removed due to  unauthenticated identification.'
                )
                return  # Unauthorized client
            else:
                logging.info(
                    f'Client {websocket} has passed authentication and is joined.'
                )
                self.clients[websocket]=data
                self.wait_room.remove(websocket)
                return
        
        if websocket in self.wait_room and (not self.use_authentication or not self.authentication_key):
            logging.info(
                    f'Client {websocket} is joined without authentication.'
                )
            self.clients[websocket]=data
            self.wait_room.remove(websocket)
            return


    async def authenticate_client(self, key):
        if self.use_authentication and key != self.authentication_key:
            return False  # Failed authentication
        return True  # Successful authentication

    async def broadcast_object(self, obj, data_type):
        if not self.clients:
            return
        logging.info(f'Broadcasting {data_type} ...')

        serialized_obj = self.serialize_object(obj, data_type)
        serialized_json = json.dumps(serialized_obj)
        websockets.broadcast(set(self.clients.keys()), serialized_json.encode())

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
        self.progress_bar = None

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
        progress_bar,
    ):
        self.design_molecule = comboBox_design_molecule.currentText()
        self.design_chain_id = comboBox_chain_id.currentText()
        self.cmap = comboBox_cmap.currentText()
        self.nproc = spinBox_nproc.value()

        self.progress_bar = progress_bar

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
        

        logging.info('Connecting to server ....')
        ssl_context = generate_ssl_context(role='client')
        self.connected = True
        try:
            self.client = await websockets.connect(
                f"ws://{self.server_url}:{self.server_port}",
                #ssl=ssl_context,server_hostname=self.server_url
            )

            if self.authentication_key:
                await self.authenticate_client()
            async for message in self.client:
                await self.process_message(message)
        except websockets.exceptions.ConnectionClosedError as e:
            logging.error(f"Connection Closed: {e}")
            self.connected = False
        except:
            traceback.print_exc()

    async def disconnect_from_server(self):
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

    async def authenticate_client(self, ):
        from REvoDesign.tools.system_tools import OS_INFO
        from REvoDesign.tools.pymol_utils import PYMOL_VERSION
        import os
        greeting_message={
                'node': OS_INFO.node,
                'user': os.getlogin(),
                'os': OS_INFO.system,
                'pymol_version': PYMOL_VERSION
                },
                
        if self.authentication_key:
            greeting_message['auth_key']=self.authentication_key
        
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
                    self.mutagenesis_from_mutant_tree(
                        mutant_tree=diff_mutant_tree
                    )

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
            progress_bar=self.progress_bar,
        )
