from dataclasses import dataclass
from io import BytesIO
import json
import logging
import os
from typing import Dict
import h5py
import numpy as np
from typingx import List, Union, Optional, Any
from energyml.utils.epc import Epc
from energyml.utils.validation import validate_epc, MissingEntityError
from energyml.utils.uri import Uri as EtpUri, parse_uri
from energyml.utils.serialization import read_energyml_xml_str, read_energyml_json_str
from energyml.utils.introspection import get_obj_uri, get_obj_uuid, get_object_attribute
from energyml.utils.constants import path_last_attribute
from energyml.utils.data.datasets_io import (
    get_path_in_external_with_path,
    h5_list_datasets,
    HDF5FileWriter,
    HDF5FileReader,
)
from py_etp_client.etpclient import ETPClient, start_client


from py_etp_client import (
    ProtocolException,
    Resource,
    Uuid,
)
from py_etp_client.etpconfig import ETPConfig
from py_etp_client.etp_requests import _create_resource, read_energyml_obj


@dataclass
class DataStorage:
    etp_client: Optional[ETPClient] = None
    dataspace: Optional[str] = None
    epc: Optional[Epc] = None

    def get_all_related_objects_uris(
        self, uri: Union[str, List[str]], scope: str = "targetOrSelf", timeout: int = 5
    ) -> List[str]:
        """
        Get all related objects URIs from the ETP client.

        :param uri: URI of the resource to get related objects for.
        :param scope: Scope of the resource retrieval (default is "targetOrSelf").
        :param timeout: Timeout for the operation (default is 5 seconds).
        :return: List of related objects URIs.
        """
        res = []
        if self.epc is not None:
            if "source" in scope.lower():
                rels = self.epc.compute_rels()  # noqa: F841
        # TODO: Implement this for EPC data storage
        raise Exception("Method not implemented for EPC data storage.")

        if self.etp_client is not None:
            res.extend(self.etp_client.get_all_related_objects_uris(uri=uri, scope=scope, timeout=timeout))
        return []

    def get_resources(
        self, uri: Optional[str], depth: int = 1, scope: str = "targetOrSelf", timeout: int = 5
    ) -> Union[List[Resource], ProtocolException]:
        """
        Get resources from the ETP client.

        :param uri: URI of the resource to get.
        :param depth: Depth of the resource retrieval (default is 1).
        :param scope: Scope of the resource retrieval (default is "targetOrSelf").
        :param timeout: Timeout for the operation (default is 5 seconds).
        :return: List of resources.
        """
        res = []
        if self.epc is not None:
            for obj in self.epc.energyml_objects:
                res.append(_create_resource(obj))

        if self.etp_client is not None:
            res.extend(self.etp_client.get_resources(uri=uri, depth=depth, scope=scope, timeout=timeout))

        return res

    def put_data_objects(
        self,
        objects: List[Union[Any, Epc, str]],
        format_: str = "xml",
        timeout: int = 15,
    ) -> Any:
        """
        Put data objects to the server.

        :param objects: List of objects to put.
        :param format_: Format of the data (default is "xml").
        :param timeout: Timeout for the operation (default is 5 seconds).
        :return: List of URIs of the put objects.
        """

        if len(objects) == 0:
            logging.warning("No objects provided to put_data_objects.")
            return []

        if not isinstance(objects, list):
            objects = [objects]

        if self.epc is not None:
            for obj in objects:
                if isinstance(obj, Epc):
                    self.epc.energyml_objects.extend(obj.energyml_objects)
                elif isinstance(obj, str):
                    if format_.lower() == "xml":
                        self.epc.energyml_objects.append(read_energyml_xml_str(obj))
                    elif format_.lower() == "json":
                        self.epc.energyml_objects.append(read_energyml_json_str(obj))
                    else:
                        raise ValueError(f"Unsupported format: {format_}. Use 'xml' or 'json'.")
                else:
                    self.epc.energyml_objects.append(obj)
        if self.etp_client is not None:
            if isinstance(objects[0], str) or isinstance(objects[0], bytes):
                return self.etp_client.put_data_object_str(
                    obj_content=objects, dataspace_name=self.dataspace or "", format=format_, timeout=timeout
                )
            else:
                return self.etp_client.put_data_object_obj(
                    obj=objects, dataspace_name=self.dataspace or "", format_=format_, timeout=timeout
                )

    def put_data_array(
        self,
        uri: str,
        path_in_resource: str,
        array_flat: np.ndarray,
        dimensions: List[int],
        timeout: int = 15,
    ) -> Dict[str, bool]:
        """
        Put a data array to the server.

        :param uri: URI of the resource.
        :param path_in_resource: Path in the resource where the array will be stored.
        :param array_flat: Flat array data to put.
        :param dimensions: Dimensions of the array.
        :param timeout: Timeout for the operation (default is 5 seconds).
        :return: Dictionary with the result of the operation.
        """

        if array_flat is None:
            logging.error("Array data is None, cannot put data array.")
            return {"success": False}

        if self.epc is not None:
            target = None
            if self.epc.epc_file_path is not None:
                target = self.epc.epc_file_path
                if target.endswith(".epc"):
                    target = target[:-4]
                target = target + ".h5"
            else:
                target = BytesIO()
                self.epc.h5_io_files.append(target)

            print(f"Writing array to target: {target}, path: {path_in_resource}")

            writer = HDF5FileWriter()
            try:
                writer.write_array(
                    target=target,
                    array=array_flat.reshape(dimensions),
                    path_in_external_file=path_in_resource,
                    dtype=array_flat.dtype,
                )
            except Exception as e:
                logging.error(f"Failed to write array to target: {e}")
                # return {"success": False}

        if self.etp_client is not None:
            return self.etp_client.put_data_array(
                uri=uri,
                path_in_resource=path_in_resource,
                array_flat=array_flat,
                dimensions=dimensions,
                timeout=timeout,
            )
        return {"success": False}

    def start_transaction(self, dataspace: Optional[str] = None) -> Optional[Uuid]:
        """
        Start a transaction on the ETP client.

        :param dataspace: Name of the dataspace to start the transaction in.
        """
        if self.etp_client is not None:
            try:
                return self.etp_client.start_transaction(dataspace=dataspace)
            except Exception as e:
                logging.error(f"Failed to start transaction on ETP client: {e}")

    def commit_transaction(self):
        """
        Commit the transaction on the ETP client (or save EPC file and h5 files).
        """
        if self.epc is not None:
            self.epc.epc_file_path = self.epc.epc_file_path or "output.epc"
            self.epc.export_file()

            h5_file_path = self.epc.epc_file_path or "output.h5"
            if h5_file_path.endswith(".epc"):
                h5_file_path = h5_file_path[:-4] + ".h5"

            print(f"nb of h5 files: {len(self.epc.h5_io_files)}")
            for h5_file in self.epc.h5_io_files:
                h5_file.seek(0)
                print(f"Processing HDF5 file: {h5_file_path}")

                h5_file.seek(0)  # Reset the file pointer to the beginning

                writer = HDF5FileReader()
                writer.extract_h5_datasets(
                    input_h5=h5_file, output_h5=h5_file_path, h5_datasets_paths=h5_list_datasets(h5_file)
                )

        if self.etp_client is not None:
            try:
                return self.etp_client.commit_transaction()
            except Exception as e:
                logging.error(f"Failed to commit transaction on ETP client: {e}")


