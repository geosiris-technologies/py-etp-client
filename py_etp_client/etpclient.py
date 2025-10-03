# Copyright (c) 2022-2023 Geosiris.
# SPDX-License-Identifier: Apache-2.0
"""
ETP Client Module

This module provides ETPClient, a high-level client for ETP (Energistics Transfer Protocol)
operations. ETPClient extends ETPSimpleClient with advanced functionality for energy industry
data management, including data objects, dataspaces, data arrays, and transactions.

The client inherits the complete event listener system from ETPSimpleClient, enabling
reactive programming patterns and event-driven architectures for ETP applications.

Key Components:
- ETPClient: High-level ETP client with advanced data management capabilities
- Data object operations (CRUD)
- Dataspace management
- Data array handling for large datasets
- Transaction support for atomic operations
- Resource discovery and type querying
- Inherited event listener system for reactive programming

Example Usage:
    ```python
    from py_etp_client.etpclient import ETPClient
    from py_etp_client.etpsimpleclient import EventType

    # Create client with event handling
    def handle_connection(event_type: EventType, **kwargs):
        if event_type == EventType.ON_OPEN:
            print("Connected to ETP server")

    client = ETPClient(url="wss://etp-server.com", spec=None)
    client.add_listener(EventType.ON_OPEN, handle_connection)

    # Start and use high-level operations
    client.start()
    dataspaces = client.get_dataspaces()
    ```

For detailed information about the event listener system, see ETPSimpleClient documentation.
"""
import json
import os
import logging
from time import perf_counter, sleep
from typing import Any, Dict, List, Optional, Union, Tuple

import numpy as np
from energyml.utils.uri import Uri as ETPUri
from energyml.utils.epc import Epc
from energyml.utils.constants import epoch
from py_etp_client.auth import AuthConfig
from py_etp_client.etpconfig import ETPConfig, ServerConfig
from py_etp_client.etp_requests import get_any_array_type, get_any_array_type_size, read_energyml_obj


from py_etp_client.etpsimpleclient import ETPSimpleClient
from py_etp_client import RequestSession, GetDataObjects
from etpproto.connection import ETPConnection, ConnectionType


from py_etp_client.etp_requests import (
    create_data_object,
    get_any_array,
    get_dataspaces,
    get_resources,
    get_supported_types,
    put_dataspace,
)
from py_etp_client.utils import (
    get_valid_uri_str,
    reshape_uris_as_str_list,
    reshape_uris_as_str_dict,
    T_UriSingleOrGrouped,
)

from py_etp_client import (
    Uuid,
    Authorize,
    AuthorizeResponse,
    AnyArrayType,
    CommitTransaction,
    CommitTransactionResponse,
    AnyLogicalArrayType,
    DataArray,
    DataArrayIdentifier,
    DataArrayMetadata,
    Dataspace,
    DeleteDataObjects,
    DeleteDataObjectsResponse,
    DeleteDataspaces,
    DeleteDataspacesResponse,
    GetDataArrayMetadata,
    GetDataArrayMetadataResponse,
    GetDataArrays,
    GetDataArraysResponse,
    GetDataObjectsResponse,
    GetDataspacesResponse,
    GetDataSubarrays,
    GetDataSubarraysResponse,
    GetDataSubarraysType,
    GetResourcesResponse,
    GetSupportedTypesResponse,
    Ping,
    Pong,
    ProtocolException,
    PutDataArrays,
    PutDataArraysResponse,
    PutDataSubarrays,
    PutDataSubarraysType,
    PutDataSubarraysResponse,
    PutDataArraysType,
    PutDataObjects,
    PutDataObjectsResponse,
    PutDataspacesResponse,
    Resource,
    RollbackTransaction,
    RollbackTransactionResponse,
    StartTransaction,
    StartTransactionResponse,
    PutUninitializedDataArrays,
    PutUninitializedDataArraysResponse,
    PutUninitializedDataArrayType,
)


def get_type_size(data_type: str) -> int:
    """
    Return the size in bytes of a given data type. Supports numpy dtypes and common string types.
    Accepts:
      - numpy.dtype or string convertible to numpy dtype
      - 'string', 'bytes', 'boolean' (special handling)
    """
    try:
        # Try to interpret as numpy dtype
        dtype = np.dtype(data_type)
        return dtype.itemsize
    except Exception:
        # Fallback for non-numpy types
        if data_type in ("string", "bytes"):
            return 1  # Variable length, assume 1 byte per char/byte
        elif data_type in ("boolean", "bool"):
            return 1
        else:
            raise NotImplementedError(f"Unknown data type: {data_type}")


