# Copyright (c) 2022-2023 Geosiris.
# SPDX-License-Identifier: Apache-2.0
from typing import Union, AsyncGenerator, Optional
from datetime import datetime
import uuid as pyUUID
import pprint
import json
import logging


# from geoetp.etp.etp_data_bridge import ETPDataBridge
# from geoetp.etp.hsds_bridge import HSDSBridge

from py_etp_client import (
    Resource,
    Dataspace,
    OpenSession,
    CloseSession,
    Ping,
    Pong,
    Authorize,
    AuthorizeResponse,
    GetResourcesResponse,
    GetResourcesEdgesResponse,
    GetDeletedResourcesResponse,
    Acknowledge,
    DeleteDataspaces,
    GetDataspaces,
    PutDataspaces,
    DeleteDataspacesResponse,
    GetDataspacesResponse,
    RequestSession,
    PutDataspacesResponse,
    GetDataObjects,
    PutDataObjects,
    DeleteDataObjects,
    GetDataObjectsResponse,
    PutDataObjectsResponse,
    DeleteDataObjectsResponse,
    GetDataArrayMetadata,
    GetDataArrayMetadataResponse,
    GetDataArrays,
    GetDataSubarrays,
    GetDataArraysResponse,
    GetDataSubarraysResponse,
    PutDataArrays,
    PutDataArraysResponse,
    GetSupportedTypes,
    GetSupportedTypesResponse,
    ProtocolException,
    CommitTransaction,
    CommitTransactionResponse,
    RollbackTransaction,
    RollbackTransactionResponse,
    StartTransaction,
    StartTransactionResponse,
    ServerCapabilities,
    SupportedProtocol,
    SupportedDataObject,
    DataValue,
    Contact,
    Version,
)
from etpproto.error import NotSupportedError
from etpproto.messages import Message
from etptypes.energistics.etp.v12.datatypes.message_header import MessageHeader

from etpproto.connection import CommunicationProtocol, Protocol, ETPConnection
from etpproto.client_info import ClientInfo

from etpproto.protocols.core import CoreHandler
from etpproto.protocols.discovery import DiscoveryHandler
from etpproto.protocols.store import StoreHandler
from etpproto.protocols.data_array import DataArrayHandler
from etpproto.protocols.supported_types import SupportedTypesHandler
from etpproto.protocols.dataspace import DataspaceHandler
from etpproto.protocols.transaction import TransactionHandler


pretty_p = pprint.PrettyPrinter(width=100, compact=True)

# etp_bridge = ETPDataBridge()

#    ______                                    __                   __
#   / ____/___  ________     ____  _________  / /_____  _________  / /
#  / /   / __ \/ ___/ _ \   / __ \/ ___/ __ \/ __/ __ \/ ___/ __ \/ /
# / /___/ /_/ / /  /  __/  / /_/ / /  / /_/ / /_/ /_/ / /__/ /_/ / /
# \____/\____/_/   \___/  / .___/_/   \____/\__/\____/\___/\____/_/
#                        /_/

__ENABLE__LOGS__ = True


def enable_logs(v: bool):
    global __ENABLE__LOGS__
    __ENABLE__LOGS__ = v


def log(*args, pretty: bool = False, **kwargs):
    if __ENABLE__LOGS__:
        if pretty:
            pretty_p.pprint(*args, **kwargs)
        else:
            logging.debug(*args, **kwargs)


def print_resource(res: Resource):
    log("Resource : %s", res.uri)
    log("\tSource count : %s", res.source_count)
    log("\tTarget count : %s", res.target_count)
    # log("\tLast change :", datetime.fromtimestamp(res.last_changed))


def print_dataspace(res: Dataspace):
    log("Dataspace : %s", res.uri)
    log("\tStore last write : %s", res.store_last_write)
    log("\tStore created : %s", res.store_created)
    log("\tPath : %s", res.path)
    log("\ttCustom data : %s", res.custom_data)
    # log("\tLast change :", datetime.fromtimestamp(res.last_changed))


