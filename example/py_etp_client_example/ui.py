# Copyright (c) 2022-2023 Geosiris.
# SPDX-License-Identifier: Apache-2.0

import json
import os
import numpy as np
from typing import Optional, Union
import logging
from time import sleep, perf_counter
from etpproto.connection import ConnectionType
from etpproto.protocols.dataspace import DataspaceHandler
from etpproto.connection import (
    CommunicationProtocol,
    Protocol,
    ETPConnection,
)

from energyml.utils.uri import parse_uri, Uri
from py_etp_client.auth import basic_auth_encode
from py_etp_client.etpclient import ETPClient
from py_etp_client.etpconfig import ETPConfig
from py_etp_client import GetDataspacesResponse, ProtocolException, AuthorizeResponse


from py_etp_client.utils import __H5PY_MODULE_EXISTS__

if __H5PY_MODULE_EXISTS__:
    import h5py
    from py_etp_client.utils import h5_list_datasets


def start_client(config: Optional[ETPConfig] = None) -> ETPClient:
    config = config or ETPConfig()
    client = ETPClient(
        url=config.URL,
        spec=ETPConnection(connection_type=ConnectionType.CLIENT),
        access_token=config.ACCESS_TOKEN,
        username=config.USERNAME,
        password=config.PASSWORD,
        headers=config.ADDITIONAL_HEADERS,
        verify=True,
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


def looper():
    """A simple looper to keep the script running."""
    config = ETPConfig()

    log_file_path = (".".join(config.URL.split(".")[-2:]).split("/")[0] or "localhost") + "_ui.log"
    print(f"Log file is : {log_file_path}")
    logging.basicConfig(
        filename=f"{log_file_path}",
        # level=logging.INFO,
        level=logging.DEBUG,
    )

    client = start_client(config)

    while client.is_connected():
        try:
            # Ask user to type a command

            prefix = ""
            if client.active_transaction is not None:
                prefix = f"[In transaction {client.active_transaction}] "

            command = input(f"{prefix}Enter command:\n").strip()
            args = command.split()
            if len(args) > 1:
                command = args[0]
                args = args[1:]
            else:
                args = []

            command = command.lower().replace("-", "").replace("_", "")

            # ===============
            # Handle commands
            # ===============

            if command == "exit" or command == "quit":
                print("Exiting...")
                exit(0)
            elif command == "close":
                break

            # ===============
            # Core
            # ===============

            elif "authorize" in command:
                # test if args are username and password or access token
                res = None
                if len(args) == 2:
                    # transform username and password into basic auth encoded in base64
                    basic = basic_auth_encode(args[0], args[1])
                    res = client.authorize(authorization=f"Basic {basic}")
                elif len(args) == 1:
                    # transform access token into bearer auth
                    bearer = f"{args[0]}"
                    if "bearer" not in bearer.lower():
                        bearer = f"Bearer {bearer}"
                    res = client.authorize(authorization=bearer)
                else:
                    print("Please provide a username and password or an access token.")

                if isinstance(res, ProtocolException):
                    print(f"Error: {res.error.code} : {res.error.message}")
                elif isinstance(res, AuthorizeResponse):
                    print(f"Authorization successful: {res}")
                else:
                    print("Authorization failed.")

            elif "ping" in command:
                resp = client.ping()
                if resp:
                    print(f"Ping successful: {resp}")
                else:
                    print("Ping failed.")

            # ===============
            # Dataspace
            # ===============

            elif "get" in command and "dataspace" in command:
                resp = client.get_dataspaces()
                if resp:
                    if isinstance(resp, list):
                        sorted_resp = sorted(resp, key=lambda x: x.uri)
                        for ds in sorted_resp:
                            print(f"\t{ds.uri}")
                    else:
                        print(f"Error: {resp}")
                    print("")
                else:
                    print("No dataspace found.")
            elif "put" in command and "dataspace" in command:
                if args:
                    resp = client.put_dataspace(args[0])
                    if resp:
                        print(f"Dataspace {args[0]} created.")
                    else:
                        print(f"Failed to create dataspace {args[0]}.")
                else:
                    print("Please provide a name for the dataspace.")
            elif "delete" in command and "dataspace" in command:
                if args:
                    resp = client.delete_dataspace(args[0], timeout=20)
                    if resp:
                        print(f"Dataspace {args[0]} deletion response : {resp}")
                    else:
                        print(f"Failed to delete dataspace {args[0]}.")
                else:
                    print("Please provide a name for the dataspace.")

            # ===============
            # Transaction
            # ===============

            elif "start" in command and "transaction" in command:
                if args:
                    resp = client.start_transaction(args[0])
                    if resp:
                        print(f"Transaction {args[0]} started.")
                    else:
                        print(f"Failed to start transaction {args[0]}.")
                else:
                    print("Please provide a dataspace name for the transaction.")
            elif "commit" in command and "transaction" in command:
                resp = client.commit_transaction()
                if resp:
                    print("Transaction committed.")
                else:
                    print("Failed to commit transaction.")
            elif "rollback" in command and "transaction" in command:
                resp = client.rollback_transaction()
                if resp:
                    print("Transaction rolled back.")
                else:
                    print("Failed to rollback transaction.")

            # ===============
            # SupportedTypes
            # ===============

            elif "supportedtype" in command:
                resp = client.get_supported_types()
                if resp:
                    for st in resp:
                        print(f"\t{st}")
                    print("")
                else:
                    print("No supported types found.")

            # ===============
            # Resource
            # ===============

            elif "get" in command and "resource" in command:
                # if len(args) == 1 or len(args) >= 3:
                resp = client.get_resources(
                    uri=args[0] if len(args) >= 1 else None,
                    depth=args[1] if len(args) >= 2 else 1,
                    scope=args[2] if len(args) >= 3 else "self",
                    types_filter=args[3:] if len(args) >= 4 else None,
                    timeout=60,
                )
                if isinstance(resp, list):
                    print(f"\t{len(resp)} resources found")
                    sorted_resp = sorted(resp, key=lambda x: x.uri)
                    for res in sorted_resp:
                        print(f"\t\t{res.uri}  S[{res.source_count}] T[{res.target_count}]")
                elif isinstance(resp, ProtocolException):
                    print(f"\tError: {resp.error.code} : {resp.error.message}")
                else:
                    print(f"\tError: {type(resp)}")
                # else:
                # print("Please provide a dataspace URI.")

            elif "get" in command and "dataobj" in command:
                if len(args) >= 1:
                    resp = client.get_data_object(uris=args, format_="json" if "json" in command else "xml")
                    print(resp)
                else:
                    print("Please provide an object URI.")
            elif "put" in command and "dataobj" in command:
                # take dataspace name and file path as args
                if len(args) > 1:

                    resp = client.put_data_object_file(
                        file_path=args[1:],
                        dataspace_name=args[0],
                        timeout=600,
                    )
                    print(resp)
                    if resp is not None:
                        print(f"success list : {resp}")
                    else:
                        print(f"Failed to create resource {args[1]}.")
                else:
                    print("Please provide a dataspace URI and a file path.")

            # elif "put" in command and "resource" in command:

            # ===============
            # DataArray
            # ===============

            elif "get" in command and "dataarray" in command:
                if len(args) >= 2:
                    resp = client.get_data_array(uri=args[0], path_in_resource=args[1])
                    print(resp)
                else:
                    print("Please provide a data array URI and a pathInResource.")
            elif "put" in command and "dataarray" in command:
                # take dataspace name and file path as args
                if len(args) == 0:
                    print("Please provide a dataspace URI and a file path.")
                    uri = input("Enter an uri : ").strip()
                    path_in_resource = input("Enter a path in resource : ").strip()
                    dimensions = input("Enter dimensions (comma separated) : ").strip()
                    array_flat = input("Enter array flat (comma separated) : ").strip()

                    print(
                        f"uri: {uri}, path_in_resource: {path_in_resource}, dimensions: {dimensions}, array_flat: {array_flat}"
                    )

                    resp = client.put_data_array(
                        uri=uri,
                        path_in_resource=path_in_resource,
                        dimensions=[int(d) for d in dimensions.split(",")],
                        array_flat=[float(a) for a in array_flat.split(",")],
                        timeout=600,
                    )
                if len(args) >= 3:
                    array_file_path = args[2]

                    if array_file_path.lower().endswith(".json"):
                        data = None
                        with open(array_file_path, "r") as f:
                            json_data = json.loads(f.read())
                            data = np.array(json_data)

                        if data is not None:
                            resp = client.put_data_array(
                                uri=args[0],
                                path_in_resource=args[1],
                                timeout=600,
                            )
                            if resp:
                                print(f"Resource {args[0]} created.")
                            else:
                                print(f"Failed to create resource {args[0]}.")
                    elif array_file_path.lower().endswith(".h5"):
                        if __H5PY_MODULE_EXISTS__:
                            dataspace_uri = Uri.parse(
                                args[0] if "eml" in args[0] else "eml:///dataspace('" + args[0] + "')"
                            )
                            epc_paths = []
                            h5_paths = []
                            for i in range(1, len(args)):
                                if args[i].lower().endswith(".epc"):
                                    epc_paths.append(args[i])
                                elif args[i].lower().endswith(".h5"):
                                    h5_paths.append(args[i])

                            # epcs = [Epc.read_file(epc_path) for epc_path in epc_paths]

                            for h5_path in h5_paths:
                                if not os.path.exists(h5_path):
                                    print(f"File {h5_path} does not exist.")
                                    continue

                                try:
                                    datasets_names = h5_list_datasets(h5_file_path=h5_path)
                                    print("TODO : fix uri for h5 upload to use object uri and not just dataspace uri")
                                    with h5py.File(h5_path, "r") as h5_file:
                                        for ds in datasets_names:
                                            # Create a resource for each dataset in the HDF5 file
                                            dataset = h5_file[ds]
                                            if len(dataset) > 0:
                                                print(
                                                    f"\t{ds} : {type(dataset[...])} -- {dataset.shape} {type(dataset.shape)} {len(dataset)}"
                                                )
                                                resp = client.put_data_array(
                                                    uri=str(dataspace_uri),
                                                    path_in_resource=ds,
                                                    array_flat=dataset[...],
                                                    dimensions=dataset.shape,
                                                    timeout=600,
                                                )
                                                if resp:
                                                    print(f"Resource {ds} created in {dataspace_uri}.")
                                                else:
                                                    print(f"Failed to create resource {ds} in {dataspace_uri}.")
                                            else:
                                                print(f"Dataset {ds} is empty in {h5_path}. Skipping.")
                                except Exception as e:
                                    print(f"Failed to load data from {h5_path}: {e}")
                        else:
                            print("H5PY module is not installed. Please install it to use HDF5 files.")

                    else:
                        print(f"Failed to load data from {array_file_path} (not supported file extension).")
                else:
                    print("Please provide a dataspace URI and a file path.")

            # ===============
            # Unofficial
            # ===============

            elif "download" in command:
                if len(args) >= 2:
                    resp = client.get_resources(
                        uri=args[0],
                        depth=1,
                        scope="self",
                        types_filter=args[2:] if len(args) >= 3 else None,
                        timeout=60,
                    )
                    ds_name = args[0]
                    try:
                        ds_name = parse_uri(ds_name).dataspace
                    except Exception:
                        pass
                    folder_path = args[1] + "/" + (ds_name or "default")
                    os.makedirs(folder_path, exist_ok=True)

                    if isinstance(resp, list):
                        ext = "json" if "json" in command else "xml"
                        print(f"\t{len(resp)} resources found")
                        sorted_resp = sorted(resp, key=lambda x: x.uri)
                        for res in sorted_resp:
                            try:
                                with open(f"{folder_path}/{res.uri.split('/')[-1]}.{ext}", "wb") as f:
                                    f.write(client.get_data_object(uris=res.uri, format_=ext))
                                    print("\t\tDownloaded: ", res.uri.split("/")[-1])
                            except Exception as e:
                                print(f"Failed to download {res.uri}: {e}")
                    elif isinstance(resp, ProtocolException):
                        print(f"\tError: {resp.error.code} : {resp.error.message}")
                    else:
                        print(f"\tError: {type(resp)}")
                else:
                    print(
                        "Please provide a dataspace name and a folder path. After that, you can specify a list of types to filter (e.g. resqml22.TriangulatedSetRepresentation)."
                    )
            else:
                print(f"Unknown command: {command}. Type 'exit' to quit.")
        except KeyboardInterrupt:
            break

    client.close()


if __name__ == "__main__":

    looper()