class ETPClient(ETPSimpleClient):
    """
    High-level ETP (Energistics Transfer Protocol) client with advanced functionality.

    ETPClient extends ETPSimpleClient with additional methods for working with ETP data objects,
    dataspaces, data arrays, and transactions. It provides a comprehensive API for interacting
    with ETP servers in energy industry applications.

    Key Features:
    - All ETPSimpleClient functionality including event listener system
    - Data object management (get, put, delete)
    - Dataspace operations
    - Data array handling with support for large arrays
    - Transaction management (start, commit, rollback)
    - Resource discovery and supported types querying
    - Ping/pong connectivity testing
    - Authorization handling

    Inherited Event Listener System:
    ------------------------------
    ETPClient inherits the complete event listener paradigm from ETPSimpleClient.
    You can register listeners for connection events, errors, messages, and lifecycle events.

    Available Event Types (from EventType enum):
    - ON_OPEN: WebSocket connection established
    - ON_CLOSE: WebSocket connection closed
    - ON_ERROR: Error occurred
    - ON_MESSAGE: Message received
    - START: Client starting
    - STOP: Client stopping
    - CLOSE: Client closing

    Example with Event Listeners:
    ```python
    from py_etp_client.etpclient import ETPClient
    from py_etp_client.etpsimpleclient import EventType

    def handle_events(event_type: EventType, **kwargs):
        if event_type == EventType.ON_ERROR:
            print(f"ETP Error: {kwargs.get('error')}")
        elif event_type == EventType.ON_MESSAGE:
            print(f"ETP Message received")

    client = ETPClient(url="wss://example.com", spec=None)
    client.add_listener(EventType.ON_ERROR, handle_events)
    client.add_listener(EventType.ON_MESSAGE, handle_events)

    # Use high-level methods
    client.start()
    dataspaces = client.get_dataspaces()
    ```

    Transaction Support:
    -------------------
    ETPClient provides transaction management for operations that need to be atomic:
    - start_transaction(): Begin a new transaction
    - commit_transaction(): Commit the current transaction
    - rollback_transaction(): Rollback the current transaction

    Data Management:
    ---------------
    - get_data_objects(): Retrieve data objects by URI
    - put_data_objects(): Store data objects
    - delete_data_objects(): Remove data objects
    - get_data_arrays(): Retrieve data arrays
    - put_data_arrays(): Store data arrays

    See ETPSimpleClient documentation for detailed information about the event listener system.
    """

    def __init__(
        self,
        url: Optional[str] = None,
        spec: Optional[ETPConnection] = None,
        access_token: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        headers: Optional[Union[dict, str]] = None,
        verify: Optional[Any] = None,
        req_session: Optional[RequestSession] = None,
        config: Optional[Union[ETPConfig, ServerConfig, AuthConfig]] = None,
    ):
        """
        Initialize the ETPClient with connection parameters.

        ETPClient extends ETPSimpleClient with high-level data management operations
        while inheriting the complete event listener system. All listener functionality
        from the parent class is available (add_listener, remove_listener, EventType enum).

        Args:
            url: WebSocket URL to connect to
            spec: ETPConnection specification to use
            access_token: Access token for authentication (optional)
            username: Username for basic authentication (optional, ignored if access_token provided)
            password: Password for basic authentication (optional, ignored if access_token provided)
            headers: Additional headers for WebSocket request (optional), parsed as JSON if string
            verify: SSL verification options (optional)
            req_session: RequestSession object to use (optional, default created if None)

        Example:
            ```python
            from py_etp_client.etpclient import ETPClient
            from py_etp_client.etpsimpleclient import EventType

            def error_handler(event_type: EventType, **kwargs):
                print(f"Error: {kwargs.get('error')}")

            client = ETPClient(url="wss://server.com", spec=None)
            client.add_listener(EventType.ON_ERROR, error_handler)
            ```
        """
        super().__init__(
            url=url,
            spec=spec,
            access_token=access_token,
            username=username,
            password=password,
            headers=headers,
            verify=verify,
            req_session=req_session,
            config=config,
        )

        self.active_transaction = None

    def start_and_wait_connected(self, timeout: int = 10) -> bool:
        """Start the client and wait until connected or timeout.

        Args:
            timeout (int, optional): Maximum time to wait for connection in seconds. Defaults to 10.
        Returns:
            bool: True if the client is connected, False if timeout occurs.
        """
        self.start()
        start_time = perf_counter()
        while not self.is_connected() and perf_counter() - start_time < timeout:
            sleep(0.25)
        return self.is_connected()

    #    ______
    #   / ____/___  ________
    #  / /   / __ \/ ___/ _ \
    # / /___/ /_/ / /  /  __/
    # \____/\____/_/   \___/

    def ping(self, timeout: int = 5) -> bool:
        """Ping the server.

        Args:
            timeout (Optional[int], optional): Defaults to 5.

        Returns:
            bool: True if the server is reachable
        """
        ping_msg_list = self.send_and_wait(Ping(currentDateTime=epoch()), timeout=timeout)
        for ping_msg in ping_msg_list:
            if isinstance(ping_msg.body, ProtocolException):
                return False
        return True

    def authorize(
        self, authorization: str, supplementalAuthorization: Optional[dict] = None, timeout: int = 5
    ) -> Optional[Union[AuthorizeResponse, ProtocolException]]:
        """Authorize the client.

        Args:
            authorization (str): Authorization string
            supplementalAuthorization (dict): Supplemental authorization string

        Returns:
            Optional[Union[AuthorizeResponse, ProtocolException]]: Returns the authorization response or a ProtocolException if an error occurs
        """
        auth_msg_list = self.send_and_wait(
            Authorize(authorization=authorization, supplementalAuthorization=supplementalAuthorization or {}),
            timeout=timeout,
        )
        body = auth_msg_list[0].body
        if isinstance(body, (AuthorizeResponse, ProtocolException)):
            return body
        return None

    #     ____        __
    #    / __ \____ _/ /_____ __________  ____ _________
    #   / / / / __ `/ __/ __ `/ ___/ __ \/ __ `/ ___/ _ \
    #  / /_/ / /_/ / /_/ /_/ (__  ) /_/ / /_/ / /__/  __/
    # /_____/\__,_/\__/\__,_/____/ .___/\__,_/\___/\___/
    #                           /_/
    def get_dataspaces(self, timeout: int = 5) -> Union[List[Dataspace], ProtocolException]:
        """Get dataspaces list.

        Args:
            timeout (Optional[int], optional): Defaults to 5.

        Returns:
            List[Dataspace]: List of dataspaces
        """
        gdr_msg_list = self.send_and_wait(get_dataspaces(), timeout=timeout)

        datasapaces = []
        for gdr_msg in gdr_msg_list:
            if isinstance(gdr_msg.body, GetDataspacesResponse):
                datasapaces.extend(gdr_msg.body.dataspaces)
            elif isinstance(gdr_msg.body, ProtocolException):
                return gdr_msg.body
        return datasapaces

    def put_dataspace(
        self, dataspace_names: T_UriSingleOrGrouped, custom_data=None, timeout: int = 5
    ) -> Union[Dict[str, Any], ProtocolException]:
        """
        @deprecated: Use put_dataspaces_with_acl instead.
        Put dataspaces.

        /!\\ In the future, for OSDU RDDMS, custom data will HAVE to contains acl and legalTags

        Args:
            dataspace_names (Union[str, ETPUri, List[str], List[ETPUri], Dict[str, str], Dict[str, ETPUri]]): List of dataspace names
            timeout (Optional[int], optional): Defaults to 5.
        """
        # dataspace_names = reshape_uris_as_str_list(dataspace_names)
        logging.warning("In the future, for OSDU RDDMS, custom data will HAVE to contains acl and legalTags")
        pdm_msg_list = self.send_and_wait(
            put_dataspace(dataspace_names=dataspace_names, custom_data=custom_data), timeout=timeout
        )
        res = {}
        for pdm in pdm_msg_list:
            if isinstance(pdm.body, PutDataspacesResponse):
                res.update(pdm.body.success)
            elif isinstance(pdm.body, ProtocolException):
                return pdm.body
            else:
                logging.error("Error: %s", pdm.body)
        return res

    def put_dataspaces_with_acl(
        self,
        dataspace_names: T_UriSingleOrGrouped,
        acl_owners: Union[str, List[str]],
        acl_viewers: Union[str, List[str]],
        legal_tags: Union[str, List[str]],
        other_relevant_data_countries: Union[str, List[str]],
        timeout: int = 5,
    ) -> Union[Dict[str, Any], ProtocolException]:
        """Put dataspaces with ACL and legal tags.
        /!\\ In the future, for OSDU RDDMS, custom data will HAVE to contains acl and legalTags
        See. https://community.opengroup.org/osdu/platform/domain-data-mgmt-services/reservoir/open-etp-server/-/issues/168#note_370528
        and https://community.opengroup.org/osdu/platform/domain-data-mgmt-services/reservoir/open-etp-server#osdu-integration
        and https://community.opengroup.org/osdu/platform/domain-data-mgmt-services/reservoir/open-etp-server/-/blob/main/docs/bestPracticesForClients.md?ref_type=heads

        Args:
            dataspace_names (Union[str, ETPUri, List[str], List[ETPUri], Dict[str, str], Dict[str, ETPUri]]): List of dataspace names
            acl_owners (Union[str, List[str]]): a list of owners or a json representation of a list of owners
            acl_viewers (Union[str, List[str]]): a list of viewers or a json representation of a list of viewers
            legal_tags (Union[str, List[str]]): a list of legal tags or a json representation of a list of legal tags
            other_relevant_data_countries (Union[str, List[str]]): a list of other relevant data countries or a json representation of a list of other relevant data countries
            timeout (Optional[int], optional): _description_. Defaults to 5.

        Returns:
            Union[Dict[str, Any], ProtocolException]:
        """
        dataspace_names = reshape_uris_as_str_dict(dataspace_names)

        # Checking ACLs
        if isinstance(acl_owners, str):
            owners_obj = json.loads(acl_owners)
            if isinstance(owners_obj, list):
                acl_owners = owners_obj
            else:
                acl_owners = [acl_owners]

        # if isinstance(acl_owners, list):
        # acl_owners = json.dumps(acl_owners)

        if isinstance(acl_viewers, str):
            viewers_obj = json.loads(acl_viewers)
            if isinstance(viewers_obj, list):
                acl_viewers = viewers_obj
            else:
                acl_viewers = [acl_viewers]

        # if isinstance(acl_viewers, list):
        # acl_viewers = json.dumps(acl_viewers)

        # Checking legal tags
        if isinstance(legal_tags, str):
            legal_tags_obj = json.loads(legal_tags)
            if isinstance(legal_tags_obj, list):
                legal_tags = legal_tags_obj
            else:
                legal_tags = [legal_tags]

        # if isinstance(legal_tags, list):
        # legal_tags = json.dumps(legal_tags)

        # Checking other relevant data countries
        if isinstance(other_relevant_data_countries, str):
            other_relevant_data_countries_obj = json.loads(other_relevant_data_countries)
            if isinstance(other_relevant_data_countries_obj, list):
                other_relevant_data_countries = other_relevant_data_countries_obj
            else:
                other_relevant_data_countries = [other_relevant_data_countries]

        # if isinstance(other_relevant_data_countries, list):
        #     other_relevant_data_countries = json.dumps(other_relevant_data_countries)

        logging.info(
            f"Creating dataspaces: {dataspace_names} with custom data: %s",
            json.dumps(
                {
                    "viewers": acl_viewers,
                    "owners": acl_owners,
                    "legaltags": legal_tags,
                    "otherRelevantDataCountries": other_relevant_data_countries,
                }
            ),
        )
        return self.put_dataspace(
            dataspace_names=dataspace_names,
            custom_data={
                "viewers": acl_viewers,
                "owners": acl_owners,
                "legaltags": legal_tags,
                "otherRelevantDataCountries": other_relevant_data_countries,
            },
            timeout=timeout,
        )

    def delete_dataspace(
        self, dataspace_names: T_UriSingleOrGrouped, timeout: int = 5
    ) -> Union[Dict[str, Any], ProtocolException]:
        """Delete dataspaces.

        Args:
            dataspace_names (Union[str, ETPUri, List[str], List[ETPUri], Dict[str, str], Dict[str, ETPUri]]): List of dataspace names
            timeout (Optional[int], optional): Defaults to 5.
        """
        dataspace_names = reshape_uris_as_str_dict(dataspace_names)

        ddm_msg_list = self.send_and_wait(DeleteDataspaces(uris=dataspace_names), timeout=timeout)
        res = {}
        for ddm in ddm_msg_list:
            if isinstance(ddm.body, DeleteDataspacesResponse):
                res.update(ddm.body.success)
            elif isinstance(ddm.body, ProtocolException):
                return ddm.body
            else:
                logging.error("Error: %s", ddm.body)
        return res

    #     ____  _
    #    / __ \(_)_____________ _   _____  _______  __
    #   / / / / / ___/ ___/ __ \ | / / _ \/ ___/ / / /
    #  / /_/ / (__  ) /__/ /_/ / |/ /  __/ /  / /_/ /
    # /_____/_/____/\___/\____/|___/\___/_/   \__, /
    #                                        /____/

    def get_resources(
        self,
        uri: Optional[Union[str, ETPUri]] = None,
        depth: int = 1,
        scope: str = "self",
        types_filter: Optional[List[str]] = None,
        include_edges: bool = False,
        timeout=10,
    ) -> Union[List[Resource], ProtocolException]:
        """Get resources from the server.

        Args:
            uris (Union[str, ETPUri]): Uri of the object
            depth (int): Depth of the search
            scope (str): "self"|"targets"|"sources"|"sources_or_self"|"targets_or_self". Default is "self"
            types_filter (List[str]): Types of the objects
            timeout (int, optional): Defaults to 10.

        Returns:
            List[Resource]: List of resources
        """
        gr_msg_list = self.send_and_wait(
            get_resources(get_valid_uri_str(uri), depth, scope, types_filter, include_edges=include_edges),
            timeout=timeout,
        )

        resources = []
        for gr in gr_msg_list:
            if isinstance(gr.body, GetResourcesResponse):
                resources.extend(gr.body.resources)
            elif isinstance(gr.body, ProtocolException):
                return gr.body
            else:
                logging.error("Error: %s", gr.body)
        return resources

    def get_all_related_objects_uris(
        self, uri: T_UriSingleOrGrouped, scope: str = "target", timeout: int = 5
    ) -> List[str]:
        """Get all related objects uris from the server.

        Args:
            uri (Union[str, ETPUri, List[str], List[ETPUri], Dict[str, str], Dict[str, ETPUri]]): Uri of the object
            timeout (int, optional): Defaults to 5.

        Returns:
            List[str]: List of uris
        """
        allready_checked = []
        to_check: List[str] = reshape_uris_as_str_list(uri)

        while len(to_check) > 0:
            uri = to_check.pop(0)
            allready_checked.append(str(uri))
            resources = self.get_resources(uri=uri, depth=2, scope=scope, timeout=timeout)
            for r in resources:
                if isinstance(r, Resource):
                    try:
                        if r.uri not in allready_checked and r.uri not in to_check:
                            to_check.append(r.uri)
                    except Exception as e:
                        logging.error("Error: %s", e)
                        continue
                else:
                    logging.error("Error: %s", r)
                    continue

        return allready_checked

    def search_resource(self, dataspace: Union[str, ETPUri], uuid: str, timeout: int = 5) -> List[str]:
        """Search for a resource in the server.

        Args:
            dataspace (Union[str, ETPUri]): Dataspace name
            uuid (str): UUID of the object
            timeout (int, optional): Defaults to 5.

        Returns:
            List[str]: List of uris
        """
        resources = self.get_resources(uri=get_valid_uri_str(dataspace), timeout=timeout)
        uris = []
        for r in resources:
            if isinstance(r, Resource) and uuid in r.uri:
                try:
                    uris.append(r.uri)
                except Exception as e:
                    logging.error("Error: %s", e)
                    continue
            else:
                logging.error("Error: %s", r)
                continue
        return uris

    #    _____ __
    #   / ___// /_____  ________
    #   \__ \/ __/ __ \/ ___/ _ \
    #  ___/ / /_/ /_/ / /  /  __/
    # /____/\__/\____/_/   \___/

    def get_data_object(
        self, uris: T_UriSingleOrGrouped, format_: str = "xml", timeout: int = 5
    ) -> Optional[Union[Dict[str, str], List[str], str, ProtocolException]]:
        """Get data object from the server.

        Args:
            uris (Union[str, ETPUri, List[str], List[ETPUri], Dict[str, str], Dict[str, ETPUri]]]): Uri(s) of the objects
            format (str, optional): "xml" | "json". Defaults to "xml".
            timeout (Optional[int], optional): Defaults to 5.

        Raises:
            ValueError: if uris is not a string, a dict or a list of strings

        Returns:
            Union[Dict[str, str], List[str], str]: Returns a dict of uris and data if uris is a dict, a list of data if uris is a list, or a single data if uris is a string
        """
        uris_dict = reshape_uris_as_str_dict(uris)

        gdor_msg_list = self.send_and_wait(GetDataObjects(uris=uris_dict, format=format_), timeout=timeout)
        data_obj = {}

        for gdor in gdor_msg_list:
            if isinstance(gdor.body, GetDataObjectsResponse):
                data_obj.update({k: v.data for k, v in gdor.body.data_objects.items()})
            elif isinstance(gdor.body, ProtocolException):
                # logging.error("Error: %s", gdor.body)
                return gdor.body

        res = None
        if len(data_obj) > 0:
            if isinstance(uris, str):
                res = data_obj["0"]
            elif isinstance(uris, dict):
                res = {k: data_obj[k] for k in uris.keys()}
            elif isinstance(uris, list):
                res = [data_obj[str(i)] for i in range(len(uris))]

        return res

    def get_data_object_as_obj(
        self, uris: T_UriSingleOrGrouped, format_: str = "xml", timeout: int = 5
    ) -> Union[Dict[str, Any], List[Any], Any, ProtocolException]:
        """Get data object as a deserialized object.

        Args:
            uris (Union[str, ETPUri, List[str], List[ETPUri], Dict[str, str], Dict[str, ETPUri]]): The URIs of the data objects to retrieve.
            format_ (str, optional): The format of the data objects. Defaults to "xml".
            timeout (int, optional): The timeout for the request. Defaults to 5.

        Returns:
            Union[Dict[str, Any], List[Any], Any, ProtocolException]: The deserialized data objects or an error.
        """

        # TODO : test if energyml.resqml or energyml.witsml exists in the dependencies
        objs = self.get_data_object(
            uris=uris,
            format_=format_,
            timeout=timeout,
        )

        if isinstance(objs, str) or isinstance(objs, bytes):
            return read_energyml_obj(objs, format_)
        elif isinstance(objs, dict):
            for k, v in objs.items():
                objs[k] = read_energyml_obj(v, format_)
        elif isinstance(objs, list):
            for i, v in enumerate(objs):
                objs[i] = read_energyml_obj(v, format_)
        # else:
        # raise ValueError("data must be a string, a dict or a list of strings")
        return objs

    def put_data_object_str(
        self,
        obj_content: Union[str, List[str]],
        dataspace_name: Optional[Union[str, ETPUri]] = None,
        format: str = "xml",
        timeout: int = 5,
    ) -> Dict[str, Any]:
        """Put data object to the server.

        Args:
            obj_content (Union[str, List[str]]): An xml or json representation of an energyml object.
            dataspace_name (Union[str, ETPUri]): Dataspace name
            timeout (int, optional): Defaults to 5.
        """
        if isinstance(obj_content, dict):
            obj_content = list(obj_content.values())  # type: ignore
        elif not isinstance(obj_content, list):
            obj_content = [obj_content]

        do_dict = {}
        for o in obj_content:
            do_dict[str(len(do_dict))] = create_data_object(
                obj_as_str=o, dataspace_name=get_valid_uri_str(dataspace_name), format=format
            )

        # do_dict = {"0": create_data_object(obj_as_str=obj_content, dataspace_name=dataspace_name)}

        pdor_msg_list = self.send_and_wait(PutDataObjects(dataObjects=do_dict), timeout=timeout)

        res = {}
        for pdor in pdor_msg_list:
            if isinstance(pdor.body, PutDataObjectsResponse):
                res.update(pdor.body.success)
            else:
                logging.error("Error: %s", pdor.body)
        return res

    def put_data_object_obj(
        self, obj: Union[Any, List[Any]], dataspace_name: str, format_: str = "xml", timeout: int = 5
    ) -> Dict[str, Any]:
        """Put data object to the server.

        Args:
            obj (Any): An object (or a list of objects) that must be an instance of a class from energyml.(witsml|resqml|prodml|eml) python module or at least having the similar attributes, OR a list of such objects.
            dataspace_name (str): Dataspace name
            timeout (int, optional): Defaults to 5.
        """
        if isinstance(obj, dict):
            obj = list(obj.values())  # type: ignore
        elif not isinstance(obj, list):
            obj = [obj]

        do_dict = {}
        for o in obj:
            do_dict[str(len(do_dict))] = create_data_object(obj=o, dataspace_name=dataspace_name, format=format_)

        pdor_msg_list = self.send_and_wait(PutDataObjects(dataObjects=do_dict), timeout=timeout)

        res = {}
        for pdor in pdor_msg_list:
            if isinstance(pdor.body, PutDataObjectsResponse):
                res.update(pdor.body.success)
            else:
                logging.error("Error: %s", pdor.body)
        return res

    def put_data_object_file(
        self, file_path: Union[List[str], str], dataspace_name: Optional[Union[str, ETPUri]] = None, timeout: int = 5
    ):
        """Put data object to the server.

        Args:
            file_path (Union[List[str], str]): Path to the file(s) to be uploaded
            dataspace_name (Union[str, ETPUri]): Dataspace name
            timeout (int, optional): Defaults to 5.
        """
        dataspace_name = get_valid_uri_str(dataspace_name)
        if isinstance(file_path, str):
            file_path = [file_path]

        file_path_checked = []
        for f in file_path:
            if os.path.exists(f):
                if os.path.isfile(f) and (f.endswith(".xml") or f.endswith(".json") or f.endswith(".epc")):
                    file_path_checked.append(f)
                elif os.path.isdir(f):
                    for root, _, files in os.walk(f):
                        for file in files:
                            if file.endswith(".xml") or file.endswith(".json") or file.endswith(".epc"):
                                file_path_checked.append(os.path.join(root, file))

        logging.info("Files to be uploaded: %s", file_path_checked)
        do_dict = {}
        for f in file_path_checked:
            flw = f.lower()
            if flw.endswith(".xml") or flw.endswith(".json"):
                with open(f, "r") as file:
                    file_content = file.read()
                    do_dict[len(do_dict)] = create_data_object(
                        obj_as_str=file_content,
                        dataspace_name=get_valid_uri_str(dataspace_name),
                        format="xml" if flw.endswith(".xml") else "json",
                    )
            elif flw.endswith(".epc"):
                epc = Epc.read_file(f)
                if epc is not None:
                    for obj in epc.energyml_objects:
                        if obj is not None:
                            do_dict[len(do_dict)] = create_data_object(obj=obj, dataspace_name=dataspace_name)
                else:
                    logging.error("Error: Cannot read EPC file %s", f)
                    continue

        pdor_msg_list = self.send_and_wait(PutDataObjects(dataObjects=do_dict), timeout=timeout)

        res = {}
        for pdor in pdor_msg_list:
            if isinstance(pdor.body, PutDataObjectsResponse):
                res.update(pdor.body.success)
            elif isinstance(pdor.body, ProtocolException):
                if len(pdor_msg_list) == 1 and len(pdor.body.errors) == 0:
                    return pdor.body
                res.update(pdor.body.errors)
            else:
                logging.error("Error: %s", pdor.body)
        return res

    def delete_data_object(self, uris: T_UriSingleOrGrouped, timeout: int = 5) -> Dict[str, Any]:
        """Delete data object from the server.

        Args:
            uris (Union[str, ETPUri, List[str], List[ETPUri], Dict[str, str], Dict[str, ETPUri]]): Uri(s) of the objects
            timeout (Optional[int], optional): Defaults to 5.

        Raises:
            ValueError: if uris is not a string, a dict or a list of strings

        Returns:
            Dict[str, Any]: A map of uri and a boolean indicating if the object has been successfully deleted
        """
        uris_dict = reshape_uris_as_str_dict(uris)

        gdor_msg_list = self.send_and_wait(DeleteDataObjects(uris=uris_dict), timeout=timeout)
        res = {}
        for gdor in gdor_msg_list:
            if isinstance(gdor.body, DeleteDataObjectsResponse):
                res.update(gdor.body.deleted_uris)
            else:
                logging.error("Error: %s", gdor.body)
        return res

    #     ____        __        ___
    #    / __ \____ _/ /_____ _/   |  ______________ ___  __
    #   / / / / __ `/ __/ __ `/ /| | / ___/ ___/ __ `/ / / /
    #  / /_/ / /_/ / /_/ /_/ / ___ |/ /  / /  / /_/ / /_/ /
    # /_____/\__,_/\__/\__,_/_/  |_/_/  /_/   \__,_/\__, /
    #                                              /____/

    def get_data_array(self, uri: Union[str, ETPUri], path_in_resource: str, timeout: int = 5) -> Optional[np.ndarray]:
        """Get an array from the server.

        Args:
            uri (Union[str, ETPUri]): Usually the uri should be an uri of an ExternalDataArrayPart or an ExternalPartReference.
            path_in_resource (str): path to the array. Must be the same than in the original object
            timeout (int, optional): Defaults to 5.

        Returns:
            np.ndarray: the array, reshaped in the correct dimension
        """
        uri = get_valid_uri_str(uri)
        gdar_msg_list = self.send_and_wait(
            GetDataArrays(dataArrays={"0": DataArrayIdentifier(uri=uri, pathInResource=path_in_resource)}),
            timeout=timeout,
        )
        array = None
        for gdar in gdar_msg_list:
            if isinstance(gdar.body, GetDataArraysResponse) and "0" in gdar.body.data_arrays:
                # print(gdar)
                if array is None:
                    array = np.array(gdar.body.data_arrays["0"].data.item.values).reshape(  # type: ignore
                        tuple(gdar.body.data_arrays["0"].dimensions)  # type: ignore
                    )
                else:
                    array = np.concatenate(
                        (
                            array,
                            np.array(gdar.body.data_arrays["0"].data.item.values).reshape(  # type: ignore
                                tuple(gdar.body.data_arrays["0"].dimensions)  # type: ignore
                            ),
                        )
                    )
            else:
                logging.error("@get_data_array Error: %s", gdar.body)
        return array

    def get_data_subarray(
        self, uri: Union[str, ETPUri], path_in_resource: str, start: List[int], count: List[int], timeout: int = 5
    ) -> Optional[np.ndarray]:
        """Get a sub part of an array from the server.

        Args:
            uri (Union[str, ETPUri]): Usually the uri should be an uri of an ExternalDataArrayPart or an ExternalPartReference.
            path_in_resource (str): path to the array. Must be the same than in the original object
            start (List[int]): start indices in each dimensions.
            count (List[int]): Count of element in each dimensions.
            timeout (int, optional): Defaults to 5.

        Returns:
            Optional[np.ndarray]: the array, NOT reshaped in the correct dimension. The result is a flat array !
        """
        start = [int(s) for s in start]
        count = [int(c) for c in count]
        gdar_msg_list = self.send_and_wait(
            GetDataSubarrays(
                dataSubarrays={
                    "0": GetDataSubarraysType(
                        uid=DataArrayIdentifier(uri=get_valid_uri_str(uri), pathInResource=path_in_resource),
                        starts=start,  # type: ignore
                        counts=count,  # type: ignore
                    )
                }
            ),
            timeout=timeout,
        )
        array = None
        for gdar in gdar_msg_list:
            if isinstance(gdar.body, GetDataSubarraysResponse) and "0" in gdar.body.data_subarrays:
                # print(gdar)
                if array is None:
                    array = np.array(gdar.body.data_subarrays["0"].data.item.values)  # type: ignore
                else:
                    array = np.concatenate(
                        (array, np.array(gdar.body.data_subarrays["0"].data.item.values)),  # type: ignore
                    )
            else:
                logging.error("Error: %s", gdar.body)
        return array

    def get_data_array_metadata(
        self, uri: Union[str, ETPUri], path_in_resource: str, timeout: int = 5
    ) -> Dict[str, DataArrayMetadata]:
        """Get metadata of an array from the server.

        Args:
            uri (Union[str, ETPUri]): Usually the uri should be an uri of an ExternalDataArrayPart or an ExternalPartReference.
            path_in_resource (str): path to the array. Must be the same than in the original object
            timeout (int, optional): Defaults to 5.

        Returns:
            Dict[str, Any]: metadata of the array
        """
        gdar_msg_list = self.send_and_wait(
            GetDataArrayMetadata(
                dataArrays={"0": DataArrayIdentifier(uri=get_valid_uri_str(uri), pathInResource=path_in_resource)}
            ),
            timeout=timeout,
        )
        metadata = {}
        for gdar in gdar_msg_list:
            if isinstance(gdar.body, GetDataArrayMetadataResponse):
                metadata.update(gdar.body.array_metadata)
            else:
                logging.error("Error: %s", gdar.body)
        return metadata

    def put_uninitialized_data_array(
        self,
        uri: Union[str, ETPUri],
        path_in_resource: str,
        dimensions: List[int],
        data_type: Union[str, AnyArrayType] = "float64",
        logical_array_type: AnyLogicalArrayType = AnyLogicalArrayType.ARRAY_OF_FLOAT32_BE,
        custom_data: Optional[Dict[str, Any]] = None,
        preffered_subarray_dimensions: Optional[List[int]] = None,
        timeout: int = 5,
    ) -> bool:
        """Put an uninitialized data array to the server.

        Args:
            uri (Union[str, ETPUri]): Usually the uri should be an uri of an ExternalDataArrayPart or an ExternalPartReference.
            path_in_resource (str): path to the array. Must be the same than in the original object
            dimensions (List[int]): dimensions of the array (as list of int)
            data_type (str, optional): Data type of the array. Defaults to "float64".
            timeout (int, optional): Defaults to 5.

        Returns:
            bool: True if the array has been successfully put
        """

        print(" datatype", data_type if isinstance(data_type, AnyArrayType) else get_any_array_type(data_type))
        uri = get_valid_uri_str(uri)
        pdar_msg_list = self.send_and_wait(
            PutUninitializedDataArrays(
                dataArrays={
                    "0": PutUninitializedDataArrayType(
                        uid=DataArrayIdentifier(uri=uri, pathInResource=path_in_resource),
                        metadata=DataArrayMetadata(
                            dimensions=dimensions,  # type: ignore
                            transportArrayType=(
                                data_type if isinstance(data_type, AnyArrayType) else get_any_array_type(data_type)
                            ),
                            logicalArrayType=logical_array_type,
                            storeLastWrite=epoch(),
                            storeCreated=epoch(),
                            customData=custom_data or {},
                            preferredSubarrayDimensions=preffered_subarray_dimensions or [],  # type: ignore
                        ),
                    )
                }
            ),
            timeout=timeout,
        )

        for pdar in pdar_msg_list:
            if isinstance(pdar.body, PutUninitializedDataArraysResponse):
                print(pdar.body)
                return pdar.body.success.get("0", None) is not None
            else:
                logging.error("Error: %s", pdar.body)
        return False

    def put_data_array(
        self,
        uri: Union[str, ETPUri],
        path_in_resource: str,
        array: Union[np.ndarray, list],
        dimensions: Union[List[int], Tuple[int, ...]],
        timeout: int = 5,
    ) -> Dict[str, bool]:
        """Put a data array to the server.

        Args:
            uri (Union[str, ETPUri]): Usually the uri should be an uri of an ExternalDataArrayPart or an ExternalPartReference.
            path_in_resource (str): path to the array. Must be the same than in the original object
            array (Union[np.array, list]): a flat array
            dimensions (List[int]): dimensions of the array (as list of int)
            timeout (int, optional): Defaults to 5.

        Returns:
            (Dict[str, bool]): A map of uri and a boolean indicating if the array has been successfully put
        """
        if isinstance(dimensions, tuple):
            dimensions = list(dimensions)

        pdar_msg_list = self.send_and_wait(
            PutDataArrays(
                dataArrays={
                    "0": PutDataArraysType(
                        uid=DataArrayIdentifier(uri=get_valid_uri_str(uri), pathInResource=path_in_resource),
                        array=DataArray(dimensions=dimensions, data=get_any_array(array)),  # type: ignore
                    )
                }
            ),
            timeout=timeout,
        )

        res = {}
        for pdar in pdar_msg_list:
            if isinstance(pdar.body, PutDataArraysResponse):
                res.update(pdar.body.success)
            else:
                logging.info("Data array put failed: %s ==> %s", pdar, pdar.body)

        return res

    def put_data_subarray(
        self,
        uri: Union[str, ETPUri],
        path_in_resource: str,
        array: Union[np.ndarray, list],
        start: List[int],
        count: List[int],
        timeout: int = 5,
    ) -> Optional[Union[PutDataSubarraysResponse, ProtocolException]]:
        """Put a sub part of a data array to the server.

        Args:
            uri (Union[str, ETPUri]): Usually the uri should be an uri of an ExternalDataArrayPart or an ExternalPartReference.
            path_in_resource (str): path to the array. Must be the same than in the original object
            array (Union[np.array, list]): a flat array
            start (List[int]): start indices in each dimensions.
            count (List[int]): Count of element in each dimensions.
            timeout (int, optional): Defaults to 5.

        Returns:
            (Optional[Union[PutDataSubarraysResponse, ProtocolException]]): A map of uri and a boolean indicating if the sub array has been successfully put
        """

        # Convert all elements in count and start to built-in int (avoid numpy types for pydantic)
        count_py = [int(x) for x in count]
        start_py = [int(x) for x in start]
        psar_msg_list = self.send_and_wait(
            PutDataSubarrays(
                dataSubarrays={
                    "0": PutDataSubarraysType(
                        uid=DataArrayIdentifier(uri=get_valid_uri_str(uri), pathInResource=path_in_resource),
                        data=get_any_array(array),
                        starts=start_py,  # type: ignore
                        counts=count_py,  # type: ignore
                    )
                }
            ),
            timeout=timeout,
        )

        for psar in psar_msg_list:
            if isinstance(psar.body, PutDataSubarraysResponse):
                return psar.body
            elif isinstance(psar.body, ProtocolException):
                return psar.body
            else:
                logging.info("Data subarray put failed: %s ==> %s", psar, psar.body)

        return None

    def put_data_array_safe(
        self,
        uri: Union[str, ETPUri],
        path_in_resource: str,
        array: np.ndarray,
        max_subarray_size: Optional[int] = None,
        timeout: int = 5,
    ) -> Optional[Dict[str, bool]]:
        """Put a data array to the server.
        If the array overflow the maximum message size, it will be split in several subarrays and put using multiple PutDataSubarrays messages.

        Args:
            uri (Union[str, ETPUri]): Usually the uri should be an uri of an ExternalDataArrayPart or an ExternalPartReference.
            path_in_resource (str): path to the array. Must be the same than in the original object
            array (np.ndarray): a flat array,
            max_subarray_size (Optional[int], optional): Maximum size of a subarray in bytes. If None, the value of the server capability "MaxWebSocketMessagePayloadSize" will be used. Defaults to None.
            timeout (int, optional): Defaults to 5.

        Returns:
            Optional[Dict[str, bool]]: A map of uri and a boolean indicating if the array has been successfully put
        """
        uri = get_valid_uri_str(uri)
        if not isinstance(array, np.ndarray):
            array = np.asarray(array)
        total_size_bytes = array.nbytes
        max_msg_size = (
            max_subarray_size
            or self.spec.client_info.getCapability("MaxWebSocketMessagePayloadSize")  # type: ignore
            or 1048576
        )  # 1 MB by default
        logging.info(f"Array size: {total_size_bytes} bytes, Max message size: {max_msg_size} bytes")
        if total_size_bytes <= max_msg_size:
            # The array can be sent in a single PutDataArrays message
            dimensions = list(array.shape)
            return self.put_data_array(
                uri=uri,
                path_in_resource=path_in_resource,
                array=array.flatten(),
                dimensions=dimensions,
                timeout=timeout,
            )
        else:
            # The array must be split in several subarrays and sent using multiple PutDataSubarrays messages
            logging.info("Array is too large to be sent in a single message, splitting it in subarrays...")
            dimensions = list(array.shape)
            data_type = str(array.dtype)
            type_size = get_type_size(data_type)
            if type_size is None:
                logging.error(f"Cannot determine size of data type {data_type}")
                return None
            logging.info(f"Array dimensions: {dimensions}, Data type: {data_type}, Type size: {type_size} bytes")
            # Now, we can determine how to split the array in subarrays
            # We will try to split the array along the first dimension
            dim0 = dimensions[0]
            other_dims = dimensions[1:]
            other_dims_size = np.prod(other_dims) if len(other_dims) > 0 else 1
            max_dim0_count = max_msg_size // (other_dims_size * type_size)
            if max_dim0_count > dim0:
                max_dim0_count = dim0
            if max_dim0_count == 0:
                logging.error(
                    "Cannot split array, max message size is too small for the array dimensions and data type"
                )
                return None
            logging.info(f"Splitting array along first dimension in chunks of {max_dim0_count} (total {dim0} chunks)")

            # Starting by putting an uninitialized data array
            if not self.put_uninitialized_data_array(
                uri=uri,
                path_in_resource=path_in_resource,
                data_type=data_type,
                dimensions=dimensions,
                timeout=timeout,
            ):
                logging.error(f"Failed to put uninitialized data array for {uri}")
                return None
            logging.info(f"Uninitialized data array put successfully for {uri}")

            # Now, we can send the array in chunks using PutDataSubarrays messages
            res = {}
            nb_splits = (dim0 + max_dim0_count - 1) // max_dim0_count
            logging.info(f"Sending array in {nb_splits} subarrays...")
            for start0 in range(0, dim0, max_dim0_count):
                count0 = min(max_dim0_count, dim0 - start0)
                start = [start0] + [0] * (len(dimensions) - 1)
                count = [count0] + other_dims
                subarray = array[start0 : start0 + count0].flatten()
                logging.info(
                    f"[{start0 // max_dim0_count} / {nb_splits}] Sending subarray starting at {start} with count {count} (size {subarray.nbytes} bytes)"
                )
                psar_response = self.put_data_subarray(
                    uri=uri,
                    path_in_resource=path_in_resource,
                    array=subarray,
                    start=start,
                    count=count,  # type: ignore
                    timeout=timeout,
                )
                if psar_response is None or (isinstance(psar_response, ProtocolException)):
                    logging.error(f"Failed to put subarray starting at {start} with count {count}: {psar_response}")
                    res[uri] = False
                    break
                else:
                    res[uri] = True

            return res if len(res) > 0 else None

    def get_data_array_safe(
        self,
        uri: Union[str, ETPUri],
        path_in_resource: str,
        max_subarray_size: Optional[int] = None,
        timeout: int = 20,
    ) -> Optional[np.ndarray]:
        """Get a data array from the server.
        After getting data array metadata, the array is retrieved in multiple subarrays using multiple GetDataSubarrays messages if necessary.
        Args:
            uri (Union[str, ETPUri]): Usually the uri should be an uri of an ExternalDataArrayPart or an ExternalPartReference for resqml 2.0.1, and the uri of the object itself for resqml > 2.0.1.
            path_in_resource (str): path to the array. Must be the same than in the original object
            max_subarray_size (Optional[int], optional): Maximum size of a subarray in bytes. If None, the value of the server capability "MaxWebSocketMessagePayloadSize" will be used. Defaults to None.
            timeout (int, optional): Defaults to 20.
        Returns:
            Optional[np.ndarray]: the array, reshaped in the correct dimension
        """
        uri = get_valid_uri_str(uri)
        metadata_dict = self.get_data_array_metadata(uri=uri, path_in_resource=path_in_resource, timeout=timeout)
        if "0" not in metadata_dict:
            logging.error(f"No metadata found for data array {uri} {path_in_resource}")
            return None
        metadata = metadata_dict["0"]
        if metadata.dimensions is None or len(metadata.dimensions) == 0:
            logging.error(f"No dimensions found in metadata for data array {uri} {path_in_resource}")
            return None
        dimensions = metadata.dimensions  # type: ignore
        if metadata.transport_array_type is None:
            logging.error(f"No transportArrayType found in metadata for data array {uri} {path_in_resource}")
            return None
        data_type = metadata.transport_array_type
        type_size = get_any_array_type_size(data_type)
        if type_size is None:
            logging.error(f"Cannot determine size of data type {data_type}")
            return None
        total_size_bytes = type_size * np.prod(dimensions)
        max_msg_size = (
            max_subarray_size
            or self.spec.client_info.getCapability("MaxWebSocketMessagePayloadSize")  # type: ignore
            or 1048576
        )  # 1 MB by default
        logging.info(f"Array size: {total_size_bytes} bytes, Max message size: {max_msg_size} bytes")
        if total_size_bytes <= max_msg_size:
            # The array can be retrieved in a single GetDataArrays message
            return self.get_data_array(uri=uri, path_in_resource=path_in_resource, timeout=timeout)
        else:
            # The array must be retrieved in several subarrays using multiple GetDataSubarrays messages
            logging.info("Array is too large to be retrieved in a single message, splitting it in subarrays...")
            dimensions = list(dimensions)
            # Now, we can determine how to split the array in subarrays
            # We will try to split the array along the first dimension
            dim0 = dimensions[0]
            other_dims = dimensions[1:]
            other_dims_size = np.prod(other_dims) if len(other_dims) > 0 else 1  # type: ignore
            max_dim0_count = max_msg_size // (other_dims_size * type_size)
            if max_dim0_count > dim0:  # type: ignore
                max_dim0_count = dim0
            if max_dim0_count == 0:
                logging.error(
                    "Cannot split array, max message size is too small for the array dimensions and data type"
                )
                return None
            logging.info(f"Splitting array along first dimension in chunks of {max_dim0_count} (total {dim0} chunks)")

            # Now, we can get the array in chunks using GetDataSubarrays messages
            array = None
            nb_splits = (dim0 + max_dim0_count - 1) // max_dim0_count  # type: ignore
            logging.info(f"Retrieving array in {nb_splits} subarrays...")
            for start0 in range(0, dim0, max_dim0_count):  # type: ignore
                logging.debug("Progress: %d / %d", start0 // max_dim0_count, nb_splits)  # type: ignore
                count0 = min(max_dim0_count, dim0 - start0)  # type: ignore
                start = [start0] + [0] * (len(dimensions) - 1)
                count = [count0] + other_dims
                logging.info(
                    f"[{start0 // max_dim0_count} / {nb_splits}] Retrieving subarray starting at {start} with count {count}"  # type: ignore
                )
                subarray = self.get_data_subarray(
                    uri=uri,
                    path_in_resource=path_in_resource,
                    start=start,
                    count=count,  # type: ignore
                    timeout=timeout,
                )
                if subarray is None:
                    logging.error(f"Failed to get subarray starting at {start} with count {count}")
                    return None
                if array is None:
                    array = subarray
                else:
                    array = np.concatenate((array, subarray))  # type: ignore

            if array is not None:
                return array.reshape(tuple(dimensions))  # type: ignore
            else:
                return None

    #    _____                              __           __   ______
    #   / ___/__  ______  ____  ____  _____/ /____  ____/ /  /_  __/_  ______  ___  _____
    #   \__ \/ / / / __ \/ __ \/ __ \/ ___/ __/ _ \/ __  /    / / / / / / __ \/ _ \/ ___/
    #  ___/ / /_/ / /_/ / /_/ / /_/ / /  / /_/  __/ /_/ /    / / / /_/ / /_/ /  __(__  )
    # /____/\__,_/ .___/ .___/\____/_/   \__/\___/\__,_/    /_/  \__, / .___/\___/____/
    #           /_/   /_/                                       /____/_/

    def get_supported_types(
        self, uri: Union[str, ETPUri], count: bool = True, return_empty_types: bool = True, scope: str = "self"
    ):
        """Get supported types.

        Args:
            uri (Union[str, ETPUri]): uri
            count (bool, optional): Defaults to True.
            return_empty_types (bool, optional): Defaults to True.
            scope (str, optional): Defaults to "self".

        Returns:
            [type]: [description]
        """
        gdar_msg_list = self.send_and_wait(
            get_supported_types(
                uri=get_valid_uri_str(uri), count=count, return_empty_types=return_empty_types, scope=scope
            )
        )

        supported_types = []
        for gdar in gdar_msg_list:
            if isinstance(gdar.body, GetSupportedTypesResponse):
                supported_types.extend(gdar.body.supported_types)
            else:
                logging.error("Error: %s", gdar.body)
        return supported_types

    #   ______                                 __  _
    #  /_  __/________ _____  _________ ______/ /_(_)___  ____
    #   / / / ___/ __ `/ __ \/ ___/ __ `/ ___/ __/ / __ \/ __ \
    #  / / / /  / /_/ / / / (__  ) /_/ / /__/ /_/ / /_/ / / / /
    # /_/ /_/   \__,_/_/ /_/____/\__,_/\___/\__/_/\____/_/ /_/

    def start_transaction(
        self, dataspace: T_UriSingleOrGrouped, readonly: bool = False, msg: str = "", timeout: int = 5
    ) -> Optional[Uuid]:
        """Start a transaction.

        Args:
            dataspace (Union[str, ETPUri, List[str], List[ETPUri], Dict[str, str], Dict[str, ETPUri]]]): Dataspace name or list of dataspace names
            or list of dataspace uris. If a list is provided, the transaction will be started on all the dataspaces.
            timeout (int, optional): Defaults to 5.

        Returns:
            int: transaction id
        """

        dataspaceUris = reshape_uris_as_str_list(dataspace)

        if self.active_transaction is not None:
            logging.warning("A transaction is already active, please commit it before starting a new one")
            return self.active_transaction
        else:
            str_msg_list = self.send_and_wait(
                StartTransaction(
                    dataspaceUris=dataspaceUris,  # type: ignore
                    message=msg,
                    readOnly=readonly,
                ),
                timeout=timeout,
            )

            transaction_id = None
            for str_msg in str_msg_list:
                if isinstance(str_msg.body, StartTransactionResponse) and str_msg.body.successful:
                    transaction_id = str_msg.body.transaction_uuid
                    self.active_transaction = transaction_id
                    return transaction_id
                else:
                    logging.error("Error: %s", str_msg.body)
            return None

    def rollback_transaction(self, timeout: int = 5) -> bool:
        """Rollback a transaction.

        Args:
            timeout (int, optional): Defaults to 5.

        Returns:
            bool: True if the transaction has been successfully rolled back
        """
        if self.active_transaction is None:
            logging.warning("No active transaction to rollback")
        else:
            rtr_msg_list = self.send_and_wait(
                RollbackTransaction(transactionUuid=self.active_transaction), timeout=timeout
            )
            for rtr_msg in rtr_msg_list:
                if isinstance(rtr_msg.body, RollbackTransactionResponse) and rtr_msg.body.successful:
                    self.active_transaction = None
                    return True
                else:
                    logging.error("Error: %s", rtr_msg.body)

        return False

    def commit_transaction(self, timeout: int = 5) -> bool:
        """Commit a transaction.

        Args:
            timeout (int, optional): Defaults to 5.

        Returns:
            bool: True if the transaction has been successfully committed
        """
        if self.active_transaction is None:
            logging.warning("No active transaction to commit")
        else:
            ctr_msg_list = self.send_and_wait(
                CommitTransaction(transactionUuid=self.active_transaction), timeout=timeout
            )
            for ctr_msg in ctr_msg_list:
                if isinstance(ctr_msg.body, CommitTransactionResponse) and ctr_msg.body.successful:
                    self.active_transaction = None
                    return True
                else:
                    logging.error("Error: %s", ctr_msg.body)

        return False

    def commit_transaction_get_msg(self, timeout: int = 5) -> Tuple[bool, Optional[str]]:
        """Commit a transaction.

        Args:
            timeout (int, optional): Defaults to 5.

        Returns:
            bool: True if the transaction has been successfully committed
        """
        if self.active_transaction is None:
            logging.warning("No active transaction to commit")
        else:
            ctr_msg_list = self.send_and_wait(
                CommitTransaction(transactionUuid=self.active_transaction), timeout=timeout
            )
            for ctr_msg in ctr_msg_list:
                if isinstance(ctr_msg.body, CommitTransactionResponse):
                    # if ctr_msg.body.successful:  # It seems that if the commit failed, the transaction is not active anymore (tested on OSDU RDDMS)
                    self.active_transaction = None
                    return ctr_msg.body.successful, ctr_msg.body.failure_reason
                else:
                    logging.error("Error: %s", ctr_msg.body)

        return False, None


def start_client(config: Optional[Union[ServerConfig, ETPConfig]] = None, verify: Optional[bool] = None) -> ETPClient:
    config = config or ServerConfig.from_file()

    if isinstance(config, ETPConfig):
        config = config.as_server_config()

    if verify is not None:
        config.verify_ssl = verify
    client = ETPClient(
        spec=ETPConnection(connection_type=ConnectionType.CLIENT),
        config=config,
    )
    client.start()

    start_time = perf_counter()
    while not client.is_connected() and perf_counter() - start_time < 5:
        sleep(0.25)
    if not client.is_connected():
        logging.info("The ETP session could not be established in 5 seconds.")
        raise Exception(f"Connexion not established with {config.url}")
    else:
        logging.info("Now connected to ETP Server")

    return client