def print_protocol_exception(pe: ProtocolException):
    if pe.error is not None:
        log("Error recieved : " + str(pe))
    elif len(pe.errors) > 0:
        log(f"Errors recieved ({pe.errors}): ")
        for code, err in pe.errors.items():
            log(f"\t{code}) {str(err)}")


@ETPConnection.on(CommunicationProtocol.CORE)
class CoreProtocolPrinter(CoreHandler):

    async def on_open_session(
        self,
        msg: OpenSession,
        msg_header: MessageHeader,
        client_info: Union[None, ClientInfo] = None,
    ) -> AsyncGenerator[Optional[Message], None]:
        log("OpenSession recieved")
        yield

    async def on_close_session(
        self,
        msg: CloseSession,
        msg_header: MessageHeader,
        client_info: Union[None, ClientInfo] = None,
    ) -> AsyncGenerator[Optional[Message], None]:
        log("@on_close_session")
        yield

    async def on_ping(
        self,
        msg: Ping,
        msg_header: MessageHeader,
        client_info: Union[None, ClientInfo] = None,
    ) -> AsyncGenerator[Optional[Message], None]:
        log("@on_ping")
        yield Message.get_object_message(
            Pong(currentDateTime=int(datetime.utcnow().timestamp())),
            correlation_id=msg_header.correlation_id,
        )

    async def on_pong(
        self,
        msg: Pong,
        msg_header: MessageHeader,
        client_info: Union[None, ClientInfo] = None,
    ) -> AsyncGenerator[Optional[Message], None]:
        log("@on_pong")
        yield

    async def on_protocol_exception(
        self,
        msg: ProtocolException,
        msg_header: MessageHeader,
        client_info: Union[None, ClientInfo] = None,
    ) -> AsyncGenerator[Optional[Message], None]:
        print_protocol_exception(msg)
        yield

    async def on_authorize(
        self,
        msg: Authorize,
        msg_header: MessageHeader,
        client_info: Union[None, ClientInfo] = None,
    ) -> AsyncGenerator[Optional[Message], None]:
        yield NotSupportedError().to_etp_message(correlation_id=msg_header.message_id)

    async def on_authorize_response(
        self,
        msg: AuthorizeResponse,
        msg_header: MessageHeader,
        client_info: Union[None, ClientInfo] = None,
    ) -> AsyncGenerator[Optional[Message], None]:
        log(f"AuthorizeResponse {msg.json()}")
        yield


#     ____  _                                         ____             __                   __
#    / __ \(_)_____________ _   _____  _______  __   / __ \_________  / /_____  _________  / /
#   / / / / / ___/ ___/ __ \ | / / _ \/ ___/ / / /  / /_/ / ___/ __ \/ __/ __ \/ ___/ __ \/ /
#  / /_/ / (__  ) /__/ /_/ / |/ /  __/ /  / /_/ /  / ____/ /  / /_/ / /_/ /_/ / /__/ /_/ / /
# /_____/_/____/\___/\____/|___/\___/_/   \__, /  /_/   /_/   \____/\__/\____/\___/\____/_/
#                                        /____/


@ETPConnection.on(CommunicationProtocol.DISCOVERY)
class DiscoveryProtocolPrinter(DiscoveryHandler):
    async def on_get_resources_response(
        self,
        msg: GetResourcesResponse,
        msg_header: MessageHeader,
        client_info: Union[None, ClientInfo] = None,
    ) -> AsyncGenerator[Optional[Message], None]:
        log(
            f"## myDiscoveryProtocol ## on_get_resources_response : nb[{len(msg.resources)}]",
        )
        for res in msg.resources:
            print_resource(res)
        yield

    async def on_protocol_exception(
        self,
        msg: ProtocolException,
        msg_header: MessageHeader,
        client_info: Union[None, ClientInfo] = None,
    ) -> AsyncGenerator[Optional[Message], None]:
        print_protocol_exception(msg)
        yield

    async def on_get_deleted_resources_response(
        self,
        msg: GetDeletedResourcesResponse,
        msg_header: MessageHeader,
        client_info: Union[None, ClientInfo] = None,
    ) -> AsyncGenerator[Optional[Message], None]:
        if msg is not None:
            if len(msg.deleted_resources) > 0:
                log(f"Deleted object list ({len(msg.deleted_resources)}) : ")
                for dr in msg.deleted_resources:
                    log(f"\t{dr.uri} \tdeleted_time: \t{dr.deleted_time}")
            else:
                log("No deleted resource found for this context")

        yield

    async def on_get_resources_edges_response(
        self,
        msg: GetResourcesEdgesResponse,
        msg_header: MessageHeader,
        client_info: Union[None, ClientInfo] = None,
    ) -> AsyncGenerator[Optional[Message], None]:
        for edge in msg.edges:
            log(f"Edge from {edge.source_uri} to {edge.target_uri} with type {edge.relationship_kind}")
        yield

    async def on_acknowledge(
        self,
        msg: Acknowledge,
        msg_header: MessageHeader,
        client_info: Union[None, ClientInfo] = None,
    ) -> AsyncGenerator[Optional[Message], None]:
        log(f"Message recieved {msg}")
        yield


