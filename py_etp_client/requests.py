# Copyright (c) 2022-2023 Geosiris.
# SPDX-License-Identifier: Apache-2.0
import logging
import traceback
from typing import Any, Dict, List, Type, Union, AsyncGenerator, Optional
import uuid as pyUUID

from etpproto.error import NotSupportedError
from etpproto.messages import Message

from etpproto.connection import CommunicationProtocol, ETPConnection
from etpproto.client_info import ClientInfo

from etpproto.protocols.core import CoreHandler
from etpproto.protocols.discovery import DiscoveryHandler
from etpproto.protocols.store import StoreHandler
from etpproto.protocols.data_array import DataArrayHandler
from etpproto.protocols.supported_types import SupportedTypesHandler
from etpproto.protocols.dataspace import DataspaceHandler
from etpproto.protocols.transaction import TransactionHandler
import numpy as np

from py_etp_client import (
    Acknowledge,
    AnyArrayType,
    ActiveStatusKind,
    AnyArray,
    ArrayOfBoolean,
    ArrayOfBytes,
    ArrayOfDouble,
    ArrayOfFloat,
    ArrayOfInt,
    ArrayOfLong,
    ArrayOfString,
    Authorize,
    AuthorizeResponse,
    CloseSession,
    CommitTransaction,
    CommitTransactionResponse,
    Contact,
    ContextInfo,
    ContextScopeKind,
    DataObject,
    Dataspace,
    DataValue,
    DeleteDataObjects,
    DeleteDataObjectsResponse,
    DeleteDataspaces,
    DeleteDataspacesResponse,
    GetDataArrayMetadata,
    GetDataArrayMetadataResponse,
    GetDataArrays,
    GetDataArraysResponse,
    GetDataObjects,
    GetDataObjectsResponse,
    GetDataspaces,
    GetDataspacesResponse,
    GetDataSubarrays,
    GetDataSubarraysResponse,
    GetDeletedResources,
    GetDeletedResourcesResponse,
    GetResources,
    GetResourcesResponse,
    GetSupportedTypes,
    GetSupportedTypesResponse,
    OpenSession,
    Ping,
    Pong,
    ProtocolException,
    PutDataArrays,
    PutDataArraysResponse,
    PutDataObjects,
    PutDataObjectsResponse,
    PutDataspaces,
    PutDataspacesResponse,
    RelationshipKind,
    RequestSession,
    Resource,
    RollbackTransaction,
    RollbackTransactionResponse,
    ServerCapabilities,
    StartTransaction,
    StartTransactionResponse,
    SupportedDataObject,
    SupportedProtocol,
    Version,
)

from energyml.utils.constants import epoch, gen_uuid, date_to_epoch
from energyml.utils.introspection import (
    get_obj_uri,
    get_obj_uuid,
    get_object_attribute,
    search_attribute_matching_type,
)
from energyml.utils.epc import get_property_kind_by_uuid
from energyml.utils.uri import parse_uri
from energyml.utils.serialization import (
    read_energyml_xml_str,
    read_energyml_json_str,
    serialize_json,
    serialize_xml,
    read_energyml_xml_bytes,
    read_energyml_json_bytes,
    JSON_VERSION,
)

from py_etp_client.utils import (
    T_UriSingleOrGrouped,
    get_valid_uri_str,
    reshape_uris_as_str_dict,
    reshape_uris_as_str_list,
)


def read_energyml_obj(data: Union[str, bytes], format_: str) -> Any:
    if isinstance(data, str):
        if format_ == "xml":
            return read_energyml_xml_str(data)
        elif format_ == "json":
            return read_energyml_json_str(data)
    elif isinstance(data, bytes):
        if format_ == "xml":
            return read_energyml_xml_bytes(data)
        elif format_ == "json":
            return read_energyml_json_bytes(data, json_version=JSON_VERSION.OSDU_OFFICIAL)
    else:
        raise ValueError("data must be a string or bytes")


def get_scope(scope: str):
    if scope is not None:
        scope_lw = scope.lower()
        if "target" in scope_lw:
            if "self" in scope_lw:
                return ContextScopeKind.TARGETS_OR_SELF
            else:
                return ContextScopeKind.TARGETS
        elif "source" in scope_lw:
            if "self" in scope_lw:
                return ContextScopeKind.SOURCES_OR_SELF
            else:
                return ContextScopeKind.SOURCES
    return ContextScopeKind.SELF


