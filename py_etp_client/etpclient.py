# Copyright (c) 2022-2023 Geosiris.
# SPDX-License-Identifier: Apache-2.0
import logging
from typing import Any, Dict, List, Optional, Union

import numpy as np
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
    ProtocolException,
    Dataspace,
    PutDataspacesResponse,
    DeleteDataspacesResponse,
    PutDataObjects,
    PutDataObjectsResponse,
    GetDataObjectsResponse,
    GetDataArrays,
    DataArrayIdentifier,
    GetDataArraysResponse,
    GetResourcesResponse,
    PutDataArrays,
    PutDataArraysType,
    DataArray,
    PutDataArraysResponse,
    GetDataSubarrays,
    GetDataSubarraysType,
    GetDataSubarraysResponse,
    GetDataArrayMetadata,
    GetDataArrayMetadataResponse,
    DataArrayMetadata,
    GetSupportedTypesResponse,
    StartTransaction,
    StartTransactionResponse,
    RollbackTransaction,
    RollbackTransactionResponse,
    CommitTransaction,
    CommitTransactionResponse,
    DeleteDataObjects,
    DeleteDataObjectsResponse,
)


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
            datasapaces.extend(gdr_msg.body.dataspaces)
        return datasapaces

    def put_dataspace(
        self, dataspace_names: List[str], custom_data=None, timeout: Optional[int] = 5
    ) -> Union[Dict[str, Any], ProtocolException]:
        """Put dataspaces.

        /!\\ In the future, for OSDU RDDMS, custom data will HAVE to contains acl and legalTags

        Args:
            dataspace_names (List[str]): List of dataspace names
            timeout (Optional[int], optional): Defaults to 5.
        """
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

    def delete_dataspace(
        self, dataspace_names: List[str], timeout: Optional[int] = 5
    ) -> Union[Dict[str, Any], ProtocolException]:
        """Delete dataspaces.

        Args:
            dataspace_names (List[str]): List of dataspace names
            timeout (Optional[int], optional): Defaults to 5.
        """
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
        self, uri: str, depth: int = 1, scope: str = None, types_filter: List[str] = None, timeout=10
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

    def put_data_object_str(self, obj_content: str, dataspace_name: str, timeout: int = 5) -> Dict[str, Any]:
        """Put data object to the server.

        Args:
            obj_content (str): An xml or json representation of an energyml object.
            dataspace_name (str): Dataspace name
            timeout (int, optional): Defaults to 5.
        """
        do_dict = {"0": _create_data_object(obj_as_str=obj_content, dataspace_name=dataspace_name)}

        pdor_msg_list = self.send_and_wait(PutDataObjects(data_objects=do_dict), timeout=timeout)

        res = {}
        for pdor in pdor_msg_list:
            if isinstance(pdor.body, PutDataObjectsResponse):
                res.update(pdor.body.success)
            else:
                logging.error("Error: %s", pdor.body)
        return res

    def put_data_object_obj(self, obj: Any, dataspace_name: str, timeout: int = 5) -> Dict[str, Any]:
        """Put data object to the server.

        Args:
            obj (Any): An object that must be an instance of a class from energyml.(witsml|resqml|prodml|eml) python module or at least having the similar attributes
            dataspace_name (str): Dataspace name
            timeout (int, optional): Defaults to 5.
        """
        if not isinstance(obj, list):
            obj = [obj]

        do_dict = {}
        for o in obj:
            do_dict[str(len(do_dict))] = _create_data_object(obj=o, dataspace_name=dataspace_name, format="xml")

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
            GetDataArrays(dataArrays={"0": DataArrayIdentifier(uri=uri, pathInResource=path_in_resource)})
        )
        array = None
        for gdar in gdar_msg_list:
            if isinstance(gdar.body, GetDataArraysResponse) and "0" in gdar.body.data_arrays:
                print(gdar)
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
            )
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
            GetDataArrayMetadata(dataArrays={"0": DataArrayIdentifier(uri=uri, pathInResource=path_in_resource)})
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
                        uid=DataArrayIdentifier(uri=uri, path_in_resource=path_in_resource),
                        array=DataArray(dimensions=dimensions, data=get_any_array(array_flat)),
                    )
                }
            )
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
