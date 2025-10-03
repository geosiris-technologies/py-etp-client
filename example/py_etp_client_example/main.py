# Copyright (c) 2022-2023 Geosiris.
# SPDX-License-Identifier: Apache-2.0
# Example Usage
import json
import asyncio
import logging
from typing import AsyncGenerator, Union
from time import sleep, perf_counter

import numpy as np

from py_etp_client.etpclient import ETPClient
from py_etp_client.etpconfig import ETPConfig, ServerConfig
from etpproto.client_info import ClientInfo
from etpproto.connection import ConnectionType
from etpproto.connection import (
    CommunicationProtocol,
    Protocol,
    ETPConnection,
)
from etpproto.protocols.dataspace import DataspaceHandler
from energyml.utils.serialization import read_energyml_xml_bytes, serialize_json
from energyml.utils.introspection import get_obj_uri
from energyml.utils.uri import parse_uri
from py_etp_client import GetDataspacesResponse, ProtocolException
from etptypes.energistics.etp.v12.datatypes.message_header import (
    MessageHeader,
)

from py_etp_client.etp_requests import get_dataspaces
from py_etp_client.utils import pe_as_str
from py_etp_client.etpclient import start_client


def main_deprecated():
    config = ETPConfig()

    short_url = ".".join(config.URL.split(".")[-2:]).split("/")[0] or "localhost"
    print(f"Log file is : {short_url}.log")
    logging.basicConfig(
        filename=f"{short_url}.log",
        # level=logging.INFO,
        level=logging.DEBUG,
    )

    client = start_client()
    # List dataspaces :
    dataspace_list = []
    print("Listing dataspaces...")
    try:
        dataspace_list = client.get_dataspaces()
        logging.info(f"Response received: {dataspace_list}")
    except TimeoutError as e:
        logging.info(f"Error: {e}")

    if not dataspace_list:
        print("No dataspace found.")
        return
    elif isinstance(dataspace_list, ProtocolException):
        print(pe_as_str(dataspace_list))
        return
    ds = dataspace_list[0]
    if "default" in ds.uri:
        ds = dataspace_list[1]
    print("using dataspace: ", ds.uri)

    resources = client.get_resources(
        uri=ds.uri,
        depth=1,
        scope="self",
        types_filter=[],
        timeout=20,
    )

    logging.info(f"Resources: {resources}")

    client.close()


def main():
    config = ServerConfig.from_env()

    client = start_client(config)
    print("Client started")

    print(client.get_dataspaces())

    client.close()


if __name__ == "__main__":
    main()
