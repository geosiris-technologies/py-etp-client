# Copyright (c) 2022-2023 Geosiris.
# SPDX-License-Identifier: Apache-2.0
# Example Usage
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
from py_etp_client import (
    GetDataspacesResponse,
)
from etptypes.energistics.etp.v12.datatypes.message_header import (
    MessageHeader,
)

from py_etp_client.requests import get_dataspaces


if __name__ == "__main__":
    print_gdo = False
    print_put_del_ds = False
    print_pdo = False
    print_gda = False
    print_pda = True

    logging.getLogger().setLevel(logging.INFO)
    config = ETPConfig()
    # logging.info(config.to_json())

    @ETPConnection.on(CommunicationProtocol.DATASPACE)
    class newDataspaceHandler(DataspaceHandler):
        async def on_get_dataspaces_response(
            self,
            msg: GetDataspacesResponse,
            msg_header: MessageHeader,
            client_info: Union[None, ClientInfo] = None,
        ) -> AsyncGenerator[bytes, None]:
            for dataspace in msg.dataspaces:
                logging.info("==> %s", dataspace.uri)
            yield

    # ================================================

    client = ETPClient(
        url=config.URL,
        spec=ETPConnection(connection_type=ConnectionType.CLIENT),
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
        print("The ETP session could not be established in 5 seconds.")
    else:
        print("Now connected to ETP Server")

    try:
        response = client.get_dataspaces()
        logging.info(f"Response received: {response}")
    except TimeoutError as e:
        logging.info(f"Error: {e}")

    if print_gdo:
        response = client.get_data_object(
            uris="eml:///dataspace('brgm')/resqml22.FaultInterpretation(4442ce2b-76b3-4af4-9841-ff7e0cbd1c29)"
        )
        print("GDO resp [str]: ", response)
        response = client.get_data_object(
            uris=[
                "eml:///dataspace('brgm')/resqml22.FaultInterpretation(4442ce2b-76b3-4af4-9841-ff7e0cbd1c29)",
                "eml:///dataspace('brgm')/resqml22.BoundaryFeature(00b59008-cceb-4291-941f-e25a080155e7)",
            ]
        )
        print("GDO resp [list]: ", response)
        response = client.get_data_object(
            uris={
                "0": "eml:///dataspace('brgm')/resqml22.FaultInterpretation(4442ce2b-76b3-4af4-9841-ff7e0cbd1c29)",
                "1": "eml:///dataspace('brgm')/resqml22.BoundaryFeature(00b59008-cceb-4291-941f-e25a080155e7)",
            }
        )
        print("GDO resp [dict]: ", response)

    if print_put_del_ds:
        response = client.get_resources("brgm")
        for r in response:
            print(f"\t{r.uri}")

        response = client.put_dataspace(["test-add"])
        print(f"Put dataspace response: {response}")

        response = client.get_dataspaces()
        for r in response:
            print(f"\t{r.uri}")

        response = client.delete_dataspace(["test-add"])
        print(f"Delete dataspace response: {response}")

        response = client.get_dataspaces()
        for r in response:
            print(f"\t{r.uri}")

    if print_pdo:
        response = client.put_dataspace(["test-add"])
        print(f"Put dataspace response: {response}")
        response = client.put_data_object_str(
            obj_content="""[{
        "$type": "resqml22.FaultInterpretation",
        "Citation": {
            "$type": "eml23.Citation",
            "Creation": "2024-12-06T16:34:08.405Z",
            "Format": "Geosiris WebStudio",
            "LastUpdate": "2024-12-06T16:36:30.761Z",
            "Originator": "Geosiris user",
            "Title": "Thym"
        },
        "DipDirectionNorthReferenceKind": "magnetic north",
        "Domain": "depth",
        "Existence": "actual",
        "InterpretedFeature": {
            "$type": "eml23.DataObjectReference",
            "QualifiedType": "resqml22.BoundaryFeature",
            "Title": "[Fault] Thym",
            "Uuid": "00b59008-cceb-4291-941f-e25a080155e7"
        },
        "SchemaVersion": "2.2",
        "Uuid": "4442ce2b-76b3-4af4-9841-ff7e0cbd1c29"
    }]""",
            dataspace_name="test-add",
        )
        response = client.get_resources("test-add")
        for r in response:
            print(f"\t{r.uri}")

        response = client.delete_dataspace(["test-add"])
        print(f"Delete dataspace response: {response}")

    if print_gda:
        response = client.get_data_array("nothing", "/")
        print(response)
        response = client.get_data_array(
            "eml:///dataspace('brgm')/resqml22.PointSetRepresentation(3ddf8a1b-efac-42d5-ae32-bf65f8dc693e)",
            "/RESQML/3ddf8a1b-efac-42d5-ae32-bf65f8dc693e/points_patch0",
        )
        print(response)

    if print_pda:
        uuid = "ffaabbaa-efac-42d5-ae32-bf65f8dc693e"
        array = np.array([[1, 2, 3], [4, 5, 6]])
        response = client.put_data_array(
            "eml:///dataspace('test-workflow-aws')", f"/test/{uuid}", array.flatten(), list(array.shape)
        )
        print(response)

        response = client.get_data_array_metadata(
            "eml:///dataspace('test-workflow-aws')",
            f"/test/{uuid}",
        )
        print(response)

        response = client.get_data_array(
            "eml:///dataspace('test-workflow-aws')",
            f"/test/{uuid}",
        )
        print(response)

    client.stop()