#    ______
#   / ____/___  ________
#  / /   / __ \/ ___/ _ \
# / /___/ /_/ / /  /  __/
# \____/\____/_/   \___/

etp_version = Version(major=1, minor=2, revision=0, patch=0)


def default_request_session():
    rq = RequestSession(
        applicationName="Geosiris etp client",
        applicationVersion="0.1.0",
        clientInstanceId=gen_uuid(),  # type: ignore
        requestedProtocols=list(
            filter(
                lambda sp: sp.protocol != 0,
                [
                    SupportedProtocol(
                        protocol=cp.value,
                        protocolVersion=etp_version,
                        role="store" if cp.value != 1 else "producer",
                        protocolCapabilities={},
                    )
                    # for cp in CommunicationProtocol
                    for cp in ETPConnection.transition_table.keys()
                ],
            )
        ),  # ETPConnection.server_capabilities.supported_protocols
        supportedDataObjects=ETPConnection.server_capabilities.supported_data_objects,  # type: ignore
        supportedCompression=ETPConnection.server_capabilities.supported_compression,  # type: ignore
        supportedFormats=ETPConnection.server_capabilities.supported_formats,  # type: ignore
        currentDateTime=epoch(),
        endpointCapabilities={},
        earliestRetainedChangeTime=0,
    )
    return rq


#     ____  _
#    / __ \(_)_____________ _   _____  _______  __
#   / / / / / ___/ ___/ __ \ | / / _ \/ ___/ / / /
#  / /_/ / (__  ) /__/ /_/ / |/ /  __/ /  / /_/ /
# /_____/_/____/\___/\____/|___/\___/_/   \__, /
#                                        /____/


def get_resources(
    uri: Optional[str] = "eml:///",
    depth: int = 1,
    scope: str = "self",
    data_object_types: Optional[List[str]] = None,
    include_edges: bool = False,
):
    uri = get_valid_uri_str(uri)
    return GetResources(
        context=ContextInfo(
            uri=uri,
            depth=depth,
            dataObjectTypes=data_object_types or [],  # type: ignore
            navigableEdges=RelationshipKind.PRIMARY,
        ),
        scope=get_scope(scope),
        countObjects=False,
        storeLastWriteFilter=None,
        activeStatusFilter=ActiveStatusKind.INACTIVE,
        includeEdges=include_edges,
    )


def get_deleted_resources(
    dataspace: str,
    delete_time_filter: Optional[int] = None,
    data_object_types: list = [],
):
    ds_uri = get_valid_uri_str(dataspace)
    return GetDeletedResources(
        dataspaceUri=ds_uri,
        deleteTimeFilter=delete_time_filter,  # type: ignore
        dataObjectTypes=data_object_types,
    )


#     ____        __
#    / __ \____ _/ /_____ __________  ____ _________
#   / / / / __ `/ __/ __ `/ ___/ __ \/ __ `/ ___/ _ \
#  / /_/ / /_/ / /_/ /_/ (__  ) /_/ / /_/ / /__/  __/
# /_____/\__,_/\__/\__,_/____/ .___/\__,_/\___/\___/
#                           /_/


def get_dataspaces():
    return GetDataspaces(storeLastWriteFilter=None)


def put_dataspace(dataspace_names: T_UriSingleOrGrouped, custom_data: Optional[dict] = None) -> PutDataspaces:
    """Create or update dataspace(s).

    Args:
        dataspace_names (T_UriSingleOrGrouped): The name(s) of the dataspace(s) to create or update.
        custom_data (Optional[dict], optional): Custom data to include in the request. Defaults to None.

    Returns:
        PutDataspaces: The PutDataspaces request object.
    """
    ds_map = {}
    now = epoch()

    dataspace_names = reshape_uris_as_str_dict(dataspace_names)

    custom_data_reshaped = None
    if custom_data is not None:
        custom_data_reshaped = {}
        for key, value in custom_data.items():
            if isinstance(value, list) or isinstance(value, np.ndarray):
                custom_data_reshaped[key] = DataValue(item=get_any_array(array=value).item)
            else:
                custom_data_reshaped[key] = DataValue(item=value)

    for k, ds_uri in dataspace_names.items():
        ds_uri_etp = parse_uri(ds_uri)
        ds_map[k] = Dataspace(
            uri=ds_uri,
            storeLastWrite=now,
            storeCreated=now,
            path=ds_uri_etp.dataspace or "",
            customData=custom_data_reshaped or {},
        )

    print(f"custom_data_reshaped: {custom_data_reshaped}")

    print(PutDataspaces(dataspaces=ds_map).json())

    return PutDataspaces(dataspaces=ds_map)