#    _____           _       __
#   / ___/__________(_)___  / /______
#   \__ \/ ___/ ___/ / __ \/ __/ ___/
#  ___/ / /__/ /  / / /_/ / /_(__  )
# /____/\___/_/  /_/ .___/\__/____/
#                 /_/


def _search_uri_from_uuid(uris: List[str], uuid: str) -> Optional[str]:
    """
    Search for a URI in a list of URIs that matches the given UUID.

    :param uris: List of URIs to search in.
    :param uuid: UUID to match against the URIs.
    :return: The matching URI if found, otherwise None.
    """
    for uri in uris:
        if uuid in uri:
            return uri
    return None


def transfert_data(
    etp_client_source: ETPClient,  # DataStorage,
    etp_client_target: DataStorage,
    uris: List[Union[str, EtpUri]],
    # dataspace_source: str,
    # dataspace_target: Optional[str] = None,
    include_references: bool = False,
    overwrite_existing: bool = False,
    timeouts: int = 120,
):
    # if not etp_client_source.is_connected():
    #     raise RuntimeError("Source ETP client is not connected.")
    # if not etp_client_target.is_connected():
    #     raise RuntimeError("Target ETP client is not connected.")

    objects_uris = [str(uri) if not isinstance(uri, str) else uri for uri in uris]

    if include_references:
        objects_uris = etp_client_source.get_all_related_objects_uris(uri=objects_uris, scope="targetOrSelf")

    filtered_uris = objects_uris
    if not overwrite_existing:

        def tmp(x):
            # print(f"===> {x}")
            return parse_uri(x.uri).uuid

        existing_uuids = list(
            map(
                lambda r: tmp(r),
                etp_client_target.get_resources(uri=etp_client_target.dataspace, depth=1, scope="targetOrSelf"),
            )
        )
        # print(f"existing_uuids : {existing_uuids}")
        filtered_uris = list(filter(lambda x: parse_uri(x).uuid not in existing_uuids, objects_uris))
        logging.debug(f"Filtered {len(objects_uris) - len(filtered_uris)} objects that already exist in target.")

    if len(filtered_uris) == 0:
        logging.warning("No objects to transfer after filtering.")
        return

    logging.debug(f"Transferring {len(filtered_uris)} objects from source to target ETP client.")
    logging.info(f"Transferring objects: {filtered_uris}")

    objs_xml: List[str] = etp_client_source.get_data_object(uris=filtered_uris, format_="xml", timeout=timeouts)
    # objs = etp_client_source.get_data_object_as_obj(uris=filtered_uris, format_="xml", timeout=timeouts)
    if not objs_xml:
        logging.warning("No objects found to transfer.")
        return

    try:
        etp_client_target.start_transaction(dataspace=etp_client_target.dataspace)
    except Exception as e:
        logging.error(f"Failed to start transaction on target ETP client: {e}")
        return

    res = []
    NB_OBJECTS_PER_PUT = 1
    # Split the objects into chunks of NB_OBJECTS_PER_PUT
    for i in range(int(len(objs_xml) / NB_OBJECTS_PER_PUT)):
        res.extend(
            etp_client_target.put_data_objects(
                objects=objs_xml[i * NB_OBJECTS_PER_PUT : (i + 1) * NB_OBJECTS_PER_PUT],
                format_="xml",
                timeout=timeouts,
            )
        )
    # res = etp_client_target.put_data_objects(objects=objs_xml, format_="xml", timeout=timeouts)
    logging.debug(f"Put data object response: {res}")

    objs = [read_energyml_obj(o, format_="xml") for o in objs_xml]

    # Arrays
    for o in objs:
        _piefs = get_path_in_external_with_path(o)
        if _piefs is not None and len(_piefs) > 0:
            uri = _search_uri_from_uuid(objects_uris, get_obj_uuid(o))
            # print(f"Object URI: {uri}, UUID: {get_obj_uuid(o)}")
            for path, pief in _piefs:
                if "hdf" in path_last_attribute(path).lower():
                    proxy_path = path[: -len(path_last_attribute(path))] + "hdf_proxy.uuid"
                    proxy_uuid = get_object_attribute(obj=o, attr_dot_path=proxy_path)
                    # print(
                    #     f"o : {o.uuid}, uri : {uri}, path: {path}, pief: {pief}, proxy_uuid: {proxy_uuid}, proxy_path: {proxy_path}"
                    # )
                    # print(f"dataspace : {parse_uri(uri).dataspace}")
                    if proxy_uuid is not None:
                        if uri is None or proxy_uuid not in uri:
                            external_part_refs = list(
                                map(
                                    lambda r: r.uri,
                                    etp_client_source.get_resources(
                                        uri=parse_uri(uri).dataspace,
                                        depth=1,
                                        types_filter=["eml20.obj_EpcExternalPartReference"],
                                    ),
                                )
                            )
                            # print(f"External part refs: {external_part_refs}")
                            uri = _search_uri_from_uuid(external_part_refs, proxy_uuid)
                            if uri is not None:
                                # transfert external part reference if not exists
                                transfert_data(
                                    etp_client_source=etp_client_source,
                                    etp_client_target=etp_client_target,
                                    uris=[uri],
                                    include_references=False,
                                    overwrite_existing=False,
                                    timeouts=timeouts,
                                )
                                objects_uris.append(uri)
                    else:
                        logging.error(
                            f"Failed to find hdfProxy UUID in path: {path}. "
                            "Ensure the object has a valid hdfProxy UUID."
                        )
                # elif uri is None:
                #     uri = _search_uri_from_uuid(filtered_uris, get_obj_uuid(o))
                # print(f"DA uri : {uri}")
                if uri is None:
                    logging.error(f"Failed to find URI for object with UUID: {get_obj_uuid(o)}")
                    continue
                else:
                    array = etp_client_source.get_data_array(
                        uri=uri,
                        path_in_resource=pief,
                        timeout=timeouts,
                    )
                    if array is None:
                        logging.error(
                            f"Failed to retrieve data array from source ETP client for URI: {uri}, path: {pief}"
                        )
                        continue
                    # print(f"Array  {array}")

                    uri_target = parse_uri(uri)  # Ensure uri is valid
                    uri_target.dataspace = etp_client_target.dataspace or dataspace_out
                    uri_target = str(uri_target)
                    logging.debug(f"uri in filter list: {_search_uri_from_uuid(filtered_uris, get_obj_uuid(o))}")
                    logging.debug(
                        f"Putting data array to target ETP client: {uri_target}, path: {path}, dimensions: {list(array.shape)} pief: {pief}, timeout: {timeouts}"
                    )

                    etp_client_target.put_data_array(
                        uri=uri_target,
                        path_in_resource=pief,
                        array_flat=array,
                        dimensions=list(array.shape),
                        timeout=timeouts,
                    )

    try:
        # debug : listing all entities in the target ETP client
        target_object_list = []
        if etp_client_target.etp_client is not None:
            target_object_list = list(
                map(
                    lambda r: r.uri,
                    etp_client_target.etp_client.get_resources(
                        uri=etp_client_target.dataspace,
                        depth=1,
                        scope="targetOrSelf",
                    ),
                )
            )
        commit_result = etp_client_target.commit_transaction()
        if not commit_result:
            print("Failed to commit transaction on target ETP client. Please check the logs for details.")
            logging.debug(
                f"Transaction failed to commit on target ETP client. These are the uploaded objects: {filtered_uris}"
            )
            # To debug missing entities :
            epc = Epc(energyml_objects=objs)

            errs = validate_epc(epc)

            logging.debug(f"Objects validation [FULL]: \n{json.dumps([err.toJson() for err in errs], indent=4)}")

            logging.debug("Objects validation [SHORT]: \n")
            missing_list = []
            for err in errs:
                if isinstance(err, MissingEntityError):
                    miss_uuid = err.missing_uuid
                    miss_uri = _search_uri_from_uuid(target_object_list, miss_uuid)
                    if miss_uri is None and miss_uuid not in missing_list:
                        missing_list.append(miss_uuid)
                        logging.error(f"Missing entity with UUID {miss_uuid} has no corresponding URI in the source.")
            logging.debug(f"[END] Objects validation, nb missing entities found : {len(missing_list)}")

            not_uploaded_uris = list(
                filter(
                    lambda u: u is not None,
                    [
                        u if _search_uri_from_uuid(target_object_list, parse_uri(u).uuid) is None else None
                        for u in filtered_uris
                    ],
                )
            )
            logging.debug(
                f"Not uploaded objects uris [{len(not_uploaded_uris)}]: {json.dumps(not_uploaded_uris, indent=4)}\n"
            )
            logging.debug(f"Supposed uploaded objects [{len(filtered_uris)}]: {json.dumps(filtered_uris, indent=4)}\n")

    except Exception as e:
        logging.error(f"Failed to commit transaction on target ETP client: {e}")
        print(e)
        return


