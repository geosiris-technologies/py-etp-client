# Copyright (c) 2022-2023 Geosiris.
# SPDX-License-Identifier: Apache-2.0
# Example Usage
import json
import logging
import os
import traceback
from typing import Optional, Union
from time import sleep, perf_counter

import numpy as np

from py_etp_client.auth import BasicAuthConfig, TokenManager
from py_etp_client.etpclient import ETPClient
from py_etp_client.etpconfig import ETPConfig, ServerConfig
from py_etp_client import ProtocolException, AuthorizeResponse
from py_etp_client.etp_requests import get_property_kind_and_parents, read_energyml_obj
from etpproto.connection import ConnectionType
from etpproto.connection import (
    ETPConnection,
)
from energyml.utils.introspection import (
    get_obj_uri,
    get_object_attribute,
)
from energyml.utils.uri import parse_uri, Uri
from energyml.utils.epc import get_property_kind_by_uuid
from energyml.utils.data.datasets_io import get_path_in_external_with_path
from energyml.utils.constants import path_last_attribute, RGX_UUID_NO_GRP

# import energyml.resqml.v2_2.resqmlv2 as r22
# import energyml.resqml.v2_0_1.resqmlv2 as r201

from py_etp_client.etp_requests import get_dataspaces
from py_etp_client.utils import __H5PY_MODULE_EXISTS__, pe_as_str

if __H5PY_MODULE_EXISTS__:
    import h5py
    from py_etp_client.utils import h5_list_datasets


def start_client(config: Optional[Union[ETPConfig, ServerConfig]] = None, verify: bool = False) -> ETPClient:
    config = config or ETPConfig()

    if isinstance(config, ETPConfig):
        add_h = config.ADDITIONAL_HEADERS or {}
        if isinstance(add_h, str):
            try:
                add_h = json.loads(add_h)
            except json.JSONDecodeError:
                logging.error("Failed to parse ADDITIONAL_HEADERS as JSON. Using empty headers.")
                add_h = {}
        client = ETPClient(
            url=config.URL,
            spec=ETPConnection(connection_type=ConnectionType.CLIENT),
            access_token=config.ACCESS_TOKEN,
            username=config.USERNAME,
            password=config.PASSWORD,
            headers=add_h,
            verify=verify,
        )
    else:
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


