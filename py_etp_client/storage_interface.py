# Copyright (c) 2022-2023 Geosiris.
# SPDX-License-Identifier: Apache-2.0
"""
Unified Storage Interface Module

This module provides a unified interface for reading and writing energyml objects and arrays,
abstracting away whether the data comes from an ETP server or a local EPC file.

The storage interface enables applications to work with energyml data without knowing the
underlying storage mechanism, making it easy to switch between server-based and file-based
workflows.

Key Components:
- EnergymlStorage: Abstract base class defining the storage interface
- ETPStorage: Implementation for ETP server-based storage
- EPCStorage: Implementation for local EPC file-based storage
- create_storage: Factory function for creating storage instances

Example Usage:
    ```python
    from py_etp_client.storage_interface import create_storage
    from py_etp_client.etpclient import ETPClient

    # Use with ETP server
    client = ETPClient(url="wss://server.com", spec=None)
    client.start()
    storage = create_storage(client)

    # Use with EPC file
    storage = create_storage("my_data.epc")

    # Same API for both!
    obj = storage.get_object("eml:///dataspace('my-ds')/resqml20.obj(uuid)")
    array = storage.get_array(obj_uri, "values")
    storage.put_object(new_obj)
    storage.close()
    ```
"""

from abc import ABC, abstractmethod
import logging
import re
import shutil
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from energyml.opc.opc import Relationship
import numpy as np
from energyml.utils.uri import Uri as ETPUri, parse_uri
from energyml.utils.introspection import (
    get_obj_identifier,
    get_obj_uri,
    get_obj_version,
    get_obj_title,
    get_direct_dor_list,
)
from energyml.utils.constants import qualified_type_to_content_type, EPCRelsRelationshipType
from energyml.utils.epc import Epc, create_h5_external_relationship
from energyml.utils.epc_stream import EpcStreamReader
from energyml.utils.constants import content_type_to_qualified_type

from py_etp_client import Resource
from py_etp_client.etpclient import ETPClient

from energyml.utils.storage_interface import EnergymlStorageInterface, DataArrayMetadata, ResourceMetadata


def obj_to_metadata(obj: Any, dataspace: Optional[str] = None) -> ResourceMetadata:
    """
    Convert an energyml object to ResourceMetadata.

    Args:
        obj: The energyml object
        dataspace: Optional dataspace name

    Returns:
        ResourceMetadata instance
    """
    uri = get_obj_uri(obj, dataspace)
    uuid = uri.uuid or "" if uri else ""
    version = get_obj_version(obj)
    object_type = uri.object_type or "" if uri else ""
    title = get_obj_title(obj) or ""
    qualified_type = uri.get_qualified_type() if uri else None
    return ResourceMetadata(
        uri=str(uri) if uri else "",
        uuid=uuid,
        title=title,
        object_type=object_type,
        content_type=qualified_type_to_content_type(qualified_type) or "" if qualified_type else "",
        version=version,
        dataspace=dataspace or (uri.dataspace if uri else None),
        source_count=None,
        target_count=None,
        custom_data={},
    )


def etp_resource_to_metadata(resource: Resource) -> ResourceMetadata:
    uri = parse_uri(resource.uri)
    object_type = uri.object_type or "" if uri else ""
    qualified_type = uri.get_qualified_type() if uri else None
    return ResourceMetadata(
        uri=str(resource.uri),
        uuid=uri.uuid or "" if uri else "",
        title=resource.name,
        object_type=object_type,
        content_type=qualified_type_to_content_type(qualified_type) or "" if qualified_type else "",
        version=uri.version or "" if uri else "",
        dataspace=uri.dataspace if uri else None,
        source_count=int(resource.source_count),
        target_count=int(resource.target_count),
        custom_data=resource.custom_data,
    )


def get_dor_identifiers_from_obj(obj: Any, dataspace: Optional[str] = None) -> Set[str]:
    """Get identifiers of all Data Object References (DORs) directly referenced by the given object."""
    identifiers = set()
    try:
        dor_list = get_direct_dor_list(obj)
        for dor in dor_list:
            try:
                identifier = get_obj_uri(obj=dor, dataspace=dataspace)
                if identifier:
                    identifiers.add(identifier)
            except Exception as e:
                logging.warning(f"Failed to extract identifier from DOR: {e}")
    except Exception as e:
        logging.warning(f"Failed to get DOR list from object: {e}")
    return identifiers


