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
from py_etp_client.etpconfig import ETPConfig
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
from py_etp_client import (
    GetDataspacesResponse,
)
from etptypes.energistics.etp.v12.datatypes.message_header import (
    MessageHeader,
)

from py_etp_client.requests import get_dataspaces


def start_client() -> ETPClient:
    config = ETPConfig()
    client = ETPClient(
        url=config.URL,
        spec=ETPConnection(connection_type=ConnectionType.CLIENT),
        access_token=config.ACCESS_TOKEN,
        username=config.USERNAME,
        password=config.PASSWORD,
        headers=config.ADDITIONAL_HEADERS,
        verify=False,
    )
    client.start()

    start_time = perf_counter()
    while not client.is_connected() and perf_counter() - start_time < 5:
        sleep(0.25)
    if not client.is_connected():
        logging.info("The ETP session could not be established in 5 seconds.")
    else:
        logging.info("Now connected to ETP Server")

    return client


def main():
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


if __name__ == "__main__":
    main()