#     ____        __
#    / __ \____ _/ /_____ __________  ____ _________  _____
#   / / / / __ `/ __/ __ `/ ___/ __ \/ __ `/ ___/ _ \/ ___/
#  / /_/ / /_/ / /_/ /_/ (__  ) /_/ / /_/ / /__/  __(__  )
# /_____/\__,_/\__/\__,_/____/ .___/\__,_/\___/\___/____/
#                           /_/


@ETPConnection.on(CommunicationProtocol.DATASPACE)
class DataspaceHandlerPrinter(DataspaceHandler):
    async def on_delete_dataspaces(
        self,
        msg: DeleteDataspaces,
        msg_header: MessageHeader,
        client_info: Union[None, ClientInfo] = None,
    ) -> AsyncGenerator[Optional[Message], None]:
        log("@on_delete_dataspaces")
        yield

    async def on_get_dataspaces(
        self,
        msg: GetDataspaces,
        msg_header: MessageHeader,
        client_info: Union[None, ClientInfo] = None,
    ) -> AsyncGenerator[Optional[Message], None]:
        log("@on_get_dataspaces")
        yield

    async def on_put_dataspaces(
        self,
        msg: PutDataspaces,
        msg_header: MessageHeader,
        client_info: Union[None, ClientInfo] = None,
    ) -> AsyncGenerator[Optional[Message], None]:
        log("@on_put_dataspaces")
        yield

    async def on_delete_dataspaces_response(
        self,
        msg: DeleteDataspacesResponse,
        msg_header: MessageHeader,
        client_info: Union[None, ClientInfo] = None,
    ) -> AsyncGenerator[Optional[Message], None]:
        log("@on_delete_dataspaces_response")
        # log(msg, pretty=True)
        yield
        # raise NotSupportedError()

    async def on_get_dataspaces_response(
        self,
        msg: GetDataspacesResponse,
        msg_header: MessageHeader,
        client_info: Union[None, ClientInfo] = None,
    ) -> AsyncGenerator[Optional[Message], None]:
        log("@on_get_dataspaces_response")
        for dataspace in msg.dataspaces:
            print_dataspace(dataspace)
        yield
        # raise NotSupportedError()

    async def on_put_dataspaces_response(
        self,
        msg: PutDataspacesResponse,
        msg_header: MessageHeader,
        client_info: Union[None, ClientInfo] = None,
    ) -> AsyncGenerator[Optional[Message], None]:
        log(msg, pretty=True)
        yield
        # raise NotSupportedError()

    async def on_protocol_exception(
        self,
        msg: ProtocolException,
        msg_header: MessageHeader,
        client_info: Union[None, ClientInfo] = None,
    ) -> AsyncGenerator[Optional[Message], None]:
        print_protocol_exception(msg)

        yield


#    _____ __                     ____             __                   __
#   / ___// /_____  ________     / __ \_________  / /_____  _________  / /
#   \__ \/ __/ __ \/ ___/ _ \   / /_/ / ___/ __ \/ __/ __ \/ ___/ __ \/ /
#  ___/ / /_/ /_/ / /  /  __/  / ____/ /  / /_/ / /_/ /_/ / /__/ /_/ / /
# /____/\__/\____/_/   \___/  /_/   /_/   \____/\__/\____/\___/\____/_/