#    _____ __
#   / ___// /_____  ________
#   \__ \/ __/ __ \/ ___/ _ \
#  ___/ / /_/ /_/ / /  /  __/
# /____/\__/\____/_/   \___/


def delete_data_object(uris: T_UriSingleOrGrouped):
    return DeleteDataObjects(
        uris=reshape_uris_as_str_dict(uris),
        pruneContainedObjects=False,
    )


def _create_resource(obj: Any, dataspace_name: Optional[str] = None) -> Resource:
    ds_name = parse_uri(get_valid_uri_str(dataspace_name)).dataspace if dataspace_name is not None else None

    uri = str(get_obj_uri(obj, ds_name))

    nb_ref = len(search_attribute_matching_type(obj, "DataObjectReference", return_self=False))
    print("Sending data object at uri ", uri, "nbref : ", nb_ref)
    date = epoch()

    last_changed = date
    try:
        last_changed = date_to_epoch(get_object_attribute(obj, "LastUpdate"))
    except:
        pass

    return Resource(
        uri=uri,
        name=get_object_attribute(obj, "Citation.Title"),
        sourceCount=0,  # type: ignore
        targetCount=nb_ref,  # type: ignore
        lastChanged=last_changed,
        storeLastWrite=date,
        storeCreated=date,
        activeStatus=ActiveStatusKind.ACTIVE,
        alternateUris=[],
        customData={},
    )


def create_data_object(
    obj: Optional[Any] = None, obj_as_str: Optional[str] = None, format="xml", dataspace_name: Optional[str] = None
):
    if obj is None and obj_as_str is None:
        raise ValueError("Either obj or obj_as_str must be provided")
    elif obj is None and obj_as_str is not None:
        obj = read_energyml_obj(obj_as_str, format_=format)
    elif obj_as_str is None:
        if format == "json":
            obj_as_str = serialize_json(obj)
        else:
            obj_as_str = serialize_xml(obj)
    if isinstance(obj, list):  # in case of json parsing
        if len(obj) == 0:
            raise ValueError("obj cannot be an empty list")
        obj = obj[0]
    print(get_obj_uuid(obj))
    return DataObject(
        data=obj_as_str.encode("utf-8") if isinstance(obj_as_str, str) else obj_as_str,
        blobId=pyUUID.UUID(get_obj_uuid(obj)).hex,  # type: ignore
        resource=_create_resource(obj=obj, dataspace_name=dataspace_name),
        format=format,
    )


def get_property_kind_and_parents(uuids: list) -> Dict[str, Any]:
    """Get PropertyKind objects and their parents from a list of UUIDs.

    Args:
        uuids (list): List of PropertyKind UUIDs.

    Returns:
        Dict[str, Any]: A dictionary mapping UUIDs to PropertyKind objects and their parents.
    """
    dict_props: Dict[str, Any] = {}

    for prop_uuid in uuids:
        prop = get_property_kind_by_uuid(prop_uuid)
        if prop is not None:
            dict_props[prop_uuid] = prop
            parent_uuid = get_object_attribute(prop, "parent.uuid")
            if parent_uuid is not None and parent_uuid not in dict_props:
                print(f"Adding parent {parent_uuid} for property {prop_uuid}")
                dict_props = get_property_kind_and_parents([parent_uuid]) | dict_props
        else:
            logging.warning(f"PropertyKind with UUID {prop_uuid} not found.")
            continue
    return dict_props


#     ___
#    /   |  ______________ ___  _______
#   / /| | / ___/ ___/ __ `/ / / / ___/
#  / ___ |/ /  / /  / /_/ / /_/ (__  )
# /_/  |_/_/  /_/   \__,_/\__, /____/
#                        /____/


def get_array_class_from_dtype(
    dtype: str,
) -> Type[Union[ArrayOfInt, ArrayOfLong, ArrayOfBoolean, ArrayOfFloat, ArrayOfDouble, ArrayOfBytes, ArrayOfString]]:
    dtype_str = str(dtype)
    # print("dtype_str", dtype_str)
    if dtype_str.startswith("long") or dtype_str.startswith("int64"):
        return ArrayOfLong
    elif dtype_str.startswith("int") or dtype_str.startswith("unsign") or dtype_str.startswith("uint"):
        return ArrayOfInt
    elif dtype_str.startswith("bool"):
        return ArrayOfBoolean
    elif dtype_str.startswith("double") or dtype_str.startswith("float64"):
        return ArrayOfDouble
    elif dtype_str.startswith("float"):
        return ArrayOfFloat
    elif dtype_str.startswith("bytes") or dtype_str.startswith("|S"):
        return ArrayOfBytes
    elif dtype_str.startswith("str") or dtype_str.startswith("<U"):
        return ArrayOfString
    return ArrayOfFloat


