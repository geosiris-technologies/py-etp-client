# Copyright (c) 2022-2023 Geosiris.
# SPDX-License-Identifier: Apache-2.0
"""
ETP Simple Client Module

This module provides ETPSimpleClient, a WebSocket client for ETP (Energistics Transfer Protocol)
connections. The client supports asynchronous message handling, authentication, automatic
reconnection, and a comprehensive event listener system.

Key Features:
- WebSocket-based ETP protocol communication
- Basic and Bearer token authentication support
- Automatic reconnection with exponential backoff
- Message correlation and response waiting
- Event listener paradigm for reactive programming

The event listener system allows you to register callback functions that are triggered
when specific events occur (connection open/close, errors, messages, start/stop operations).
This enables building reactive applications that respond to ETP client state changes.

Example:
    ```python
    from py_etp_client.etpsimpleclient import ETPSimpleClient, EventType

    def handle_events(event_type: EventType, **kwargs):
        if event_type == EventType.ON_OPEN:
            print(f"Connected! WebSocket: {kwargs.get('ws')}")
        elif event_type == EventType.ON_ERROR:
            print(f"Error: {kwargs.get('error')}")
        elif event_type == EventType.ON_MESSAGE:
            print(f"Message: {len(kwargs.get('message', b''))} bytes")

    client = ETPSimpleClient(url="wss://example.com", spec=None)
    client.add_listener(EventType.ON_OPEN, handle_events)
    client.add_listener(EventType.ON_ERROR, handle_events)
    client.add_listener(EventType.ON_MESSAGE, handle_events)
    client.start()
    ```
"""
import asyncio
from dotenv import load_dotenv
from enum import Enum

import json
import os
import ssl
import threading
from typing import Optional, Any, List, Callable, Dict, Union
import websocket
import time
import logging

from etpproto.connection import ETPConnection, ConnectionType
from etpproto.messages import Message, decode_binary_message

from etpproto.client_info import ClientInfo
from etptypes.energistics.etp.v12.protocol.core.request_session import (
    RequestSession,
)

from py_etp_client.etpconfig import ETPConfig, ServerConfig
from py_etp_client.etp_requests import default_request_session
from py_etp_client.auth import AuthConfig, BasicAuthConfig, TokenManager
from py_etp_client import CloseSession

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

MSG_ID_LOGGER = logging.getLogger("MSG_ID_LOGGER")

load_dotenv()
DEBUG = os.getenv("DEBUG", "False").lower() in ["true", "1", "yes"]


class EventType(Enum):
    """Enum defining the types of events that can trigger listeners.

    Each event type corresponds to a specific operation or state change in the ETP client.
    Listeners registered for these events will be called with relevant context data.

    Event Types and their **kwargs parameters:
    - ON_OPEN: WebSocket connection established
      * ws: The WebSocket object
    - ON_CLOSE: WebSocket connection closed
      * ws: The WebSocket object
      * close_status_code: The close status code
      * close_msg: The close message
    - ON_ERROR: Error occurred
      * ws: The WebSocket object
      * error: The error that occurred
    - ON_MESSAGE: Message received
      * ws: The WebSocket object
      * message: The raw message bytes received
      * received: The decoded Message object
    - START: Client starting (no additional parameters)
    - STOP: Client stopping (no additional parameters)
    - CLOSE: Client closing (no additional parameters)
    """

    ON_OPEN = "on_open"
    ON_CLOSE = "on_close"
    ON_ERROR = "on_error"
    ON_MESSAGE = "on_message"
    START = "start"
    STOP = "stop"
    CLOSE = "close"