@ETPConnection.on(CommunicationProtocol.STORE)
class StoreProtocolPrinter(StoreHandler):
    async def on_get_data_objects(
        self,
        msg: GetDataObjects,
        msg_header: MessageHeader,
        client_info: Union[None, ClientInfo] = None,
    ) -> AsyncGenerator[Optional[Message], None]:
        log("@on_get_data_objects")
        yield

    async def on_put_data_objects(
        self,
        msg: PutDataObjects,
        msg_header: MessageHeader,
        client_info: Union[None, ClientInfo] = None,
    ) -> AsyncGenerator[Optional[Message], None]:
        log("@on_put_data_objects")
        yield

    async def on_delete_data_objects(
        self,
        msg: DeleteDataObjects,
        msg_header: MessageHeader,
        client_info: Union[None, ClientInfo] = None,
    ) -> AsyncGenerator[Optional[Message], None]:
        log("@on_delete_data_objects")
        yield

    async def on_get_data_objects_response(
        self,
        msg: GetDataObjectsResponse,
        msg_header: MessageHeader,
        client_info: Union[None, ClientInfo] = None,
    ) -> AsyncGenerator[Optional[Message], None]:
        log("# on_get_data_objects_response")
        # log(msg, pretty=True)
        for do in msg.data_objects.values():
            form = do.format_.lower()
            try:
                if form == "xml":
                    log(do.data.decode("utf-8"))
                elif form == "json":
                    json.dumps(json.loads(do.data.decode("utf-8")), indent=4)
            except Exception as e:
                log(f"\n\n============= {e}\n")
                log(do, pretty=True)

        yield

    async def on_put_data_objects_response(
        self,
        msg: PutDataObjectsResponse,
        msg_header: MessageHeader,
        client_info: Union[None, ClientInfo] = None,
    ) -> AsyncGenerator[Optional[Message], None]:
        # log(f"@on_put_data_objects_response Success {len(msg.success)}:")
        # for code, pr in msg.success.items():
        #     log(f"\t@on_put_data_objects_response {code}) {str(pr.created_contained_object_uris)}")
        yield

    async def on_delete_data_objects_response(
        self,
        msg: DeleteDataObjectsResponse,
        msg_header: MessageHeader,
        client_info: Union[None, ClientInfo] = None,
    ) -> AsyncGenerator[Optional[Message], None]:
        log(f"Deletion success {len(msg.deleted_uris)}:")
        for code, aos in msg.deleted_uris.items():
            log(f"\t{code}) {str(aos)}")
        yield

    async def on_protocol_exception(
        self,
        msg: ProtocolException,
        msg_header: MessageHeader,
        client_info: Union[None, ClientInfo] = None,
    ) -> AsyncGenerator[Optional[Message], None]:
        print_protocol_exception(msg)
        yield


#     ____        __        ___                             ____             __                   __
#    / __ \____ _/ /_____ _/   |  ______________ ___  __   / __ \_________  / /_____  _________  / /
#   / / / / __ `/ __/ __ `/ /| | / ___/ ___/ __ `/ / / /  / /_/ / ___/ __ \/ __/ __ \/ ___/ __ \/ /
#  / /_/ / /_/ / /_/ /_/ / ___ |/ /  / /  / /_/ / /_/ /  / ____/ /  / /_/ / /_/ /_/ / /__/ /_/ / /
# /_____/\__,_/\__/\__,_/_/  |_/_/  /_/   \__,_/\__, /  /_/   /_/   \____/\__/\____/\___/\____/_/
#                                              /____/