class ETPStorageWorkspace(EnergymlStorageInterface):
    """
    ETP server-based storage implementation conforming to EnergymlStorageInterface.

    This implementation uses an ETPClient to interact with energyml data stored on
    an ETP server. It handles data objects, arrays, and dataspaces through the ETP protocol.

    Args:
        client: An initialized ETPClient instance
        dataspace: Optional default dataspace for operations
        default_timeout: Timeout in seconds for ETP operations
    """

    CACHE_URIS: Dict[str, List[ResourceMetadata]]
    CACHE_OBJECTS: Dict[str, Any]

    def __init__(self, client: "ETPClient", dataspace: Optional[str] = None, default_timeout: int = 30):  # noqa: F821
        """
        Initialize ETP storage with a client.

        Args:
            client: An ETPClient instance (should be started before use)
            dataspace: Optional default dataspace
            default_timeout: Timeout in seconds for ETP operations
        """
        self.client = client
        self.dataspace = dataspace
        self.default_timeout = default_timeout
        self.CACHE_URIS = {}
        self.CACHE_OBJECTS = {}

    def clear_caches(self) -> None:
        """
        Clear the internal caches for URIs and objects.
        """
        self.CACHE_URIS.clear()
        self.CACHE_OBJECTS.clear()

    def get_object(self, identifier: Union[str, ETPUri]) -> Optional[Any]:
        """
        Retrieve an object by its identifier (UUID or UUID.version).

        Args:
            identifier: Object identifier (UUID or UUID.version) or ETP URI

        Returns:
            The deserialized energyml object, or None if not found
        """
        # Convert identifier to URI if needed
        _uri = identifier if isinstance(identifier, ETPUri) else parse_uri(identifier)  # type: ignore
        if _uri is None:
            return None

        if _uri.dataspace is None and self.dataspace is not None:
            _uri.dataspace = self.dataspace

        if str(_uri) in self.CACHE_OBJECTS:
            return self.CACHE_OBJECTS[str(_uri)]

        result = self.client.get_data_object_as_obj(_uri, format_="xml", timeout=self.default_timeout)
        if not isinstance(result, Exception):
            self.CACHE_OBJECTS[str(_uri)] = result
            return result
        else:
            return None

    def get_object_by_uuid(self, uuid: str) -> List[Any]:
        """
        Retrieve all objects with the given UUID (all versions).

        Args:
            uuid: Object UUID

        Returns:
            List of objects with this UUID (may be empty)
        """
        for cached_meta in self.CACHE_URIS.get(self.dataspace or "", []):
            parsed = parse_uri(cached_meta.uri)
            if parsed and parsed.uuid == uuid:
                obj = self.get_object(cached_meta.uri)
                if obj is not None:
                    return [obj]

        # Get resources matching this UUID
        resources = self.client.get_resources(uri=self.dataspace, depth=1, timeout=self.default_timeout)

        # Filter by UUID and get all matching objects
        objects = []
        for resource in resources:
            if not hasattr(resource, "uri"):
                continue
            uri_str = str(resource.uri)  # type: ignore
            if uri_str is not None:
                parsed = parse_uri(uri_str)
                if parsed and parsed.uuid == uuid:
                    obj = self.get_object(uri_str)
                    if obj is not None:
                        objects.append(obj)
                        self.CACHE_OBJECTS[uri_str] = obj

        return objects

    def put_object(self, obj: Any, dataspace: Optional[str] = None) -> Optional[str]:
        """
        Store an energyml object.

        Args:
            obj: The energyml object to store
            dataspace: Optional dataspace name (primarily for ETP)

        Returns:
            The identifier of the stored object (UUID.version or UUID), or None on error
        """
        result = self.client.put_data_object_obj(obj, dataspace or self.dataspace, timeout=self.default_timeout)
        if result is not None and len(result) > 0:
            uri = str(get_obj_uri(obj, dataspace or self.dataspace))
            return uri
        return None

    def delete_object(self, identifier: Union[str, ETPUri]) -> bool:
        """
        Delete an object by its identifier.

        Args:
            identifier: Object identifier (UUID or UUID.version) or ETP URI

        Returns:
            True if successfully deleted, False otherwise
        """
        _uri = identifier if isinstance(identifier, ETPUri) else parse_uri(identifier)  # type: ignore
        if _uri is None:
            return False

        if _uri.dataspace is None and self.dataspace is not None:
            _uri.dataspace = self.dataspace

        result = self.client.delete_data_object(_uri, timeout=self.default_timeout)
        return len(result) > 0

    def read_array(
        self,
        proxy: Union[str, ETPUri, Any],
        path_in_external: str,
        start_indices: Optional[List[int]] = None,
        counts: Optional[List[int]] = None,
        external_uri: Optional[str] = None,
    ) -> Optional[np.ndarray]:
        """
        Read a data array from external storage (HDF5) with optional sub-selection.

        Args:
            proxy: The object identifier/URI or the object itself that references the array
            path_in_external: Path within the HDF5 file (e.g., 'values/0')
            start_indices: Optional start index for each dimension (RESQML v2.2 StartIndex)
            counts: Optional count of elements for each dimension (RESQML v2.2 Count)
            external_uri: Optional URI to override default file path (RESQML v2.2 URI)

        Returns:
            The data array as a numpy array, or None if not found.
            If start_indices and counts are provided, returns the sub-selected portion.

        """
        # Convert proxy to URI if it's an object
        if not isinstance(proxy, (str, ETPUri)):
            uri = get_obj_uri(obj=proxy, dataspace=self.dataspace)
        else:
            uri = proxy

        _uri = uri if isinstance(uri, ETPUri) else parse_uri(uri)
        if _uri is None:
            return None
        if _uri.dataspace is None and self.dataspace is not None:
            _uri.dataspace = self.dataspace

        array = self.client.get_data_array_safe(_uri, path_in_external, timeout=self.default_timeout)

        if isinstance(array, np.ndarray):
            # modify array if start_indices and counts are provided
            if start_indices is not None and counts is not None:
                slices = tuple(slice(start, start + count) for start, count in zip(start_indices, counts))
                array = array[slices]
            return array
        else:
            logging.warning(f"Failed to read array at path '{path_in_external}' for URI '{_uri}': {array}")
            return None

    def write_array(
        self,
        proxy: Union[str, ETPUri, Any],
        path_in_external: str,
        array: np.ndarray,
        start_indices: Optional[List[int]] = None,
        external_uri: Optional[str] = None,
        **kwargs,
    ) -> bool:
        """
        Write a data array to external storage (HDF5).

        Args:
            proxy: The object identifier/URI or the object itself that references the array
            path_in_external: Path within the HDF5 file (e.g., 'values/0')
            array: The numpy array to write
            start_indices: Optional start indices for writing a subset of the array

        Returns:
            True if successfully written, False otherwise
        """
        # Convert proxy to URI if it's an object
        if not isinstance(proxy, (str, ETPUri)):
            uri = get_obj_uri(obj=proxy, dataspace=self.dataspace)
        else:
            uri = proxy

        _uri = uri if isinstance(uri, ETPUri) else parse_uri(uri)  # type: ignore
        if _uri is None:
            return False
        if _uri.dataspace is None and self.dataspace is not None:
            _uri.dataspace = self.dataspace

        result = self.client.put_data_array_safe(_uri, path_in_external, array, timeout=self.default_timeout)
        return result is not None and len(result) > 0

    def get_array_metadata(
        self,
        proxy: Union[str, ETPUri, Any],
        path_in_external: Optional[str] = None,
        start_indices: Optional[List[int]] = None,
        counts: Optional[List[int]] = None,
    ):
        """
        Get metadata for data array(s).

        Args:
            proxy: The object identifier/URI or the object itself that references the array
            path_in_external: Optional specific path. If None, returns all array metadata for the object

        Returns:
            DataArrayMetadata if path specified, List[DataArrayMetadata] if no path,
            or None if not found
        """

        # Convert proxy to URI if it's an object
        if not isinstance(proxy, (str, ETPUri)):
            uri = get_obj_uri(obj=proxy, dataspace=self.dataspace)
        else:
            uri = proxy

        if path_in_external is None:
            # Return all array metadata for the object - not easily supported by ETP
            # Would need to inspect the object structure
            raise NotImplementedError("Getting all array metadata without path not supported for ETP storage")

        # Get metadata for specific path
        metadata_dict = self.client.get_data_array_metadata(uri, path_in_external, timeout=self.default_timeout)

        if not metadata_dict:
            return None

        # Convert ETP DataArrayMetadata to energyml DataArrayMetadata
        # Get first (and usually only) metadata entry
        etp_metadata = next(iter(metadata_dict.values()))

        # Get array type
        array_type = "unknown"
        if hasattr(etp_metadata, "arrayType"):
            array_type = str(etp_metadata.arrayType)  # type: ignore

        # Get dimensions
        dimensions: List[int] = []
        if hasattr(etp_metadata, "dimensions"):
            dimensions = [int(d) for d in etp_metadata.dimensions]  # type: ignore

        # Get custom data
        custom_data: Dict[str, Any] = {}
        if hasattr(etp_metadata, "custom_data") and etp_metadata.custom_data:  # type: ignore
            custom_data = dict(etp_metadata.custom_data)  # type: ignore

        return DataArrayMetadata(
            path_in_resource=path_in_external,
            array_type=array_type,
            dimensions=dimensions,
            custom_data=custom_data,
        )

    def list_objects(
        self, dataspace: Optional[str] = None, object_type: Optional[str] = None
    ) -> List[ResourceMetadata]:
        """
        List all objects with their metadata.

        Args:
            dataspace: Optional dataspace filter (primarily for ETP)
            object_type: Optional type filter (qualified type, e.g., 'resqml20.obj_Grid2dRepresentation')

        Returns:
            List of ResourceMetadata for all matching objects
        """

        if dataspace is None:
            dataspace = self.dataspace

        # Build type filter if provided
        types_filter = [object_type] if object_type else None

        resources = self.client.get_resources(
            uri=dataspace, depth=1, types_filter=types_filter, timeout=self.default_timeout
        )
        if isinstance(resources, Exception):
            logging.warning(f"Error retrieving resource: {resources}")
            return []

        # Convert ETP Resource objects to ResourceMetadata
        metadata_list = []
        for resource in resources:
            metadata = etp_resource_to_metadata(resource=resource)
            metadata_list.append(metadata)
            self.CACHE_URIS.setdefault(dataspace or "", []).append(metadata.uri)

        return metadata_list

    def get_obj_rels(self, obj: str | ETPUri | Any) -> List[Relationship]:
        """
        Get relationships for the specified object.

        Args:
            obj: The object identifier/URI or the object itself
        Returns:
            List of Relationship instances
        """
        # Makes a getResources with Sources and Targets to get relationships
        uri = obj if isinstance(obj, (str, ETPUri)) else get_obj_uri(obj, self.dataspace)
        obj_sources = self.client.get_resources(uri=uri, depth=0, scope="sources", timeout=self.default_timeout)
        obj_targets = self.client.get_resources(uri=uri, depth=0, scope="targets", timeout=self.default_timeout)
        relationships: List[Relationship] = []

        if isinstance(obj_sources, Exception):
            logging.warning(f"Error retrieving sources for {uri}: {obj_sources}")
        elif isinstance(obj_sources, list):
            for res in obj_sources:
                relationships.append(
                    Relationship(target=str(res.uri), type_value=EPCRelsRelationshipType.SOURCE_OBJECT.get_type())
                )

        if isinstance(obj_targets, Exception):
            logging.warning(f"Error retrieving targets for {uri}: {obj_targets}")
        elif isinstance(obj_targets, list):
            for res in obj_targets:
                relationships.append(
                    Relationship(target=str(res.uri), type_value=EPCRelsRelationshipType.DESTINATION_OBJECT.get_type())
                )
        return relationships

    def close(self) -> None:
        """
        Close the storage connection and release resources.
        """
        self.client.close()

    def start_transaction(self) -> bool:
        """
        Start a transaction (if supported).

        Returns:
            True if transaction started, False if not supported
        """
        try:
            self.client.start_transaction(self.dataspace, timeout=self.default_timeout)
            return True
        except Exception:
            return False

    def commit_transaction(self) -> Tuple[bool, Optional[str]]:
        """
        Commit the current transaction (if supported).

        Returns:
            Tuple of (success, transaction_uuid)
        """
        return self.client.commit_transaction_get_msg(timeout=self.default_timeout)

    def rollback_transaction(self) -> bool:
        """
        Rollback the current transaction (if supported).

        Returns:
            True if rolled back successfully
        """
        try:
            self.client.rollback_transaction(timeout=self.default_timeout)
            return True
        except Exception:
            return False

    def get_object_dependencies(self, identifier: Union[str, ETPUri]) -> List[str]:
        return list(get_dor_identifiers_from_obj(self.get_object(identifier)))
