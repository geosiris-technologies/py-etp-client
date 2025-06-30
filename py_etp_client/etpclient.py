# Copyright (c) 2022-2023 Geosiris.
# SPDX-License-Identifier: Apache-2.0
import json
import logging
from typing import Any, Dict, List, Optional, Union

import numpy as np
from energyml.utils.uri import Uri as ETPUri
from energyml.utils.epc import Epc
from energyml.utils.constants import epoch
from energyml.utils.serialization import (
    read_energyml_json_bytes,
    read_energyml_json_str,
    read_energyml_xml_bytes,
    read_energyml_xml_str,
)

from py_etp_client.etpsimpleclient import ETPSimpleClient
from py_etp_client import RequestSession, GetDataObjects
from etpproto.connection import ETPConnection, ConnectionType


from py_etp_client.requests import (
    _create_data_object,
    get_any_array,
    get_dataspaces,
    get_resources,
    get_supported_types,
    put_dataspace,
    delete_dataspace,
)
from py_etp_client import (
    Authorize,
    AuthorizeResponse,
    CommitTransaction,
    CommitTransactionResponse,
    DataArray,
    DataArrayIdentifier,
    DataArrayMetadata,
    Dataspace,
    DeleteDataObjects,
    DeleteDataObjectsResponse,
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
    PutDataArraysType,
    PutDataObjects,
    PutDataObjectsResponse,
    PutDataspacesResponse,
    RollbackTransaction,
    RollbackTransactionResponse,
    StartTransaction,
    StartTransactionResponse,
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
            return read_energyml_json_bytes(data)
    else:
        raise ValueError("data must be a string or bytes")


class ETPClient(ETPSimpleClient):
    def __init__(
        self,
        url,
        spec: Optional[ETPConnection],
        access_token: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        headers: Optional[dict] = None,
        verify: Optional[Any] = None,
        req_session: Optional[RequestSession] = None,
    ):
        super().__init__(
            url=url,
            spec=spec,
            access_token=access_token,
            username=username,
            password=password,
            headers=headers,
            verify=verify,
            req_session=req_session,
        )

        self.active_transaction = None

    #    ______
    #   / ____/___  ________
    #  / /   / __ \/ ___/ _ \
    # / /___/ /_/ / /  /  __/
    # \____/\____/_/   \___/

    def ping(self, timeout: Optional[int] = 5) -> bool:
        """Ping the server.

        Args:
            timeout (Optional[int], optional): Defaults to 5.

        Returns:
            bool: True if the server is reachable
        """
        ping_msg_list = self.send_and_wait(Ping(current_date_time=epoch()), timeout=timeout)
        for ping_msg in ping_msg_list:
            if isinstance(ping_msg.body, ProtocolException):
                return False
        return True

    def authorize(
        self, authorization: str, supplementalAuthorization: Optional[dict] = None, timeout: Optional[int] = 5
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
        return auth_msg_list[0].body

    #     ____        __
    #    / __ \____ _/ /_____ __________  ____ _________
    #   / / / / __ `/ __/ __ `/ ___/ __ \/ __ `/ ___/ _ \
    #  / /_/ / /_/ / /_/ /_/ (__  ) /_/ / /_/ / /__/  __/
    # /_____/\__,_/\__/\__,_/____/ .___/\__,_/\___/\___/
    #                           /_/
    def get_dataspaces(self, timeout: Optional[int] = 5) -> List[Dataspace]:
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
        self, dataspace_names: List[str], custom_data=None, timeout: Optional[int] = 5
    ) -> Union[Dict[str, Any], ProtocolException]:
        """
        @deprecated: Use put_dataspaces_with_acl instead.
        Put dataspaces.

        /!\\ In the future, for OSDU RDDMS, custom data will HAVE to contains acl and legalTags

        Args:
            dataspace_names (List[str]): List of dataspace names
            timeout (Optional[int], optional): Defaults to 5.
        """
        if isinstance(dataspace_names, str):
            dataspace_names = [dataspace_names]
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
        dataspace_names: List[str],
        acl_owners: Union[str, List[str]],
        acl_viewers: Union[str, List[str]],
        legal_tags: Union[str, List[str]],
        other_relevant_data_countries: Union[str, List[str]],
        timeout: Optional[int] = 5,
    ) -> Union[Dict[str, Any], ProtocolException]:
        """Put dataspaces with ACL and legal tags.
        /!\\ In the future, for OSDU RDDMS, custom data will HAVE to contains acl and legalTags
        See. https://community.opengroup.org/osdu/platform/domain-data-mgmt-services/reservoir/open-etp-server/-/issues/168#note_370528
        and https://community.opengroup.org/osdu/platform/domain-data-mgmt-services/reservoir/open-etp-server#osdu-integration

        Args:
            dataspace_names (List[str]): List of dataspace names
            acl_owners (Union[str, List[str]]): a list of owners or a json representation of a list of owners
            acl_viewers (Union[str, List[str]]): a list of viewers or a json representation of a list of viewers
            legal_tags (Union[str, List[str]]): a list of legal tags or a json representation of a list of legal tags
            other_relevant_data_countries (Union[str, List[str]]): a list of other relevant data countries or a json representation of a list of other relevant data countries
            timeout (Optional[int], optional): _description_. Defaults to 5.

        Returns:
            Union[Dict[str, Any], ProtocolException]:
        """
        if isinstance(dataspace_names, str):
            dataspace_names = [dataspace_names]

        # Checking ACLs
        if isinstance(acl_owners, str):
            owners_obj = json.loads(acl_owners)
            if isinstance(owners_obj, list):
                acl_owners = owners_obj
            else:
                acl_owners = [acl_owners]

        if isinstance(acl_owners, list):
            acl_owners = json.dumps(acl_owners)

        if isinstance(acl_viewers, str):
            viewers_obj = json.loads(acl_viewers)
            if isinstance(viewers_obj, list):
                acl_viewers = viewers_obj
            else:
                acl_viewers = [acl_viewers]

        if isinstance(acl_viewers, list):
            acl_viewers = json.dumps(acl_viewers)

        # Checking legal tags
        if isinstance(legal_tags, str):
            legal_tags_obj = json.loads(legal_tags)
            if isinstance(legal_tags_obj, list):
                legal_tags = legal_tags_obj
            else:
                legal_tags = [legal_tags]

        if isinstance(legal_tags, list):
            legal_tags = json.dumps(legal_tags)

        # Checking other relevant data countries
        if isinstance(other_relevant_data_countries, str):
            other_relevant_data_countries_obj = json.loads(other_relevant_data_countries)
            if isinstance(other_relevant_data_countries_obj, list):
                other_relevant_data_countries = other_relevant_data_countries_obj
            else:
                other_relevant_data_countries = [other_relevant_data_countries]

        if isinstance(other_relevant_data_countries, list):
            other_relevant_data_countries = json.dumps(other_relevant_data_countries)

        return self.put_dataspace(
            dataspace_names=dataspace_names,
            custom_data={
                "viewers ": acl_viewers,
                "owners": acl_owners,
                "legaltags": legal_tags,
                "otherRelevantDataCountries": other_relevant_data_countries,
            },
            timeout=timeout,
        )

    def delete_dataspace(
        self, dataspace_names: List[str], timeout: Optional[int] = 5
    ) -> Union[Dict[str, Any], ProtocolException]:
        """Delete dataspaces.

        Args:
            dataspace_names (List[str]): List of dataspace names
            timeout (Optional[int], optional): Defaults to 5.
        """
        if isinstance(dataspace_names, str):
            dataspace_names = [dataspace_names]
        ddm_msg_list = self.send_and_wait(delete_dataspace(dataspace_names), timeout=timeout)
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
        self, uri: str, depth: int = 1, scope: str = "self", types_filter: List[str] = None, timeout=10
    ) -> Union[List[Any], ProtocolException]:
        """Get resources from the server.

        Args:
            uris (str): Uri of the object
            depth (int): Depth of the search
            scope (str): "self"|"targets"|"sources"|"sources_or_self"|"targets_or_self". Default is "self"
            types_filter (List[str]): Types of the objects
            timeout (int, optional): Defaults to 10.

        Returns:
            List[Resource]: List of resources
        """
        gr_msg_list = self.send_and_wait(get_resources(uri, depth, scope, types_filter), timeout=timeout)

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
        self, uri: Union[str, List[str]], scope: str = "target", timeout: int = 5
    ) -> List[str]:
        """Get all related objects uris from the server.

        Args:
            uri (str): Uri of the object
            timeout (int, optional): Defaults to 5.

        Returns:
            List[str]: List of uris
        """
        allready_checked = []
        to_check = []
        if isinstance(uri, str):
            to_check.append(uri)
        elif isinstance(uri, list):
            for u in uri:
                to_check.append(u)

        while len(to_check) > 0:
            uri = to_check.pop(0)
            allready_checked.append(uri)
            resources = self.get_resources(uri=uri, depth=2, scope=scope, timeout=timeout)
            for r in resources:
                try:
                    if r.uri not in allready_checked and r.uri not in to_check:
                        to_check.append(r.uri)
                except Exception as e:
                    logging.error("Error: %s", e)
                    continue

        return allready_checked

    def search_resource(self, dataspace: str, uuid: str, timeout: int = 5) -> List[str]:
        """Search for a resource in the server.

        Args:
            dataspace (str): Dataspace name
            uuid (str): UUID of the object
            timeout (int, optional): Defaults to 5.

        Returns:
            List[str]: List of uris
        """
        resources = self.get_resources(uri=dataspace, timeout=timeout)
        uris = []
        for r in resources:
            if uuid in r.uri:
                try:
                    uris.append(r.uri)
                except Exception as e:
                    logging.error("Error: %s", e)
                    continue
        return uris

    #    _____ __
    #   / ___// /_____  ________
    #   \__ \/ __/ __ \/ ___/ _ \
    #  ___/ / /_/ /_/ / /  /  __/
    # /____/\__/\____/_/   \___/

    def get_data_object(
        self, uris: Union[str, Dict, List], format_: str = "xml", timeout: Optional[int] = 5
    ) -> Union[Dict[str, str], List[str], str, ProtocolException]:
        """Get data object from the server.

        Args:
            uris (Union[str, Dict, List]): Uri(s) of the objects
            format (str, optional): "xml" | "json". Defaults to "xml".
            timeout (Optional[int], optional): Defaults to 5.

        Raises:
            ValueError: if uris is not a string, a dict or a list of strings

        Returns:
            Union[Dict[str, str], List[str], str]: Returns a dict of uris and data if uris is a dict, a list of data if uris is a list, or a single data if uris is a string
        """
        uris_dict = {}
        if isinstance(uris, str):
            uris_dict["0"] = uris
        elif isinstance(uris, dict):
            uris_dict = uris
        elif isinstance(uris, list):
            for i, u in enumerate(uris):
                uris_dict[str(i)] = u
        elif isinstance(uris, ETPUri):
            uris_dict["0"] = str(uris)
        else:
            raise ValueError("uri must be a string, a dict or a list of strings")

        for ui in uris_dict.keys():
            # remove starting and trailing spaces
            uris_dict[ui] = uris_dict[ui].strip()

        gdor_msg_list = self.send_and_wait(GetDataObjects(uris=uris_dict, format_=format_), timeout=timeout)
        data_obj = {}

        for gdor in gdor_msg_list:
            if isinstance(gdor.body, GetDataObjectsResponse):
                data_obj.update({k: v.data for k, v in gdor.body.data_objects.items()})
            else:
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
        self, uris: Union[str, Dict, List], format_: str = "xml", timeout: Optional[int] = 5
    ) -> Union[Dict[str, Any], List[Any], Any, ProtocolException]:
        # TODO : test if energyml.resqml or energyml.witsml exists in the dependencies
        objs = self.get_data_object(
            uris=uris,
            format_=format_,
            timeout=timeout,
        )

        if isinstance(objs, str):
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
        self, obj_content: Union[str, List], dataspace_name: str, timeout: int = 5
    ) -> Dict[str, Any]:
        """Put data object to the server.

        Args:
            obj_content (str): An xml or json representation of an energyml object.
            dataspace_name (str): Dataspace name
            timeout (int, optional): Defaults to 5.
        """
        if not isinstance(obj_content, list):
            obj_content = [obj_content]

        do_dict = {}
        for o in obj_content:
            do_dict[str(len(do_dict))] = _create_data_object(obj_as_str=o, dataspace_name=dataspace_name)

        # do_dict = {"0": _create_data_object(obj_as_str=obj_content, dataspace_name=dataspace_name)}

        pdor_msg_list = self.send_and_wait(PutDataObjects(data_objects=do_dict), timeout=timeout)

        res = {}
        for pdor in pdor_msg_list:
            if isinstance(pdor.body, PutDataObjectsResponse):
                res.update(pdor.body.success)
            else:
                logging.error("Error: %s", pdor.body)
        return res

    def put_data_object_obj(
        self, obj: Any, dataspace_name: str, format_: str = "xml", timeout: int = 5
    ) -> Dict[str, Any]:
        """Put data object to the server.

        Args:
            obj (Any): An object that must be an instance of a class from energyml.(witsml|resqml|prodml|eml) python module or at least having the similar attributes, OR a list of such objects.
            dataspace_name (str): Dataspace name
            timeout (int, optional): Defaults to 5.
        """
        if not isinstance(obj, list):
            obj = [obj]

        do_dict = {}
        for o in obj:
            do_dict[str(len(do_dict))] = _create_data_object(obj=o, dataspace_name=dataspace_name, format=format_)

        pdor_msg_list = self.send_and_wait(PutDataObjects(data_objects=do_dict), timeout=timeout)

        res = {}
        for pdor in pdor_msg_list:
            if isinstance(pdor.body, PutDataObjectsResponse):
                res.update(pdor.body.success)
            else:
                logging.error("Error: %s", pdor.body)
        return res

    def delete_data_object(self, uris: Union[str, Dict, List], timeout: Optional[int] = 5) -> Dict[str, Any]:
        """Delete data object from the server.

        Args:
            uris (Union[str, Dict, List]): Uri(s) of the objects
            timeout (Optional[int], optional): Defaults to 5.

        Raises:
            ValueError: if uris is not a string, a dict or a list of strings

        Returns:
            Dict[str, Any]: A map of uri and a boolean indicating if the object has been successfully deleted
        """
        uris_dict = {}
        if isinstance(uris, str):
            uris_dict["0"] = uris
        elif isinstance(uris, dict):
            uris_dict = uris
        elif isinstance(uris, list):
            for i, u in enumerate(uris):
                uris_dict[str(i)] = u
        else:
            raise ValueError("uri must be a string, a dict or a list of strings")

        gdor_msg_list = self.send_and_wait(DeleteDataObjects(uris=uris_dict), timeout=timeout)
        res = {}
        for gdor in gdor_msg_list:
            if isinstance(gdor.body, DeleteDataObjectsResponse):
                res.update(gdor.body.deleted_uris)
            else:
                logging.error("Error: %s", gdor.body)
        return res

    def put_data_object_file(
        self, file_path: Union[List[str], str], dataspace_name: Optional[str] = None, timeout: int = 5
    ):
        """Put data object to the server.

        Args:
            file_path (Union[List[str], str]): Path to the file(s) to be uploaded
            dataspace_name (str): Dataspace name
            timeout (int, optional): Defaults to 5.
        """
        if isinstance(file_path, str):
            file_path = [file_path]

        do_dict = {}
        for f in file_path:
            if f.endswith(".xml") or f.endswith(".json"):
                with open(f, "r") as file:
                    file_content = file.read()
                    do_dict[len(do_dict)] = _create_data_object(obj_as_str=file_content, dataspace_name=dataspace_name)
            elif f.endswith(".epc"):
                epc = Epc.read_file(f)
                for obj in epc.energyml_objects:
                    if obj is not None:
                        do_dict[len(do_dict)] = _create_data_object(obj=obj, dataspace_name=dataspace_name)

        pdor_msg_list = self.send_and_wait(PutDataObjects(data_objects=do_dict), timeout=timeout)

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

    #     ____        __        ___
    #    / __ \____ _/ /_____ _/   |  ______________ ___  __
    #   / / / / __ `/ __/ __ `/ /| | / ___/ ___/ __ `/ / / /
    #  / /_/ / /_/ / /_/ /_/ / ___ |/ /  / /  / /_/ / /_/ /
    # /_____/\__,_/\__/\__,_/_/  |_/_/  /_/   \__,_/\__, /
    #                                              /____/

    def get_data_array(self, uri: str, path_in_resource: str, timeout: int = 5) -> np.ndarray:
        """Get an array from the server.

        Args:
            uri (str): Usually the uri should be an uri of an ExternalDataArrayPart or an ExternalPartReference.
            path_in_resource (str): path to the array. Must be the same than in the original object
            timeout (int, optional): Defaults to 5.

        Returns:
            np.ndarray: the array, reshaped in the correct dimension
        """
        gdar_msg_list = self.send_and_wait(
            GetDataArrays(dataArrays={"0": DataArrayIdentifier(uri=uri, path_in_resource=path_in_resource)}),
            timeout=timeout,
        )
        array = None
        for gdar in gdar_msg_list:
            if isinstance(gdar.body, GetDataArraysResponse) and "0" in gdar.body.data_arrays:
                # print(gdar)
                if array is None:
                    array = np.array(gdar.body.data_arrays["0"].data.item.values).reshape(
                        tuple(gdar.body.data_arrays["0"].dimensions)
                    )
                else:
                    array = np.concatenate(
                        (
                            array,
                            np.array(gdar.body.data_arrays["0"].data.item.values).reshape(
                                tuple(gdar.body.data_arrays["0"].dimensions)
                            ),
                        )
                    )
            else:
                logging.error("Error: %s", gdar.body)
        return array

    def get_data_subarray(
        self, uri: str, path_in_resource: str, start: List[int], count: List[int], timeout: int = 5
    ) -> np.ndarray:
        """Get a sub part of an array from the server.

        Args:
            uri (str): Usually the uri should be an uri of an ExternalDataArrayPart or an ExternalPartReference.
            path_in_resource (str): path to the array. Must be the same than in the original object
            start (List[int]): start indices in each dimensions.
            count (List[int]): Count of element in each dimensions.
            timeout (int, optional): Defaults to 5.

        Returns:
            np.ndarray: the array, NOT reshaped in the correct dimension. The result is a flat array !
        """
        gdar_msg_list = self.send_and_wait(
            GetDataSubarrays(
                dataArrays={
                    "0": GetDataSubarraysType(
                        uid=DataArrayIdentifier(uri=uri, pathInResource=path_in_resource),
                        start=start,
                        count=count,
                    )
                }
            ),
            timeout=timeout,
        )
        array = None
        for gdar in gdar_msg_list:
            if isinstance(gdar.body, GetDataSubarraysResponse) and "0" in gdar.body.data_arrays:
                print(gdar)
                if array is None:
                    array = np.array(gdar.body.data_subarrays["0"].data.item.values)
                else:
                    array = np.concatenate(
                        (array, np.array(gdar.body.data_subarrays["0"].data.item.values)),
                    )
            else:
                logging.error("Error: %s", gdar.body)
        return array

    def get_data_array_metadata(
        self, uri: str, path_in_resource: str, timeout: int = 5
    ) -> Dict[str, DataArrayMetadata]:
        """Get metadata of an array from the server.

        Args:
            uri (str): Usually the uri should be an uri of an ExternalDataArrayPart or an ExternalPartReference.
            path_in_resource (str): path to the array. Must be the same than in the original object
            timeout (int, optional): Defaults to 5.

        Returns:
            Dict[str, Any]: metadata of the array
        """
        gdar_msg_list = self.send_and_wait(
            GetDataArrayMetadata(dataArrays={"0": DataArrayIdentifier(uri=uri, pathInResource=path_in_resource)}),
            timeout=timeout,
        )
        metadata = {}
        for gdar in gdar_msg_list:
            if isinstance(gdar.body, GetDataArrayMetadataResponse):
                metadata.update(gdar.body.array_metadata)
            else:
                logging.error("Error: %s", gdar.body)
        return metadata

    def put_data_array(
        self,
        uri: str,
        path_in_resource: str,
        array_flat: Union[np.array, list],
        dimensions: List[int],
        timeout: int = 5,
    ) -> Dict[str, bool]:
        """Put a data array to the server.

        Args:
            uri (str): Usually the uri should be an uri of an ExternalDataArrayPart or an ExternalPartReference.
            path_in_resource (str): path to the array. Must be the same than in the original object
            array_flat (Union[np.array, list]): a flat array
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
                        uid=DataArrayIdentifier(uri=str(uri), path_in_resource=path_in_resource),
                        array=DataArray(dimensions=dimensions, data=get_any_array(array_flat)),
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
                logging.info("Data array put failed: %s", pdar.body)

        return res

    #    _____                              __           __   ______
    #   / ___/__  ______  ____  ____  _____/ /____  ____/ /  /_  __/_  ______  ___  _____
    #   \__ \/ / / / __ \/ __ \/ __ \/ ___/ __/ _ \/ __  /    / / / / / / __ \/ _ \/ ___/
    #  ___/ / /_/ / /_/ / /_/ / /_/ / /  / /_/  __/ /_/ /    / / / /_/ / /_/ /  __(__  )
    # /____/\__,_/ .___/ .___/\____/_/   \__/\___/\__,_/    /_/  \__, / .___/\___/____/
    #           /_/   /_/                                       /____/_/

    def get_supported_types(self, uri: str, count: bool = True, return_empty_types: bool = True, scope: str = "self"):
        """Get supported types.

        Args:
            uri (str): uri
            count (bool, optional): Defaults to True.
            return_empty_types (bool, optional): Defaults to True.
            scope (str, optional): Defaults to "self".

        Returns:
            [type]: [description]
        """
        gdar_msg_list = self.send_and_wait(
            get_supported_types(uri=uri, count=count, return_empty_types=return_empty_types, scope=scope)
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
        self, dataspace: Union[str, List[str]], readonly: bool = False, msg: str = "", timeout: int = 5
    ) -> Optional[int]:
        """Start a transaction.

        Args:
            dataspace (Union[str; List[str]]): Dataspace name or list of dataspace names
            or list of dataspace uris. If a list is provided, the transaction will be started on all the dataspaces.
            timeout (int, optional): Defaults to 5.

        Returns:
            int: transaction id
        """

        dataspaceUris = [dataspace] if isinstance(dataspace, str) else dataspace

        for i, ds in enumerate(dataspaceUris):
            if not ds.startswith("eml:///"):
                dataspaceUris[i] = f"eml:///dataspace('{ds}')"

        if self.active_transaction is not None:
            logging.warning("A transaction is already active, please commit it before starting a new one")
            return self.active_transaction
        else:
            str_msg_list = self.send_and_wait(
                StartTransaction(
                    dataspaceUris=dataspaceUris,
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
                RollbackTransaction(transaction_uuid=self.active_transaction), timeout=timeout
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
                CommitTransaction(transaction_uuid=self.active_transaction), timeout=timeout
            )
            for ctr_msg in ctr_msg_list:
                if isinstance(ctr_msg.body, CommitTransactionResponse) and ctr_msg.body.successful:
                    self.active_transaction = None
                    return True
                else:
                    logging.error("Error: %s", ctr_msg.body)

        return False
