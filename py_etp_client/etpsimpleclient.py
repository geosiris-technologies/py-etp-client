# Copyright (c) 2022-2023 Geosiris.
# SPDX-License-Identifier: Apache-2.0
import asyncio
import ssl
import threading
from typing import Optional, Any, List
import websocket
import time
import logging

from etpproto.connection import ETPConnection, ConnectionType
from etpproto.messages import Message

from etpproto.client_info import ClientInfo
from etptypes.energistics.etp.v12.protocol.core.request_session import (
    RequestSession,
)

from py_etp_client.requests import default_request_session
from py_etp_client.auth import basic_auth_encode

# To enable handlers
from py_etp_client.serverprotocols import (
    CoreProtocolPrinter,
    DiscoveryProtocolPrinter,
    DataspaceHandlerPrinter,
    StoreProtocolPrinter,
    DataArrayHandlerPrinter,
    SupportedTypesProtocolPrinter,
    TransactionHandlerPrinter,
)


class ETPSimpleClient:

    def __init__(
        self,
        url: str,
        spec: Optional[ETPConnection],
        access_token: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        headers: Optional[dict] = None,
        verify: Optional[Any] = None,
        req_session: Optional[RequestSession] = None,
    ):
        self.url = url
        if not self.url.startswith("ws"):
            if self.url.lower().startswith("http"):
                self.url = "ws" + self.url[4:]
            else:
                self.url = "wss://" + self.url

        self.spec = spec
        self.access_token = access_token
        self.headers = {}
        self.ws = None
        self.thread = None
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self.request_session = req_session or default_request_session()
        # other attributes
        self.closed = False
        self.sslopt = None
        # Cache for received msg
        self.recieved_msg_dict = {}

        # Dictionary to store waiting requests {message_id: (Event, response)}
        self.pending_requests = {}

        if self.spec is None:
            self.spec = ETPConnection(connection_type=ConnectionType.CLIENT)
            # raise Exception(
            #     "You must provide an ETPConnection instance to define your client/server spec"
            # )
        if self.spec.client_info is None:
            self.spec.client_info = ClientInfo(
                login=username or "GeosirisETPClient",
                endpoint_capabilities={},
            )
        if "MaxWebSocketFramePayloadSize" not in self.spec.client_info.endpoint_capabilities:
            self.spec.client_info.endpoint_capabilities["MaxWebSocketFramePayloadSize"] = 900000
        if "MaxWebSocketMessagePayloadSize" not in self.spec.client_info.endpoint_capabilities:
            self.spec.client_info.endpoint_capabilities["MaxWebSocketMessagePayloadSize"] = 900000

        # Headers
        if isinstance(headers, dict):
            self.headers = self.headers | headers
        elif isinstance(headers, list):
            for a_h in headers or []:
                self.headers = self.headers | a_h

        # Access token :
        if self.access_token is not None and len(self.access_token) > 0:
            if "bearer" not in self.access_token.lower():
                self.access_token = f"Bearer {self.access_token}"
            self.headers["Authorization"] = self.access_token
        elif username is not None:
            self.headers["Authorization"] = "Basic " + basic_auth_encode(username, password)

        # SSL
        if isinstance(verify, bool) and not verify:
            self.sslopt = {"cert_reqs": ssl.CERT_NONE}

    def on_error(self, ws, error):
        logging.info(f"Error: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        logging.info("WebSocket closed")
        self.closed = True

    def on_open(self, ws):
        logging.info("Connected to WebSocket!")
        try:
            req_sess = default_request_session()
            # logging.debug("Sending RequestSession")
            # logging.debug(req_sess.json(by_alias=True, indent=4))
            answer = self.send(req_sess, 4.0)
            logging.info(f"CONNECTED : {answer}")
        except Exception as e:
            logging.error(e)

    def _run_websocket(self):
        """Runs the WebSocket connection in a separate thread."""
        self.ws = websocket.WebSocketApp(
            self.url,
            header=self.headers,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
        )
        self.ws.run_forever(sslopt=self.sslopt)

    def start(self):
        """Start the WebSocket connection in a separate thread."""
        if self.thread is None or not self.thread.is_alive():
            self.thread = threading.Thread(target=self._run_websocket, daemon=True)
            self.thread.start()
            time.sleep(1)  # Allow time for connection

    def stop(self):
        """Gracefully stop the WebSocket connection."""
        self.stop_event.set()
        if self.ws:
            self.ws.close()
        if self.thread:
            self.thread.join()
        logging.info("WebSocket client stopped.")

    def on_message(self, ws, message):
        """Handles incoming WebSocket messages."""
        # logging.info(f"Received: {message}")
        # logging.debug("##> before recieved " )
        recieved = Message.decode_binary_message(
            message,
            dict_map_pro_to_class=ETPConnection.generic_transition_table,
        )
        if recieved.is_final_msg():
            logging.info(f"\n##> recieved header : {recieved.header}")
            logging.info(f"##> body type : {type(recieved.body)}")

        async def handle_msg(conn: ETPConnection, client, msg: bytes):
            try:
                if message:
                    async for b_msg in self.spec.handle_bytes_generator(message):
                        pass

            # return None, None
            except Exception as e:
                logging.error(f"#ERR: {type(e).__name__}")
                logging.error(f"#Err: {message}")
                raise e

        if recieved.header.correlation_id not in self.recieved_msg_dict:
            self.recieved_msg_dict[recieved.header.correlation_id] = []
            self.recieved_msg_dict[recieved.header.correlation_id].append(recieved)

        if recieved.header.correlation_id is not None:
            with self.lock:
                if recieved.header.correlation_id in self.pending_requests:
                    event, _ = self.pending_requests[recieved.header.correlation_id]
                    self.pending_requests[recieved.header.correlation_id] = (
                        event,
                        self.recieved_msg_dict[recieved.header.correlation_id],
                    )
                    event.set()
        asyncio.run(handle_msg(self.spec, self, message))

    def send_and_wait(self, req, timeout: int = 5) -> List[Message]:
        """
        Sends an ETP message and wait for all answers.
        Returns a list of all messages received
        """
        msg_id = self.send(req=req, timeout=timeout)

        event = threading.Event()
        with self.lock:
            self.pending_requests[msg_id] = (event, None)

            # logging.debug(f"@WS: [{m_id}] {obj_msg}")

        # Wait for the response with the correct ID
        success = event.wait(timeout)

        with self.lock:
            _, response = self.pending_requests.pop(msg_id, (None, None))

        if success and response:
            return response
        else:
            raise TimeoutError(f"No response received for message ID: {msg_id}")

    def send(self, req, timeout: int = 5) -> int:
        """
        Sends an ETP message and wait for all answers.
        Returns the message id
        """
        if not self.ws:
            raise RuntimeError("WebSocket is not connected.")

        obj_msg = Message.get_object_message(etp_object=req)

        msg_id = -1
        for (
            m_id,
            msg_to_send,
        ) in self.spec.send_msg_and_error_generator(obj_msg, None):
            self.ws.send(msg_to_send, websocket.ABNF.OPCODE_BINARY)
            if msg_id < 0:
                msg_id = m_id
            logging.debug(f"@WS: [{m_id}]")
            logging.debug(obj_msg)

        return msg_id

    def is_connected(self):
        # logging.debug(self.spec)
        # return self.spec.is_connected
        return self.spec.is_connected and not self.closed