if __name__ == "__main__":

    logging.basicConfig(level=logging.DEBUG, filename="logs/etpscript.log", filemode="w")

    etp_client_source = start_client()
    print(etp_client_source.get_dataspaces())
    target = start_client(ETPConfig(os.environ.get("INI_FILE_PATH_2")))
    dataspace_out = "geosiris/volve"
    # dataspace_out = "test-workflow-aws"
    # target = Epc(epc_file_path="D:/pyetpclient_tranfert.epc")

    transfert_data(
        etp_client_source=etp_client_source,
        etp_client_target=DataStorage(etp_client=target, dataspace=dataspace_out),
        # dataspace_target="default",
        uris=[
            # "eml:///dataspace('demo/Volve')/resqml20.obj_GridConnectionSetRepresentation(2efbb020-a489-4037-87b0-7204784f7c0c)"
            # "eml:///dataspace('demo/Volve')/resqml20.obj_DiscreteProperty(1d189a27-2f6e-445e-8720-58eb7e8e3ddf)"
            # "eml:///dataspace('demo/Volve')/resqml20.TriangulatedSetRepresentation(092fd2e8-6ab0-4076-8b8b-912e6112dfa1)"
            # "eml:///dataspace('demo/Volve')/resqml20.obj_PolylineSetRepresentation(3befef85-a866-479a-b41e-ef24036087a0)"  # aws f52
            "eml:///dataspace('demo/Volve')/resqml20.obj_PolylineSetRepresentation(2e497a63-4dac-4da3-96f0-c57ff29f6e75)",  # aws f3
            "eml:///dataspace('demo/Volve')/resqml20.obj_PolylineSetRepresentation(b013f6c9-43c4-408d-8c4a-42b8ab337d0c)",  # aws f8
            # "eml:///dataspace('demo/Volve')/resqml20.obj_PolylineSetRepresentation(a1753655-3aac-43ad-a146-84cc821654ae)",  # aws f10
            # "eml:///dataspace('demo/Volve')/resqml20.obj_PolylineSetRepresentation(ae7a4a88-f54c-4516-8987-31a61b8108b7)",  # aws f20
        ],
        include_references=True,
        timeouts=120,
    )


if __name__ == "__main__2":
    logging.basicConfig(level=logging.DEBUG, filename="logs/etpscript.log", filemode="w")

    etp_client_source = start_client()
    # target = Epc()
    target = Epc(epc_file_path="data/grid-aws-2.epc")
    # target = Epc(epc_file_path="D:/pyetpclient_tranfert.epc")

    transfert_data(
        etp_client_source=etp_client_source,
        etp_client_target=DataStorage(epc=target),
        # dataspace_target="default",
        uris=[
            # "eml:///dataspace('volve-eqn-plus')/resqml20.obj_PolylineSetRepresentation(38bf3283-9514-43ab-81e3-17080dc5826f)"
            # "eml:///dataspace('demo/Volve')/resqml20.obj_GridConnectionSetRepresentation(2efbb020-a489-4037-87b0-7204784f7c0c)"
            "eml:///dataspace('demo/Volve')/resqml20.obj_PolylineSetRepresentation(3befef85-a866-479a-b41e-ef24036087a0)"  # aws f52
        ],
        include_references=True,
        timeouts=300,
    )