def looper():
    """A simple looper to keep the script running."""
    # config = ETPConfig()
    # log_file_path = "logs/" + (".".join(config.URL.split(".")[-2:]).split("/")[0] or "localhost") + "_ui.log"  # type: ignore
    config = ServerConfig.from_file()
    log_file_path = "logs/" + (".".join(config.url.split(".")[-2:]).split("/")[0] or "localhost") + "_ui.log"  # type: ignore

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
                    tm = TokenManager()
                    basic = tm._get_basic_auth_token(BasicAuthConfig(args[0], args[1]))
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
                    print(pe_as_str(res))
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
                    ds_name = args[0]
                    acl_option = (
                        input(
                            "Do you want to set an ACL for the dataspace?\n\t[0] No \n\t[1] Yes from config file \n\t[2] Yes interactively\n"
                        )
                        .strip()
                        .lower()
                    )
                    if acl_option == "0":
                        resp = client.put_dataspace(ds_name)
                    elif acl_option == "1":
                        resp = client.put_dataspaces_with_acl(
                            ds_name,
                            acl_owners=config.acl_owners,
                            acl_viewers=config.acl_viewers,
                            legal_tags=config.legal_tags,
                            other_relevant_data_countries=config.data_countries,
                            timeout=20,
                        )
                    elif acl_option == "2":
                        acl_owners = input("Enter ACL owners (comma separated): ").strip().split(",")
                        acl_viewers = input("Enter ACL viewers (comma separated): ").strip().split(",")
                        legal_tags = input("Enter legal tags (comma separated): ").strip().split(",")
                        other_relevant_data_countries = (
                            input("Enter other relevant data countries (comma separated): ").strip().split(",")
                        )

                        print("Creating dataspace with the following ACL:")
                        print(f"  Owners: {acl_owners}")
                        print(f"  Viewers: {acl_viewers}")
                        print(f"  Legal Tags: {legal_tags}")
                        print(f"  Other Relevant Data Countries: {other_relevant_data_countries}")

                        resp = client.put_dataspaces_with_acl(
                            ds_name,
                            acl_owners=acl_owners,
                            acl_viewers=acl_viewers,
                            legal_tags=legal_tags,
                            other_relevant_data_countries=other_relevant_data_countries,
                            timeout=20,
                        )
                    else:
                        print("Invalid option. Please try again.")
                        continue
                    if resp:
                        if isinstance(resp, list):
                            for r in resp:
                                print(f"Dataspace {r} created.")
                        elif isinstance(resp, ProtocolException):
                            print(f"Failed to create dataspace {ds_name}: {resp}")
                        else:
                            print(f"Dataspace {ds_name} created.")
                    else:
                        print(f"Failed to create dataspace {ds_name}.")
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

            elif "start" in command:  # and "transaction" in command:
                if args:
                    resp = client.start_transaction(args[0])
                    if resp:
                        print(f"Transaction {args[0]} started.")
                    else:
                        print(f"Failed to start transaction {args[0]}.")
                else:
                    print("Please provide a dataspace name for the transaction.")
            elif "commit" in command:  # and "transaction" in command:
                resp, msg = client.commit_transaction_get_msg()
                if resp:
                    print("Transaction committed.")
                else:
                    print(f"Failed to commit transaction: {msg}")
            elif "rollback" in command:  # and "transaction" in command:
                resp = client.rollback_transaction()
                if resp:
                    print("Transaction rolled back.")
                else:
                    print("Failed to rollback transaction.")

            # ===============
            # SupportedTypes
            # ===============

            elif "supportedtype" in command:
                if args is not None and len(args) > 0:
                    resp = client.get_supported_types(args[0])
                    if resp:
                        for st in resp:
                            print(f"\t{st}")
                        print("")
                    else:
                        print("No supported types found.")
                else:
                    print("Please provide a dataspace name or uri")

            # ===============
            # Resource
            # ===============

            elif "get" in command and "resource" in command:
                # if len(args) == 1 or len(args) >= 3:
                resp = client.get_resources(
                    uri=args[0] if len(args) >= 1 else None,
                    depth=int(args[1]) if len(args) >= 2 else 1,
                    scope=args[2] if len(args) >= 3 else "self",
                    types_filter=args[3:] if len(args) >= 4 else None,
                    include_edges="edges" in command,
                    timeout=60,
                )
                if isinstance(resp, list):
                    print(f"\t{len(resp)} resources found")
                    sorted_resp = sorted(resp, key=lambda x: x.uri)
                    for res in sorted_resp:
                        print(f"\t\t{res.uri}  S[{res.source_count}] T[{res.target_count}] {res.name}")
                elif isinstance(resp, ProtocolException):
                    print(pe_as_str(resp))
                else:
                    print(f"\tError: {type(resp)}")
                # else:
                # print("Please provide a dataspace URI.")

            elif "get" in command and "dataobj" in command:
                if len(args) >= 1:
                    obj_format = "json" if "json" in command else "xml"
                    resp = client.get_data_object(uris=args, format_=obj_format)

                    if isinstance(resp, ProtocolException):
                        print(pe_as_str(resp))
                        resp = None
                    elif isinstance(resp, list):
                        objs = []
                        if "json" in command:
                            print(f"type : {type(resp)} -- {len(resp)}\n {resp}")
                            print(json.dumps([json.loads(r) for r in resp], indent=2))
                        else:
                            print(resp)

                        objs = []
                        for r in resp:
                            try:
                                o = read_energyml_obj(r, obj_format)
                                objs.append(o)
                            except Exception:
                                pass

                        array_seach_msg = ""
                        for o in objs:
                            piefs = get_path_in_external_with_path(o)
                            if len(piefs) > 0:
                                array_seach_msg += f"\t{get_obj_uri(o)} '{get_object_attribute(o, 'Citation.Title')}': {list(map(lambda p: p[1], piefs))}\n"

                        if len(array_seach_msg) > 0:
                            print(f"Found {len(objs)} objects with potential arrays:\n{array_seach_msg}")

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

            elif "put" in command and "prop" in command:
                if len(args) >= 2:
                    props_uuids = args[1:]

                    props = list(get_property_kind_and_parents(props_uuids).values())

                    resp = client.put_data_object_obj(
                        obj=props,
                        dataspace_name=args[0],
                        timeout=600,
                    )
                    if resp:
                        print(f"Resource {args[0]} created.")
                    else:
                        print(f"Failed to create resource {args[0]}.")

            elif "delete" in command and "dataspace" not in command:
                if len(args) >= 1:
                    resp = client.delete_data_object(args, timeout=60)
                    if resp:
                        print(f"Resource deletion result : {resp}.")
                    else:
                        print("Failed to delete resource.")
                else:
                    print("Please provide a resource URI.")

            # ===============
            # DataArray
            # ===============

            elif "get" in command and "dataarray" in command:
                if len(args) >= 2:
                    resp = client.get_data_array(uri=args[0], path_in_resource=args[1], timeout=30)
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
                                array_flat=data,
                                dimensions=list(data.shape),
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
                                    with h5py.File(h5_path, "r") as h5_file:  # type: ignore
                                        for ds in datasets_names:
                                            # Create a resource for each dataset in the HDF5 file
                                            dataset = h5_file[ds]
                                            if len(dataset) > 0:  # type: ignore
                                                print(
                                                    f"\t{ds} : {type(dataset[...])} -- {dataset.shape} {type(dataset.shape)} {len(dataset)}"  # type: ignore
                                                )
                                                resp = client.put_data_array(
                                                    uri=str(dataspace_uri),
                                                    path_in_resource=ds,
                                                    array_flat=dataset[...],  # type: ignore
                                                    dimensions=dataset.shape,  # type: ignore
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
                                    _do = client.get_data_object(uris=res.uri, format_=ext)
                                    if isinstance(_do, ProtocolException):
                                        print(f"Failed to download {res.uri}: {pe_as_str(_do)}")
                                        continue
                                    elif isinstance(_do, (str, bytes)):
                                        f.write(_do.encode("utf-8") if isinstance(_do, str) else _do)
                                        print("\t\tDownloaded: ", res.uri.split("/")[-1])
                                    else:
                                        print(f"Failed to download {res.uri}: unexpected response type {type(_do)}")
                                        continue
                            except Exception as e:
                                print(f"Failed to download {res.uri}: {e}")
                    elif isinstance(resp, ProtocolException):
                        print(pe_as_str(resp))
                    else:
                        print(f"\tError: {type(resp)}")
                else:
                    print(
                        "Please provide a dataspace name and a folder path. After that, you can specify a list of types to filter (e.g. resqml22.TriangulatedSetRepresentation)."
                    )
            elif "help" in command or "?" in command:
                print(
                    "Available commands:\n"
                    "- exit/quit: Exit the program\n"
                    "- close: Close the client connection\n"
                    "- authorize <username> <password> or <access_token>: Authorize the client\n"
                    "- ping: Ping the server\n\n"
                    "===============\n"
                    " Dataspace Commands\n"
                    "===============\n"
                    "- getDataspace: List all dataspaces\n"
                    "- putDataspace <name>: Create a new dataspace\n"
                    "- deleteDataspace <name>: Delete a dataspace\n\n"
                    "===============\n"
                    " Transaction Commands\n"
                    "===============\n"
                    "- start <dataspace_name>: Start a transaction in a dataspace\n"
                    "- commit: Commit the current transaction\n"
                    "- rollback: Rollback the current transaction\n\n"
                    "===============\n"
                    " Resources Commands\n"
                    "===============\n"
                    "- getSupportedtype: List all supported types\n"
                    "- getResource <uri> [depth] [scope] [types_filter]: Get resources from a dataspace\n\n"
                    "===============\n"
                    " DataObject Commands\n"
                    "===============\n"
                    "- getDataobj <uri> [format]: Get a data object by URI\n"
                    "- putDataobj <dataspace_name> <file_path | folder_path>: Put data objects in a dataspace from a file (xml/json/epc) or a folder containing some.\n\n"
                    "- putProperty <dataspace_name> <property_uuid+>: Put PropertyKind objects (from official dictionary) in a dataspace by their UUIDs\n"
                    "- deleteDataobj <uris+>: Delete a data object by URI\n\n"
                    "===============\n"
                    " DataArray Commands\n"
                    "===============\n"
                    "- getDataarray <uri> <path_in_resource>: Get a data array by URI and path in resource\n"
                    "- putDataarray <dataspace_name> <path_in_resource> [file_path]: Put a data array in a dataspace\n"
                    "- download <dataspace_uri> <folder_path> [types_filter...]: Download resources from a dataspace to a folder\n"
                )
            else:
                print(f"Unknown command: {command}. Type 'exit' to quit.")
        except KeyboardInterrupt:
            break
        except Exception as e:
            traceback.print_exc()
            logging.error(f"An error occurred: {e}")
            print(f"An error occurred: {e}")

    client.close()


if __name__ == "__main__":

    from py_etp_client.serverprotocols import (
        CoreProtocolPrinter,
        DiscoveryProtocolPrinter,
        DataspaceHandlerPrinter,
        StoreProtocolPrinter,
        DataArrayHandlerPrinter,
        SupportedTypesProtocolPrinter,
        TransactionHandlerPrinter,
        enable_logs,
    )

    looper()