@ETPConnection.on(CommunicationProtocol.DATA_ARRAY)
class DataArrayHandlerPrinter(DataArrayHandler):
    # hsdsbridge: HSDSBridge = HSDSBridge('alwyn')

    async def on_get_data_array_metadata(
        self,
        msg: GetDataArrayMetadata,
        msg_header: MessageHeader,
        client_info: Union[None, ClientInfo] = None,
    ) -> AsyncGenerator[Optional[Message], None]:
        log("@on_get_data_array_metadata")
        yield

    async def on_get_data_array_metadata_response(
        self,
        msg: GetDataArrayMetadataResponse,
        msg_header: MessageHeader,
        client_info: Union[None, ClientInfo] = None,
    ) -> AsyncGenerator[Optional[Message], None]:
        log("@on_get_data_array_metadata_response")
        yield

    async def on_get_data_arrays(
        self,
        msg: GetDataArrays,
        msg_header: MessageHeader,
        client_info: Union[None, ClientInfo] = None,
    ) -> AsyncGenerator[Optional[Message], None]:
        log("@on_get_data_arrays")
        yield

    async def on_get_data_subarrays(
        self,
        msg: GetDataSubarrays,
        msg_header: MessageHeader,
        client_info: Union[None, ClientInfo] = None,
    ) -> AsyncGenerator[Optional[Message], None]:
        log("@on_get_data_subarrays")
        yield

    async def on_get_data_arrays_response(
        self,
        msg: GetDataArraysResponse,
        msg_header: MessageHeader,
        client_info: Union[None, ClientInfo] = None,
    ) -> AsyncGenerator[Optional[Message], None]:
        log("@on_get_data_arrays_response")
        yield

    async def on_get_data_subarrays_response(
        self,
        msg: GetDataSubarraysResponse,
        msg_header: MessageHeader,
        client_info: Union[None, ClientInfo] = None,
    ) -> AsyncGenerator[Optional[Message], None]:
        log("@on_get_data_subarrays_response")
        yield

    async def on_put_data_arrays(
        self,
        msg: PutDataArrays,
        msg_header: MessageHeader,
        client_info: Union[None, ClientInfo] = None,
    ) -> AsyncGenerator[Optional[Message], None]:
        log("@on_put_data_arrays")
        yield

    async def on_put_data_arrays_response(
        self,
        msg: PutDataArraysResponse,
        msg_header: MessageHeader,
        client_info: Union[None, ClientInfo] = None,
    ) -> AsyncGenerator[Optional[Message], None]:
        log("@on_put_data_arrays_response")
        yield

    async def on_protocol_exception(
        self,
        msg: ProtocolException,
        msg_header: MessageHeader,
        client_info: Union[None, ClientInfo] = None,
    ) -> AsyncGenerator[Optional[Message], None]:
        print_protocol_exception(msg)
        yield


#    _____                              __           ________
#   / ___/__  ______  ____  ____  _____/ /____  ____/ /_  __/_  ______  ___  _____
#   \__ \/ / / / __ \/ __ \/ __ \/ ___/ __/ _ \/ __  / / / / / / / __ \/ _ \/ ___/
#  ___/ / /_/ / /_/ / /_/ / /_/ / /  / /_/  __/ /_/ / / / / /_/ / /_/ /  __(__  )
# /____/\__,_/ .___/ .___/\____/_/   \__/\___/\__,_/ /_/  \__, / .___/\___/____/
#           /_/   /_/                                    /____/_/


@ETPConnection.on(CommunicationProtocol.SUPPORTED_TYPES)
class SupportedTypesProtocolPrinter(SupportedTypesHandler):

    async def on_get_supported_types(
        self,
        msg: GetSupportedTypes,
        msg_header: MessageHeader,
        client_info: Union[None, ClientInfo] = None,
    ) -> AsyncGenerator[Optional[Message], None]:
        log("@on_get_supported_types")
        yield

    async def on_get_supported_types_response(
        self,
        msg: GetSupportedTypesResponse,
        msg_header: MessageHeader,
        client_info: Union[None, ClientInfo] = None,
    ) -> AsyncGenerator[Optional[Message], None]:
        for st in msg.supported_types:
            log(f"\t{st.data_object_type}\t count : {str(st.object_count)}")
        yield

    async def on_protocol_exception(
        self,
        msg: ProtocolException,
        msg_header: MessageHeader,
        client_info: Union[None, ClientInfo] = None,
    ) -> AsyncGenerator[Optional[Message], None]:
        print_protocol_exception(msg)
        yield


