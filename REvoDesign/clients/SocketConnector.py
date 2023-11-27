import asyncio
import ssl
import websockets
import socket
import json
import base64
import pickle
from absl import logging

from REvoDesign.common.Mutant import Mutant
from REvoDesign.common.MutantTree import MutantTree
from REvoDesign.common.MutantVisualizer import MutantVisualizer


from REvoDesign.tools.client_tools import generate_ssl_context



class REvoDesignWebSocketServer:
    def __init__(self, port=7890):
        self.port = port
        self.use_authentication = False
        self.authentication_key = None
        self.do_broadcast_view = False
        self.clients = set()
        self.is_running = False  # Flag to indicate server status
        
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
        lineEdit_ws_server_port,
        checkBox_ws_server_use_key,
        lineEdit_ws_server_key,
        checkBox_ws_broadcast_view,
        doubleSpinBox_ws_view_broadcast_interval,
    ):
        self.deplex_mode = checkBox_ws_duplex_mode.isChecked()
        requested_port = int(lineEdit_ws_server_port.text())
        self.use_authentication = checkBox_ws_server_use_key.isChecked()
        self.authentication_key = lineEdit_ws_server_key.text()
        if self.use_authentication and not self.authentication_key:
            raise ValueError(f'Key for authentication is empty!')

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

    async def start_server(self):
        self.is_running = True  # Set flag when server starts
        ssl_context = generate_ssl_context(role='server')  # Generate SSL context
        async with websockets.serve(self.handler, "localhost", self.port, ssl=ssl_context):
            await asyncio.Future()  # Keeps the server running indefinitely

    async def stop_server(self):
        # Close all WebSocket connections
        self.is_running = False  # Set flag when server stops
        for client in self.clients:
            await client.close()

        # Perform any additional cleanup or shutdown operations if needed
        # ...

        print("Server shutting down...")

    async def handle_client_double_click(self, row_index):
        client_list = list(self.clients)
        if row_index < len(client_list):
            selected_client = client_list[row_index]
            await self.kick_out_client(selected_client)

    async def kick_out_client(self, client):
        # Close the WebSocket connection of the selected client
        await client.close()
        # Update the client list if needed

    async def handler(self, websocket, path):
        self.clients.add(websocket)
        try:
            async for message in websocket:
                await self.process_message(websocket, message)
        finally:
            self.clients.remove(websocket)

    async def process_message(self, websocket, message):
        data = json.loads(message)
        if 'auth_key' in data:
            authenticated = await self.authenticate_client(
                websocket, data['auth_key']
            )
            if not authenticated:
                return  # Unauthorized client

    async def authenticate_client(self, websocket, key):
        if self.use_authentication and key != self.authentication_key:
            return False  # Failed authentication
        return True  # Successful authentication

    async def broadcast_object(self, obj, data_type):
        if not self.clients:
            return

        serialized_obj = self.serialize_object(obj, data_type)
        serialized_json = json.dumps(serialized_obj)
        await asyncio.wait([client.send(serialized_json.encode()) for client in self.clients])

    def serialize_object(self, obj, data_type):
        serialized_data = {
            'data_type': data_type,
            'data': self.encode_object(obj)
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

        self.receive_mutagenesis_broadcast=True

        self.design_molecule=''
        self.design_chain_id='A'


    def setup_ws_client(self,
                        comboBox_design_molecule,
                        comboBox_chain_id,
                        comboBox_cmap,

                        lineEdit_ws_server_url_to_connect,
                        lineEdit_ws_server_port_to_connect,
                        lineEdit_ws_server_key_to_connect,

                        checkBox_ws_receive_mutagenesis_broadcast,
                        checkBox_ws_receive_view_broadcast):
        
        self.design_molecule=comboBox_design_molecule.currentText()
        self.design_chain_id=comboBox_chain_id.currentText()
        self.cmap=comboBox_cmap.currentText()
        
        if not self.design_molecule or not self.design_chain_id:
            raise ValueError(f'Invalid design moleculre/chain id!')

        self.server_url=lineEdit_ws_server_url_to_connect.text()
        self.server_port=int(lineEdit_ws_server_port_to_connect.text())

        if not self.server_url or not self.server_port:
            raise ValueError(f'Invalid server configurations!')
        
        self.authentication_key=lineEdit_ws_server_key_to_connect.text()
        self.receive_mutagenesis_broadcast=checkBox_ws_receive_mutagenesis_broadcast.isChecked()
        self.receive_view_broadcast=checkBox_ws_receive_view_broadcast.isChecked()


    async def connect_to_server(self):
        ssl_context = generate_ssl_context(role='client')
        try:
            async with websockets.connect(
                f"wss://{self.server_url}:{self.server_port}", ssl=ssl_context,
            ) as websocket:
                if self.authentication_key:
                    await self.authenticate_client(websocket)
                async for message in websocket:
                    await self.process_message(message)
        except websockets.exceptions.ConnectionClosedError as e:
            logging.error(f"Connection Closed: {e}")

    async def authenticate_client(self, websocket):
        if self.authentication_key:
            auth_message = json.dumps({'auth_key': self.authentication_key})
            await websocket.send(auth_message)

    async def process_message(self, message):
        data = json.loads(message)
        if 'data' in data and 'data_type' in data:
            obj = self.deserialize_object(data['data'], data['data_type'])
            # Use the received 'obj' and 'data_type' as needed

    def deserialize_object(self, serialized_data, data_type):
        decoded_obj = base64.b64decode(serialized_data)
        return pickle.loads(decoded_obj)