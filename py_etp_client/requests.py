# Copyright (c) 2022-2023 Geosiris.
# SPDX-License-Identifier: Apache-2.0
import logging
from typing import Any, List, Union, AsyncGenerator, Optional
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
from energyml.utils.uri import parse_uri
from energyml.utils.serialization import (
    read_energyml_xml_str,
    read_energyml_json_str,
    serialize_json,
    serialize_xml,
    read_energyml_xml_bytes,
    read_energyml_json_bytes,
)


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
        clientInstanceId=gen_uuid(),
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
        supportedDataObjects=ETPConnection.server_capabilities.supported_data_objects,
        supportedCompression=ETPConnection.server_capabilities.supported_compression,
        supportedFormats=ETPConnection.server_capabilities.supported_formats,
        currentDateTime=epoch(),
        endpointCapabilities={},
        earliest_retained_change_time=0,
    )
    return rq


#     ____  _
#    / __ \(_)_____________ _   _____  _______  __
#   / / / / / ___/ ___/ __ \ | / / _ \/ ___/ / / /
#  / /_/ / (__  ) /__/ /_/ / |/ /  __/ /  / /_/ /
# /_____/_/____/\___/\____/|___/\___/_/   \__, /
#                                        /____/


def get_resources(
    uri: str = "eml:///",
    depth: int = 1,
    scope=None,
    data_object_types: Optional[List[str]] = None,
):
    if uri is not None:
        if not uri.startswith("eml:///"):
            uri = f"eml:///dataspace('{uri}')"
    else:
        uri = "eml:///"
    return GetResources(
        context=ContextInfo(
            uri=uri,
            depth=depth,
            dataObjectTypes=data_object_types or [],
            navigableEdges=RelationshipKind.PRIMARY,
        ),
        scope=get_scope(scope),
        countObjects=False,
        storeLastWriteFilter=None,
        activeStatusFilter=ActiveStatusKind.INACTIVE,
        includeEdges=False,
    )


def get_deleted_resources(
    dataspace: str,
    delete_time_filter: int = None,
    data_object_types: list = [],
):
    ds_uri = "eml:///dataspace('" + dataspace + "')" if "eml:///" not in dataspace else dataspace
    return GetDeletedResources(
        dataspace_uri=ds_uri,
        delete_time_filter=delete_time_filter,
        data_object_types=data_object_types,
    )


#     ____        __
#    / __ \____ _/ /_____ __________  ____ _________
#   / / / / __ `/ __/ __ `/ ___/ __ \/ __ `/ ___/ _ \
#  / /_/ / /_/ / /_/ /_/ (__  ) /_/ / /_/ / /__/  __/
# /_____/\__,_/\__/\__,_/____/ .___/\__,_/\___/\___/
#                           /_/


def get_dataspaces():
    return GetDataspaces()


def put_dataspace(dataspace_names: list, custom_data: dict = None):
    ds_map = {}
    now = epoch()

    custom_data_reshaped = None
    if custom_data is not None:
        custom_data_reshaped = {}
        for key, value in custom_data.items():
            if isinstance(value, list) or isinstance(value, np.ndarray):
                custom_data_reshaped[key] = DataValue(item=get_any_array(array=value).item)
            else:
                custom_data_reshaped[key] = DataValue(item=value)

    for ds_name in dataspace_names:
        ds_map[str(len(ds_map))] = Dataspace(
            uri=("eml:///dataspace('" + ds_name + "')" if "eml:///" not in ds_name else ds_name),
            store_last_write=now,
            store_created=now,
            path=ds_name,
            custom_data=custom_data_reshaped or {},
        )

    return PutDataspaces(dataspaces=ds_map)


def delete_dataspace(dataspace_names: list):
    ds_map = {}
    for ds_name in dataspace_names:
        ds_map[str(len(ds_map))] = "eml:///dataspace('" + ds_name + "')" if "eml:///" not in ds_name else ds_name
    return DeleteDataspaces(uris=ds_map)


#    _____ __
#   / ___// /_____  ________
#   \__ \/ __/ __ \/ ___/ _ \
#  ___/ / /_/ /_/ / /  /  __/
# /____/\__/\____/_/   \___/


def delete_data_object(uris: list):
    return DeleteDataObjects(
        uris={i: uris[i] for i in range(len(uris))},
        prune_contained_objects=False,
    )


def _create_resource(obj: Any, dataspace_name: str = None) -> Resource:
    ds_name = dataspace_name
    if "eml:///" in ds_name:
        ds_name = parse_uri(ds_name).dataspace

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
        source_count=0,
        target_count=nb_ref,
        last_changed=last_changed,
        store_last_write=date,
        store_created=date,
        active_status=ActiveStatusKind.ACTIVE,
        alternate_uris=[],
        custom_data={},
    )


def _create_data_object(
    obj: Optional[Any] = None, obj_as_str: Optional[str] = None, format="xml", dataspace_name: str = None
):
    if obj is None and obj_as_str is None:
        raise ValueError("Either obj or obj_as_str must be provided")
    if obj is None:
        try:
            if isinstance(obj_as_str, bytes):
                obj = read_energyml_xml_bytes(obj_as_str)
            else:
                obj = read_energyml_xml_str(obj_as_str)
        except:
            if isinstance(obj_as_str, bytes):
                obj = read_energyml_json_bytes(obj_as_str)
            else:
                obj = read_energyml_json_str(obj_as_str)[0]
            format = "json"
    elif obj_as_str is None:
        if format == "json":
            obj_as_str = serialize_json(obj)
        else:
            obj_as_str = serialize_xml(obj)

    return DataObject(
        data=obj_as_str,
        blobId=pyUUID.UUID(get_obj_uuid(obj)).hex,
        resource=_create_resource(obj=obj, dataspace_name=dataspace_name),
        format=format,
    )


#     ___
#    /   |  ______________ ___  _______
#   / /| | / ___/ ___/ __ `/ / / / ___/
#  / ___ |/ /  / /  / /_/ / /_/ (__  )
# /_/  |_/_/  /_/   \__,_/\__, /____/
#                        /____/


def get_array_class_from_dtype(
    dtype: str,
) -> Union[ArrayOfInt, ArrayOfLong, ArrayOfBoolean, ArrayOfFloat, ArrayOfDouble, ArrayOfBytes, ArrayOfString]:
    dtype_str = str(dtype)
    print("dtype_str", dtype_str)
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
    return AnyArray(item=get_array_class_from_dtype(str(array.dtype))(values=array.tolist()))


if __name__ == "__main__":
    print(get_any_array([1, 2, 3, 4, 5]))
    print(get_any_array(np.array([[1.52, 2, 3], [4, 5, 6]])))
    print(get_any_array(np.array([["1.52", "2", "3"], ["4", "5", "6"]])))
    print(get_any_array(np.array([True, False, True])))
    # print(get_any_array(np.array([b"hello", b"world"])))


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
    if not uri.startswith("eml:///"):
        uri = f"eml:///dataspace('{uri}')"
    if isinstance(count, str):
        count = count.lower() == "true"
    if isinstance(return_empty_types, str):
        return_empty_types = return_empty_types.lower() == "true"
    print(f"==>  uri={uri}, count={count}, return_empty_types={return_empty_types}")
    return GetSupportedTypes(
        uri=uri,
        count_objects=count,
        return_empty_types=return_empty_types,
        scope=get_scope(scope),
    )