class ETPSimpleClient:

    def __init__(
        self,
        url: Optional[str] = None,
        spec: Optional[ETPConnection] = None,
        access_token: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        headers: Optional[Union[dict, str]] = None,
        verify: Optional[Any] = None,
        max_reconnect_attempts: int = 5,
        req_session: Optional[RequestSession] = None,
        config: Optional[Union[ETPConfig, ServerConfig, AuthConfig]] = None,
    ):
        """Initializes the ETPSimpleClient with the given parameters.
        This class is a simple WebSocket client for ETP (Energistics Transfer Protocol) connections.
        It handles the connection, sending and receiving messages, and managing the connection state.
        It also provides a method to send messages and wait for responses.

        Event Listener System:
        ---------------------
        The client supports a listener paradigm that allows you to register callback functions
        to be notified when specific events occur. This enables reactive programming patterns
        and decoupled event handling.

        Available Event Types (from EventType enum):
        - ON_OPEN: Triggered when WebSocket connection is established
        - ON_CLOSE: Triggered when WebSocket connection is closed
        - ON_ERROR: Triggered when an error occurs
        - ON_MESSAGE: Triggered when a message is received
        - START: Triggered when the client starts
        - STOP: Triggered when the client stops gracefully
        - CLOSE: Triggered when the client initiates a close operation

        Listener Functions:
        - Must accept (event_type: EventType, **kwargs) as parameters
        - event_type: The EventType enum value indicating which event occurred
        - **kwargs: Event-specific data, see details below:

        Event-specific kwargs:
        - ON_OPEN: ws (WebSocket object)
        - ON_CLOSE: ws (WebSocket object), close_status_code (int), close_msg (str)
        - ON_ERROR: ws (WebSocket object), error (exception/error object)
        - ON_MESSAGE: ws (WebSocket object), message (raw bytes), received (decoded Message)
        - START: No additional parameters
        - STOP: No additional parameters
        - CLOSE: No additional parameters

        Example Usage:
        ```python
        def my_listener(event_type: EventType, **kwargs):
            if event_type == EventType.ON_ERROR:
                print(f"Error occurred: {kwargs.get('error')}")
                print(f"WebSocket: {kwargs.get('ws')}")
            elif event_type == EventType.ON_MESSAGE:
                print(f"Message received: {len(kwargs.get('message', b''))} bytes")
                print(f"Decoded message: {kwargs.get('received')}")
            elif event_type == EventType.ON_CLOSE:
                print(f"Connection closed with code: {kwargs.get('close_status_code')}")
                print(f"Close message: {kwargs.get('close_msg')}")
            elif event_type == EventType.ON_OPEN:
                print(f"Connection opened: {kwargs.get('ws')}")

        client = ETPSimpleClient(url="wss://example.com", spec=None)
        client.add_listener(EventType.ON_ERROR, my_listener)
        client.add_listener(EventType.ON_MESSAGE, my_listener)
        client.add_listener(EventType.ON_CLOSE, my_listener)
        client.add_listener(EventType.ON_OPEN, my_listener)
        ```

        Listener Management:
        - add_listener(event_type, callback): Register a listener function
        - remove_listener(event_type, callback): Unregister a specific listener
        - Multiple listeners can be registered for the same event type
        - Listener exceptions are caught and logged without affecting client operation

        Args:
            url (str): The WebSocket URL to connect to.
            spec (Optional[ETPConnection]): The ETPConnection specification to use.
            access_token (Optional[str], optional): Access token for authentication. Defaults to None.
            username (Optional[str], optional): Username for basic authentication (ignored if access_token is provided). Defaults to None.
            password (Optional[str], optional): Password for basic authentication (ignored if access_token is provided). Defaults to None.
            headers (Optional[Union[dict, str]], optional): Additional headers to include in the WebSocket request. Defaults to None. If a string is provided, it will be parsed as JSON.
            verify (Optional[Any], optional): SSL verification options. Defaults to None.
            max_reconnect_attempts (int, optional): Maximum number of reconnection attempts. Defaults to 5.
            req_session (Optional[RequestSession], optional): RequestSession object to use. If None provided, a default one will be created. Defaults to None.
            config (Optional[Union[ETPConfig, ServerConfig, AuthConfig]], optional): Configuration object for server settings. Defaults to None.
        """
        self.url = url

        self.spec = spec
        self.access_token = access_token
        self.headers = {}
        self.request_session = req_session or default_request_session()
        self.max_reconnect_attempts = max_reconnect_attempts or 3
        self.verify = verify
        self.token_manager = TokenManager()

        # Headers
        if isinstance(headers, dict):
            self.headers = self.headers | headers
        # elif isinstance(headers, list):
        #     for a_h in headers or []:
        #         self.headers = self.headers | a_h
        elif isinstance(headers, str):
            try:
                self.headers = json.loads(headers)
            except json.JSONDecodeError:
                logging.error(f"Invalid JSON string for headers: {headers}")
                self.headers = {}

        # Access token :
        if self.access_token is not None and len(self.access_token) > 0:
            if "bearer" not in self.access_token.lower():
                self.access_token = f"Bearer {self.access_token}"
            self.headers["Authorization"] = self.access_token
        elif username is not None and password is not None:
            self.headers["Authorization"] = "Basic " + str(
                self.token_manager._get_basic_auth_token(BasicAuthConfig(username, password))
            )

        # Listener infrastructure
        self.listeners: Dict[EventType, List[Callable[..., None]]] = {event_type: [] for event_type in EventType}

        # other attributes
        self.closed = False
        self.sslopt = None
        self.ws = None
        self.thread = None
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        # Cache for received msg
        self.recieved_msg_dict = {}

        # Dictionary to store waiting requests {message_id: (Event, response)}
        self.pending_requests = {}

        self.client_info = (
            ClientInfo(
                login=username or "GeosirisETPClient",
                endpoint_capabilities={},
            )
            if self.spec is not None
            else None
        )

        if isinstance(config, ETPConfig):
            config = config.as_server_config()

        if config is not None and isinstance(config, ServerConfig):
            self.url = config.url or self.url
            self.verify = config.verify_ssl if self.verify is None else self.verify
            # self.max_reconnect_attempts = (
            #     config.auto_reconnect if config.auto_reconnect is not None else self.max_reconnect_attempts
            # )
            self.headers = (
                self.headers.update(config.additional_headers or {})
                if self.headers
                else config.additional_headers or {}
            )
            logging.debug(f"\n\nWebSocket Headers: {self.headers}")
            self.access_token = self.token_manager.get_token(config)
            if self.access_token is not None:
                self.headers["Authorization"] = self.access_token

        if self.url is None:
            raise ValueError("WebSocket URL must be provided either directly or via config")

        if not self.url.startswith("ws"):
            if self.url.lower().startswith("http"):
                self.url = "ws" + self.url[4:]
            else:
                self.url = "wss://" + self.url

        logging.debug(f"WebSocket URL set to: {self.url}")
        logging.debug(f"WebSocket Headers: {self.headers}")
        self._init_connection(config)

        # SSL
        if isinstance(self.verify, bool) and not self.verify:
            self.sslopt = {"cert_reqs": ssl.CERT_NONE}

    def _init_connection(self, config: Optional[Union[ServerConfig, AuthConfig]] = None) -> None:
        if self.spec is None:
            self.spec = ETPConnection(connection_type=ConnectionType.CLIENT)
            if self.client_info is not None:
                self.spec.client_info = self.client_info

        if (
            config is not None
            and isinstance(config, ServerConfig)
            and config.max_web_socket_frame_payload_size is not None
        ):
            self.spec.client_info.endpoint_capabilities["MaxWebSocketFramePayloadSize"] = (
                config.max_web_socket_frame_payload_size
            )
        elif "MaxWebSocketFramePayloadSize" not in self.spec.client_info.endpoint_capabilities:
            self.spec.client_info.endpoint_capabilities["MaxWebSocketFramePayloadSize"] = 900000

        if (
            config is not None
            and isinstance(config, ServerConfig)
            and config.max_web_socket_message_payload_size is not None
        ):
            self.spec.client_info.endpoint_capabilities["MaxWebSocketMessagePayloadSize"] = (
                config.max_web_socket_message_payload_size
            )
        elif "MaxWebSocketMessagePayloadSize" not in self.spec.client_info.endpoint_capabilities:
            self.spec.client_info.endpoint_capabilities["MaxWebSocketMessagePayloadSize"] = 900000

    def add_listener(self, event_type: EventType, callback: Callable[..., None]) -> None:
        """
        Register a listener function for a specific event type.

        Args:
            event_type (EventType): The type of event to listen for
            callback (Callable[..., None]): Function to call when the event occurs.
                                           It will receive the event_type as first argument,
                                           followed by **kwargs containing event-specific data.
        """
        if not isinstance(event_type, EventType):
            raise ValueError(f"event_type must be an instance of EventType, got {type(event_type)}")

        if not callable(callback):
            raise ValueError("callback must be callable")

        self.listeners[event_type].append(callback)

    def remove_listener(self, event_type: EventType, callback: Callable[..., None]) -> bool:
        """
        Unregister a listener function for a specific event type.

        Args:
            event_type (EventType): The type of event to stop listening for
            callback (Callable[..., None]): The exact function reference that was registered

        Returns:
            bool: True if the listener was found and removed, False otherwise
        """
        if not isinstance(event_type, EventType):
            raise ValueError(f"event_type must be an instance of EventType, got {type(event_type)}")

        try:
            self.listeners[event_type].remove(callback)
            return True
        except ValueError:
            return False

    def _notify_listeners(self, event_type: EventType, **kwargs) -> None:
        """
        Internal method to notify all registered listeners for a specific event type.

        Args:
            event_type (EventType): The type of event that occurred
            **kwargs: Event-specific data to pass to the listeners
        """
        for callback in self.listeners[event_type]:
            try:
                callback(event_type, **kwargs)
            except Exception as e:
                logging.error(f"Error in listener {callback.__name__} for event {event_type.value}: {e}")

    def on_error(self, ws, error):
        logging.info(f"Error: {error}")
        self._notify_listeners(EventType.ON_ERROR, ws=ws, error=error)

    def on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket closure and notify all waiting operations."""
        logging.info("WebSocket closed")
        self.closed = True
        self.stop_event.set()

        # Signal all waiting events to prevent hanging
        if hasattr(self, "_connection_closed_events"):
            for event in list(self._connection_closed_events):
                event.set()

        self._notify_listeners(EventType.ON_CLOSE, ws=ws, close_status_code=close_status_code, close_msg=close_msg)

    def on_open(self, ws):
        logging.info("Connected to WebSocket!")
        try:
            req_sess = default_request_session()
            # logging.debug("Sending RequestSession")
            # logging.debug(req_sess.json(by_alias=True, indent=4))
            answer = self.send(req_sess, 4)
            logging.info(f"CONNECTED : {answer}")
        except Exception as e:
            import traceback

            traceback.print_exc()
            logging.error(e)

        self._notify_listeners(EventType.ON_OPEN, ws=ws)

    def _run_websocket(self):
        """Runs the WebSocket connection in a separate thread with configurable reconnection attempts."""
        logging.debug(self.headers)

        reconnect_count = 0
        while reconnect_count <= self.max_reconnect_attempts and not self.stop_event.is_set():
            try:
                self.ws = websocket.WebSocketApp(
                    self.url,
                    subprotocols=[ETPConnection.SUB_PROTOCOL],
                    header=self.headers,
                    on_open=self.on_open,
                    on_message=self.on_message,
                    on_error=self.on_error,
                    on_close=self.on_close,
                )

                logging.info(
                    f"Connecting to {self.url} ... (attempt {reconnect_count + 1}/{self.max_reconnect_attempts + 1})"
                )

                if self.sslopt:
                    self.ws.run_forever(sslopt=self.sslopt, reconnect=False)
                else:
                    self.ws.run_forever(reconnect=False)

                # Connection closed normally
                if self.stop_event.is_set():
                    logging.info("Connection stopped by user request")
                    break

            except Exception as e:
                logging.error(f"WebSocket connection failed (attempt {reconnect_count + 1}): {e}")

            reconnect_count += 1

            if reconnect_count <= self.max_reconnect_attempts and not self.stop_event.is_set():
                # Exponential backoff: 2, 4, 8, 16, 30 seconds
                wait_time = min(2**reconnect_count, 30)
                logging.info(f"Reconnecting in {wait_time} seconds...")
                if self.stop_event.wait(wait_time):
                    break
            else:
                if reconnect_count > self.max_reconnect_attempts:
                    logging.error(f"Maximum reconnection attempts ({self.max_reconnect_attempts}) reached")
                self.closed = True
                break

    def start(self):
        """Start the WebSocket connection in a separate thread."""

        self.ws = None
        self.closed = False
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.recieved_msg_dict = {}
        self.pending_requests = {}
        self._init_connection()
        if self.thread is None or not self.thread.is_alive():
            self.thread = threading.Thread(target=self._run_websocket, daemon=True)
            self.thread.start()
            time.sleep(1)  # Allow time for connection
        self._notify_listeners(EventType.START)

        logging.debug("WebSocket client started. with headers : %s", self.headers)

    def stop(self):
        """Gracefully stop the WebSocket connection."""
        self.stop_event.set()
        if self.ws:
            self.ws.close()
        logging.info("WebSocket client stopped.")

        if self.thread and self.thread != threading.current_thread():
            self.thread.join()
            self.thread = None
        self.spec = None

        self._notify_listeners(EventType.STOP)

    def close(self):
        """Close the WebSocket connection.

        This method sends a CloseSession message, stops the client, and notifies
        CLOSE event listeners.
        """
        self.send(CloseSession(reason="I want to stop"), timeout=2)
        self.stop()

        self._notify_listeners(EventType.CLOSE)

    def on_message(self, ws, message):
        """Handles incoming WebSocket messages."""
        # logging.info(f"Received: {message}")
        # logging.debug("##> before recieved " )
        recieved = Message.decode_binary_message(
            message,
            dict_map_pro_to_class=ETPConnection.generic_transition_table,
        )

        if not isinstance(recieved, Message):
            logging.error(f"Received message is not an instance of Message: {type(recieved)} : {recieved}")
            return

        if recieved.is_final_msg():
            logging.info(f"\n##> recieved header : {recieved.header}")
            logging.info(f"##> body type : {type(recieved.body)}")

        if self.spec is None:
            logging.error(
                "ETPConnection spec is not defined for this client. A default one should have been created. Check other logs for errors."
            )
            return

        async def handle_msg(conn: ETPConnection, client, msg: bytes):
            try:
                if message is not None and self.spec is not None:
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

        self._notify_listeners(EventType.ON_MESSAGE, ws=ws, message=message, received=recieved)

    def send_and_wait(self, req, timeout: int = 5) -> List[Message]:
        """
        Sends an ETP message and waits passively for all answers.
        Returns a list of all messages received.

        Args:
            req: The request to send
            timeout: Maximum time to wait for a response in seconds

        Returns:
            List[Message]: List of received messages

        Raises:
            TimeoutError: If no response is received within timeout
            RuntimeError: If WebSocket connection is closed while waiting
        """
        t_start_send = time.time()
        msg_id = self.send(req=req, timeout=timeout)
        logging.debug(f"[PERF] Message sent in {time.time() - t_start_send:.2f} seconds")

        # Create event that will be triggered by on_message or on_close
        event = threading.Event()

        # Register a connection_closed callback if not already present
        if not hasattr(self, "_connection_closed_events"):
            self._connection_closed_events = set()

        self._connection_closed_events.add(event)

        with self.lock:
            self.pending_requests[msg_id] = (event, None)

        # Passive waiting - simply wait on the event with timeout
        if not event.wait(timeout):
            logging.debug(f"[PERF] timeout after {timeout} seconds for message ID: {msg_id}")
            # Timeout occurred
            with self.lock:
                self.pending_requests.pop(msg_id, None)
                if hasattr(self, "_connection_closed_events"):
                    self._connection_closed_events.discard(event)
            raise TimeoutError(f"No response received for message ID: {msg_id} within {timeout} seconds")

        # Check if the wait was interrupted by connection close
        if self.closed or self.stop_event.is_set():
            with self.lock:
                self.pending_requests.pop(msg_id, None)
                if hasattr(self, "_connection_closed_events"):
                    self._connection_closed_events.discard(event)
            raise RuntimeError("WebSocket connection closed while waiting for response")

        # Get the response
        with self.lock:
            logging.debug(f"[PERF] message {msg_id} received after {time.time() - t_start_send:.2f} seconds")
            _, response = self.pending_requests.pop(msg_id, (None, None))
            if hasattr(self, "_connection_closed_events"):
                self._connection_closed_events.discard(event)

        return response if response else []

    def send(self, req, timeout: int = 5) -> int:
        """
        Sends an ETP message and wait for all answers.
        Returns the message id
        """
        if not self.ws:
            raise RuntimeError("WebSocket is not connected.")

        obj_msg = Message.get_object_message(etp_object=req)

        if not isinstance(obj_msg, Message):
            raise TypeError(f"Expected an instance of Message, got {type(obj_msg)}")

        assert self.spec is not None, "ETPConnection spec must be defined before sending messages."

        msg_id = -1
        for (
            m_id,
            msg_to_send,
        ) in self.spec.send_msg_and_error_generator(
            obj_msg, None  # type: ignore
        ):
            if DEBUG:
                # only use for debugging
                _dg_msg = Message.decode_binary_message(msg_to_send, ETPConnection.generic_transition_table)
                if _dg_msg is not None:
                    MSG_ID_LOGGER.debug(
                        f"[{self.url}] Sending: [{m_id:0>4.0f} ==> {_dg_msg.header.message_id:0>4.0f}] {type(_dg_msg.body)} final ? {_dg_msg.is_final_msg()}"
                    )
                else:
                    MSG_ID_LOGGER.debug(f"[{self.url}] Sending: [{m_id:0>4.0f}] (could not decode message)")
            self.ws.send(msg_to_send, websocket.ABNF.OPCODE_BINARY)
            if msg_id < 0:
                msg_id = m_id
            # logging.debug(obj_msg)

        return msg_id

    def is_connected(self):
        """Checks if the WebSocket connection is open and the etp connexion is active

        Returns:
            bool: True if connected, False otherwise
        """
        # logging.debug(self.spec)
        # return self.spec.is_connected
        return self.spec is not None and self.spec.is_connected and not self.closed