#   ______                                 __  _
#  /_  __/________ _____  _________ ______/ /_(_)___  ____
#   / / / ___/ __ `/ __ \/ ___/ __ `/ ___/ __/ / __ \/ __ \
#  / / / /  / /_/ / / / (__  ) /_/ / /__/ /_/ / /_/ / / / /
# /_/ /_/   \__,_/_/ /_/____/\__,_/\___/\__/_/\____/_/ /_/


@ETPConnection.on(CommunicationProtocol.TRANSACTION)
class TransactionHandlerPrinter(TransactionHandler):
    # async def on_commit_transaction(
    #     self,
    #     msg: CommitTransaction,
    #     msg_header: MessageHeader,
    #     client_info: Union[None, ClientInfo] = None,
    # ) -> AsyncGenerator[Optional[Message], None]:
    #     yield NotSupportedError().to_etp_message(
    #         correlation_id=msg_header.message_id
    #     )

    async def on_commit_transaction_response(
        self,
        msg: CommitTransactionResponse,
        msg_header: MessageHeader,
        client_info: Union[None, ClientInfo] = None,
    ) -> AsyncGenerator[Optional[Message], None]:
        log("@on_commit_transaction_response")
        yield

    # async def on_rollback_transaction(
    #     self,
    #     msg: RollbackTransaction,
    #     msg_header: MessageHeader,
    #     client_info: Union[None, ClientInfo] = None,
    # ) -> AsyncGenerator[Optional[Message], None]:
    #     yield NotSupportedError().to_etp_message(
    #         correlation_id=msg_header.message_id
    #     )

    async def on_rollback_transaction_response(
        self,
        msg: RollbackTransactionResponse,
        msg_header: MessageHeader,
        client_info: Union[None, ClientInfo] = None,
    ) -> AsyncGenerator[Optional[Message], None]:
        log("@on_rollback_transaction_response")
        yield

    # async def on_start_transaction(
    #     self,
    #     msg: StartTransaction,
    #     msg_header: MessageHeader,
    #     client_info: Union[None, ClientInfo] = None,
    # ) -> AsyncGenerator[Optional[Message], None]:
    #     yield NotSupportedError().to_etp_message(
    #         correlation_id=msg_header.message_id
    #     )

    async def on_start_transaction_response(
        self,
        msg: StartTransactionResponse,
        msg_header: MessageHeader,
        client_info: Union[None, ClientInfo] = None,
    ) -> AsyncGenerator[Optional[Message], None]:
        log("@on_start_transaction_response")
        yield


#    _____                              ______
#   / ___/___  ______   _____  _____   / ____/___ _____  _____
#   \__ \/ _ \/ ___/ | / / _ \/ ___/  / /   / __ `/ __ \/ ___/
#  ___/ /  __/ /   | |/ /  __/ /     / /___/ /_/ / /_/ (__  )
# /____/\___/_/    |___/\___/_/      \____/\__,_/ .___/____/
#                                              /_/