def get_any_array_type(
    dtype: str,
) -> AnyArrayType:
    dtype_str = str(dtype)
    # print("dtype_str", dtype_str)
    if dtype_str.startswith("long") or dtype_str.startswith("int64"):
        return AnyArrayType.ARRAY_OF_LONG
    elif dtype_str.startswith("int") or dtype_str.startswith("unsign") or dtype_str.startswith("uint"):
        return AnyArrayType.ARRAY_OF_INT
    elif dtype_str.startswith("bool"):
        return AnyArrayType.ARRAY_OF_BOOLEAN
    elif dtype_str.startswith("double") or dtype_str.startswith("float64"):
        return AnyArrayType.ARRAY_OF_DOUBLE
    elif dtype_str.startswith("float"):
        return AnyArrayType.ARRAY_OF_FLOAT
    elif dtype_str.startswith("bytes") or dtype_str.startswith("|S"):
        return AnyArrayType.BYTES
    elif dtype_str.startswith("str") or dtype_str.startswith("<U"):
        return AnyArrayType.ARRAY_OF_STRING
    return AnyArrayType.ARRAY_OF_FLOAT


def get_any_array_type_size(
    dtype: AnyArrayType,
) -> int:
    if dtype == AnyArrayType.ARRAY_OF_LONG or dtype == AnyArrayType.ARRAY_OF_DOUBLE:
        return 8
    elif dtype == AnyArrayType.ARRAY_OF_INT or dtype == AnyArrayType.ARRAY_OF_FLOAT:
        return 4
    elif (
        dtype == AnyArrayType.ARRAY_OF_BOOLEAN or dtype == AnyArrayType.BYTES or dtype == AnyArrayType.ARRAY_OF_STRING
    ):
        return 1
    return 4


def get_any_array(
    array: Union[List[Any], np.ndarray],
) -> AnyArray:
    """Get an AnyArray instance from an array

    Args:
        array (Union[List[Any], np.ndarray]): an array.

    Returns:
        AnyArray: The AnyArray instance
    """
    if not isinstance(array, np.ndarray):
        # logging.debug("@get_any_array: was not an array")
        array = np.array(array)
    array = array.flatten()
    # logging.debug("\t@get_any_array: type array : %s", type(array.tolist()))
    # logging.debug("\t@get_any_array: type inside : %s", type(array.tolist()[0]))
    return AnyArray(item=get_array_class_from_dtype(str(array.dtype))(values=array.tolist()))  # type: ignore


#    _____                              __           __   __
#   / ___/__  ______  ____  ____  _____/ /____  ____/ /  / /___  ______  ___  _____
#   \__ \/ / / / __ \/ __ \/ __ \/ ___/ __/ _ \/ __  /  / __/ / / / __ \/ _ \/ ___/
#  ___/ / /_/ / /_/ / /_/ / /_/ / /  / /_/  __/ /_/ /  / /_/ /_/ / /_/ /  __(__  )
# /____/\__,_/ .___/ .___/\____/_/   \__/\___/\__,_/   \__/\__, / .___/\___/____/
#           /_/   /_/                                     /____/_/


def get_supported_types(
    uri: str,
    count: bool = True,
    return_empty_types: bool = True,
    scope: str = "self",
):
    uri = get_valid_uri_str(uri)
    if isinstance(count, str):
        count = count.lower() == "true"
    if isinstance(return_empty_types, str):
        return_empty_types = return_empty_types.lower() == "true"
    print(f"==>  uri={uri}, count={count}, return_empty_types={return_empty_types}")
    return GetSupportedTypes(
        uri=uri,
        countObjects=count,
        returnEmptyTypes=return_empty_types,
        scope=get_scope(scope),
    )


#  __________________
# /_____/_____/_____/


if __name__ == "__main__":
    print(get_any_array([1, 2, 3, 4, 5]))
    print(get_any_array(np.array([[1.52, 2, 3], [4, 5, 6]])))
    print(get_any_array(np.array([["1.52", "2", "3"], ["4", "5", "6"]])))
    print(get_any_array(np.array([True, False, True])))
    # print(get_any_array(np.array([b"hello", b"world"])))