# ATTENTION : A FAIRE EN DERNIER ! a cause de supportedProtocolList_fun()
@ETPConnection.dec_server_capabilities()
def computeCapability(supportedProtocolList_fun) -> ServerCapabilities:
    protocolDict = supportedProtocolList_fun()

    # log(protocolDict, pretty=True)
    print(list(filter(lambda p: p.protocol != 0, protocolDict)))
    return ServerCapabilities(
        applicationName="py_etp_client",
        applicationVersion="1.1.2",
        supportedProtocols=list(
            map(
                lambda d: SupportedProtocol(
                    protocol=d.protocol,
                    protocolVersion=d.protocol_version,
                    role="store" if d.protocol != 1 else "producer",
                    protocolCapabilities=d.protocol_capabilities,
                ),
                list(filter(lambda p: p.protocol != 0, protocolDict)),
            )
        ),
        supportedDataObjects=[
            # SupportedDataObject(
            #     qualified_type="resqml20.*",
            #     data_object_capabilities={}),
            # data_object_capabilities={"SupportsGet": True, "SupportsPut": True, "SupportsDelete": True}),
            # SupportedDataObject(
            #     qualified_type="resqml22.*",
            #     data_object_capabilities={}),
            # data_object_capabilities={"SupportsGet": True, "SupportsPut": True, "SupportsDelete": True})
            # SupportedDataObject({'dataObjectCapabilities': {'SupportsDelete': {'item': {'boolean': True}},
            #                                           'SupportsGet': {'item': {'boolean': True}},
            #                                           'SupportsPut': {'item': {'boolean': True}}}}
            #                                           )
            SupportedDataObject(
                qualifiedType="eml20.*",
                dataObjectCapabilities={
                    "SupportsDelete": DataValue(item=True),  # type: ignore
                    "SupportsPut": DataValue(item=True),  # type: ignore
                    "SupportsGet": DataValue(item=True),  # type: ignore
                },
            ),
            SupportedDataObject(
                qualifiedType="eml21.*",
                dataObjectCapabilities={
                    "SupportsDelete": DataValue(item=True),  # type: ignore
                    "SupportsPut": DataValue(item=True),  # type: ignore
                    "SupportsGet": DataValue(item=True),  # type: ignore
                },
            ),
            SupportedDataObject(
                qualifiedType="eml22.*",
                dataObjectCapabilities={
                    "SupportsDelete": DataValue(item=True),  # type: ignore
                    "SupportsPut": DataValue(item=True),  # type: ignore
                    "SupportsGet": DataValue(item=True),  # type: ignore
                },
            ),
            SupportedDataObject(
                qualifiedType="eml23.*",
                dataObjectCapabilities={
                    "SupportsDelete": DataValue(item=True),  # type: ignore
                    "SupportsPut": DataValue(item=True),  # type: ignore
                    "SupportsGet": DataValue(item=True),  # type: ignore
                },
            ),
            SupportedDataObject(
                qualifiedType="resqml20.*",
                dataObjectCapabilities={
                    "SupportsDelete": DataValue(item=True),  # type: ignore
                    "SupportsPut": DataValue(item=True),  # type: ignore
                    "SupportsGet": DataValue(item=True),  # type: ignore
                },
            ),
            SupportedDataObject(
                qualifiedType="resqml22.*",
                dataObjectCapabilities={
                    "SupportsDelete": DataValue(item=True),  # type: ignore
                    "SupportsPut": DataValue(item=True),  # type: ignore
                    "SupportsGet": DataValue(item=True),  # type: ignore
                },
            ),
            SupportedDataObject(
                qualifiedType="witsml20.*",
                dataObjectCapabilities={
                    "SupportsDelete": DataValue(item=True),  # type: ignore
                    "SupportsPut": DataValue(item=True),  # type: ignore
                    "SupportsGet": DataValue(item=True),  # type: ignore
                },
            ),
            SupportedDataObject(
                qualifiedType="witsml21.*",
                dataObjectCapabilities={
                    "SupportsDelete": DataValue(item=True),  # type: ignore
                    "SupportsPut": DataValue(item=True),  # type: ignore
                    "SupportsGet": DataValue(item=True),  # type: ignore
                },
            ),
            SupportedDataObject(
                qualifiedType="prodml20.*",
                dataObjectCapabilities={
                    "SupportsDelete": DataValue(item=True),  # type: ignore
                    "SupportsPut": DataValue(item=True),  # type: ignore
                    "SupportsGet": DataValue(item=True),  # type: ignore
                },
            ),
            SupportedDataObject(
                qualifiedType="prodml22.*",
                dataObjectCapabilities={
                    "SupportsDelete": DataValue(item=True),  # type: ignore
                    "SupportsPut": DataValue(item=True),  # type: ignore
                    "SupportsGet": DataValue(item=True),  # type: ignore
                },
            ),
        ],
        # supported_compression=["gzip"],
        supportedFormats=["xml"],  # type: ignore
        endpointCapabilities={"MaxWebSocketMessagePayloadSize": DataValue(item=128000000)},  # type: ignore
        supportedEncodings=["binary"],  # type: ignore
        contactInformation=Contact(
            organizationName="Geosiris",
            contactName="Gauthier Valentin",
            contactPhone="",
            contactEmail="valentin.gauthier@geosiris.com",
        ),
    )


if __name__ == "__main__":
    for v in CommunicationProtocol:
        print(v)
