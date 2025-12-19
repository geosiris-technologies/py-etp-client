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
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
from energyml.utils.uri import Uri as ETPUri, parse_uri
from energyml.utils.introspection import get_obj_identifier, get_obj_uri, get_obj_version, get_obj_title
from energyml.utils.constants import qualified_type_to_content_type
from energyml.utils.epc import Epc, create_h5_external_relationship
from energyml.utils.epc_stream import EpcStreamReader
from energyml.utils.constants import content_type_to_qualified_type

from py_etp_client import Resource
from py_etp_client.etpclient import ETPClient

from energyml.utils.storage_interface import EnergymlStorageInterface, DataArrayMetadata, ResourceMetadata


# class EnergymlWorkspace(ABC):
#     """
#     Abstract base class for energyml data storage operations.

#     This interface defines a common API for interacting with energyml objects and arrays,
#     regardless of whether they are stored on an ETP server or in a local EPC file.

#     All implementations must provide methods for:
#     - Getting, putting, and deleting energyml objects
#     - Reading and writing data arrays
#     - Listing available objects
#     - Closing the storage connection
#     """

#     @abstractmethod
#     def get_object(self, uri: Union[str, ETPUri]) -> Optional[Any]:
#         """
#         Retrieve a deserialized energyml object by URI.

#         Args:
#             uri: The URI of the object to retrieve

#         Returns:
#             The deserialized energyml object, or None if not found
#         """
#         pass

#     @abstractmethod
#     def put_object(self, obj: Any, dataspace: Optional[str] = None) -> Optional[str]:
#         """
#         Store an energyml object.

#         Args:
#             obj: The energyml object to store
#             dataspace: Optional dataspace name (used for ETP storage)

#         Returns:
#             The URI of the added object if successful, None otherwise
#         """
#         pass

#     @abstractmethod
#     def delete_object(self, uri: Union[str, ETPUri]) -> bool:
#         """
#         Delete an energyml object by URI.

#         Args:
#             uri: The URI of the object to delete

#         Returns:
#             True if successful, False otherwise
#         """
#         pass

#     @abstractmethod
#     def get_array(self, uri: Union[str, ETPUri], path_in_resource: str) -> Optional[np.ndarray]:
#         """
#         Get a data array from storage.

#         Args:
#             uri: The URI of the object containing the array
#             path_in_resource: The path to the array within the resource (e.g., HDF5 path)

#         Returns:
#             The data array as a numpy array, or None if not found
#         """
#         pass

#     def read_array(self, proxy: Union[str, ETPUri, Any], path_in_external: str) -> Optional[np.ndarray]:
#         """
#         Get array from HDF5 external file associated with this EPC stream.

#         Args:
#             proxy: The URI of the object containing the array reference or the object itself
#             path_in_external: The path within the HDF5 file
#         return self.stream_reader.read_array(proxy, path_in_external)
#         Returns:
#             The data array as a numpy array, or None if not found
#         """
#         if not isinstance(proxy, (str, ETPUri)):
#             # Get URI from object without dataspace (subclass should override if needed)
#             uri = get_obj_uri(obj=proxy, dataspace=None)
#         else:
#             uri = proxy
#         return self.get_array(uri, path_in_external)

#     @abstractmethod
#     def put_array(
#         self,
#         uri: Union[str, ETPUri],
#         path_in_resource: str,
#         array: np.ndarray,
#     ) -> bool:
#         """
#         Put a data array to storage.

#         Args:
#             uri: The URI of the object containing the array
#             path_in_resource: The path to the array within the resource (e.g., HDF5 path)
#             array: The numpy array to store

#         Returns:
#             True if successful, False otherwise
#         """
#         pass

#     @abstractmethod
#     def list_objects(self, dataspace: Optional[str] = None) -> List[str]:
#         """
#         List available object URIs.

#         Args:
#             dataspace: Optional dataspace filter (used for ETP storage)

#         Returns:
#             List of object URIs
#         """
#         pass

#     @abstractmethod
#     def close(self):
#         """Close the storage connection and release resources."""
#         pass

#     @abstractmethod
#     def start_transaction(self):
#         """Start a transaction if supported by the storage backend."""
#         pass

#     @abstractmethod
#     def commit_transaction(self) -> Tuple[bool, Optional[str]]:
#         """Commit the current transaction if supported by the storage backend."""
#         return False, "Not implemented"

#     @abstractmethod
#     def rollback_transaction(self):
#         """Rollback the current transaction if supported by the storage backend."""
#         pass


# class ETPStorage(EnergymlWorkspace):
#     """
#     ETP server-based storage implementation.

#     This implementation uses an ETPClient to interact with energyml data stored on
#     an ETP server. It handles data objects, arrays, and dataspaces through the ETP protocol.

#     Args:
#         client: An initialized ETPClient instance
#     """

#     CACHED_URIS: Optional[Dict[str, List[str]]]

#     def __init__(
#         self, client: "ETPClient", dataspace: Optional[str] = None, use_cache: bool = True, default_timeout: int = 30
#     ):  # noqa: F821
#         """
#         Initialize ETP storage with a client.

#         Args:
#             client: An ETPClient instance (should be started before use)
#         """
#         self.client = client
#         self.dataspace = dataspace
#         self.CACHED_URIS = {} if use_cache else None
#         self.use_cache = use_cache
#         self.default_timeout = default_timeout

#     def get_object(self, uri: Union[str, ETPUri]) -> Optional[Any]:
#         """
#         Retrieve an object from the ETP server.

#         Args:
#             uri: The URI of the object to retrieve

#         Returns:
#             The deserialized energyml object, or None if not found or on error
#         """
#         _uri = uri if isinstance(uri, ETPUri) else parse_uri(uri)  # type: ignore
#         if _uri is None:
#             return None
#         if _uri.dataspace is None and self.dataspace is not None:
#             _uri.dataspace = self.dataspace
#         result = self.client.get_data_object_as_obj(_uri, format_="xml", timeout=self.default_timeout)
#         return result if not isinstance(result, Exception) else None

#     def put_object(self, obj: Any, dataspace: Optional[str] = None) -> Optional[str]:
#         """
#         Store an object on the ETP server.

#         Args:
#             obj: The energyml object to store
#             dataspace: The dataspace name (defaults to empty string)

#         Returns:
#             The URI of the added object if successful, None otherwise
#         """
#         result = self.client.put_data_object_obj(obj, dataspace or self.dataspace, timeout=self.default_timeout)
#         return str(get_obj_uri(obj, self.dataspace)) if len(result) > 0 else None

#     def delete_object(self, uri: Union[str, ETPUri]) -> bool:
#         """
#         Delete an object from the ETP server.

#         Args:
#             uri: The URI of the object to delete

#         Returns:
#             True if the deletion was successful
#         """
#         _uri = uri if isinstance(uri, ETPUri) else parse_uri(uri)  # type: ignore
#         if _uri is None:
#             return False
#         if _uri.dataspace is None and self.dataspace is not None:
#             _uri.dataspace = self.dataspace
#         result = self.client.delete_data_object(_uri, timeout=self.default_timeout)
#         return len(result) > 0

#     def get_array(self, uri: Union[str, ETPUri], path_in_resource: str) -> Optional[np.ndarray]:
#         """
#         Get a data array from the ETP server.

#         Args:
#             uri: The URI of the object containing the array
#             path_in_resource: The path to the array within the resource

#         Returns:
#             The data array as a numpy array, or None if not found
#         """
#         _uri = uri if isinstance(uri, ETPUri) else parse_uri(uri)  # type: ignore
#         if _uri is None:
#             return None
#         if _uri.dataspace is None and self.dataspace is not None:
#             _uri.dataspace = self.dataspace
#         return self.client.get_data_array_safe(_uri, path_in_resource, timeout=self.default_timeout)

#     def put_array(
#         self,
#         uri: Union[str, ETPUri],
#         path_in_resource: str,
#         array: np.ndarray,
#     ) -> bool:
#         """
#         Put a data array to the ETP server.

#         Args:
#             uri: The URI of the object containing the array
#             path_in_resource: The path to the array within the resource
#             array: The numpy array to store

#         Returns:
#             True if the array was successfully stored
#         """
#         _uri = uri if isinstance(uri, ETPUri) else parse_uri(uri)  # type: ignore
#         if _uri is None:
#             return False
#         if _uri.dataspace is None and self.dataspace is not None:
#             _uri.dataspace = self.dataspace
#         result = self.client.put_data_array_safe(_uri, path_in_resource, array, timeout=self.default_timeout)
#         return result is not None and len(result) > 0

#     def list_objects(self, dataspace: Optional[str] = None) -> List[str]:
#         """
#         List available object URIs from the ETP server.

#         Args:
#             dataspace: Optional dataspace URI to filter results

#         Returns:
#             List of object URIs
#         """

#         if dataspace is None:
#             dataspace = self.dataspace

#         resources = self.client.get_resources(uri=dataspace, depth=1, timeout=self.default_timeout)
#         uris = [str(r.uri) for r in resources if hasattr(r, "uri")]  # type: ignore

#         if self.use_cache:
#             if self.CACHED_URIS is None:
#                 self.CACHED_URIS = {}
#             self.CACHED_URIS[dataspace or ""] = uris

#         return uris

#     def close(self):
#         """Close the ETP client connection."""
#         self.client.close()

#     def start_transaction(self):
#         """Start a transaction on the ETP client."""
#         self.client.start_transaction(self.dataspace, timeout=self.default_timeout)

#     def commit_transaction(self) -> Tuple[bool, Optional[str]]:
#         """Commit the current transaction on the ETP client."""
#         return self.client.commit_transaction_get_msg(timeout=self.default_timeout)

#     def rollback_transaction(self):
#         """Rollback the current transaction on the ETP client."""
#         self.client.rollback_transaction(timeout=self.default_timeout)


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

    def read_array(self, proxy: Union[str, ETPUri, Any], path_in_external: str) -> Optional[np.ndarray]:
        """
        Read a data array from external storage (HDF5).

        Args:
            proxy: The object identifier/URI or the object itself that references the array
            path_in_external: Path within the HDF5 file (e.g., 'values/0')

        Returns:
            The data array as a numpy array, or None if not found
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

        return self.client.get_data_array_safe(_uri, path_in_external, timeout=self.default_timeout)

    def write_array(
        self,
        proxy: Union[str, ETPUri, Any],
        path_in_external: str,
        array: np.ndarray,
    ) -> bool:
        """
        Write a data array to external storage (HDF5).

        Args:
            proxy: The object identifier/URI or the object itself that references the array
            path_in_external: Path within the HDF5 file (e.g., 'values/0')
            array: The numpy array to write

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

    def get_array_metadata(self, proxy: Union[str, ETPUri, Any], path_in_external: Optional[str] = None):
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

    def list_objects(self, dataspace: Optional[str] = None, object_type: Optional[str] = None):
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


# class EPCStorage(EnergymlWorkspace):
#     """
#     EPC file-based storage implementation.

#     This implementation uses an Epc object to interact with energyml data stored in
#     a local EPC file. Arrays are stored in associated HDF5 external files.

#     Args:
#         epc: An initialized Epc instance
#     """

#     def __init__(self, epc: Epc):
#         """
#         Initialize EPC storage with an Epc instance.

#         Args:
#             epc: An Epc instance (can be created from file or new)
#         """
#         self.epc = epc

#     def get_object(self, uri: Union[str, ETPUri]) -> Optional[Any]:
#         """
#         Retrieve an object from the EPC file.

#         Args:
#             uri: The URI or identifier of the object to retrieve

#         Returns:
#             The energyml object, or None if not found
#         """
#         return self.epc.get_object_by_identifier(str(uri))

#     def put_object(self, obj: Any, dataspace: Optional[str] = None) -> Optional[str]:
#         """
#         Add an object to the EPC file.

#         Note: The dataspace parameter is ignored for EPC storage.

#         Args:
#             obj: The energyml object to add
#             dataspace: Ignored for EPC storage

#         Returns:
#             The URI of the added object if successful, None otherwise
#         """
#         try:
#             if self.epc.add_object(obj):
#                 uri = get_obj_uri(obj)
#                 return str(uri) if uri else None
#         except Exception:
#             return None

#     def delete_object(self, uri: Union[str, ETPUri]) -> bool:
#         """
#         Delete an object from the EPC file.

#         Args:
#             uri: The URI or identifier of the object to delete

#         Returns:
#             True if the object was found and deleted, False otherwise
#         """
#         self.epc.remove_object(str(uri))
#         return True

#     def get_array(self, uri: Union[str, ETPUri], path_in_resource: str) -> Optional[np.ndarray]:
#         """
#         Get array from HDF5 external file associated with this EPC.

#         Args:
#             uri: The URI of the object containing the array reference
#             path_in_resource: The path within the HDF5 file

#         Returns:
#             The data array as a numpy array, or None if not found
#         """
#         return self.epc.read_array(uri, path_in_resource)

#     def put_array(
#         self,
#         uri: Union[str, ETPUri],
#         path_in_resource: str,
#         array: np.ndarray,
#     ) -> bool:
#         """
#         Put array to HDF5 external file associated with this EPC.

#         Note: This functionality requires additional HDF5 writing implementation.

#         Args:
#             uri: The URI of the object that will reference the array
#             path_in_resource: The path within the HDF5 file
#             array: The numpy array to store

#         Returns:
#             True if successful

#         Raises:
#             NotImplementedError: Array writing to EPC/HDF5 is not yet fully implemented
#         """
#         # TODO: Implement HDF5 writing using datasets_io functions
#         success = self.epc.write_array(uri, path_in_resource, array)
#         if not success:
#             self.epc.add_rels_for_object(
#                 uri,
#                 relationships=[
#                     create_h5_external_relationship(
#                         h5_path=re.sub(
#                             pattern=r"\.epc$",
#                             repl=".h5",
#                             string=str(self.epc.epc_file_path),
#                             flags=re.IGNORECASE,
#                         )
#                     )
#                 ],
#             )
#             success = self.epc.write_array(uri, path_in_resource, array)
#         return success

#     def list_objects(self, dataspace: Optional[str] = None) -> List[str]:
#         """
#         List all object identifiers in the EPC file.

#         Note: The dataspace parameter is ignored for EPC storage.

#         Args:
#             dataspace: Ignored for EPC storage

#         Returns:
#             List of object identifiers
#         """

#         return [str(get_obj_uri(obj)) for obj in self.epc.energyml_objects]

#     def close(self):
#         """
#         Close the EPC storage.

#         Note: EPC files don't require explicit closing, but this method is provided
#         for interface consistency.
#         """
#         pass

#     def save(self, file_path: str):
#         """
#         Save the EPC to a file.

#         Args:
#             file_path: The path where the EPC file should be saved
#         """
#         self.epc.export_file(file_path)

#     def start_transaction(self):
#         """EPC storage does not support transactions."""
#         pass

#     def commit_transaction(self) -> Tuple[bool, Optional[str]]:
#         """EPC storage does not support transactions."""
#         try:
#             self.save(self.epc.epc_file_path)
#             return True, None
#         except Exception as e:
#             return False, str(e)

#     def rollback_transaction(self):
#         """EPC storage does not support transactions."""
#         pass


# class EPCStreamStorage(EnergymlWorkspace):
#     """
#     Memory-efficient EPC stream-based storage implementation.

#     This implementation uses EpcStreamReader for lazy loading and caching,
#     making it ideal for handling very large EPC files with thousands of objects.

#     Features:
#     - Lazy loading: Objects loaded only when accessed
#     - Smart caching: LRU cache with configurable size
#     - Memory monitoring: Track memory usage and cache efficiency
#     - Same interface as EPCStorage for seamless switching

#     Args:
#         stream_reader: An EpcStreamReader instance
#     """

#     def __init__(self, stream_reader: EpcStreamReader):  # noqa: F821
#         """
#         Initialize stream-based storage.

#         Args:
#             stream_reader: An EpcStreamReader instance
#         """
#         self.stream_reader: EpcStreamReader = stream_reader

#     def get_object(self, uri: Union[str, ETPUri]) -> Optional[Any]:
#         """
#         Retrieve an object from the EPC stream.

#         Args:
#             uri: The URI or identifier of the object to retrieve

#         Returns:
#             The deserialized energyml object, or None if not found
#         """
#         # Determine if input is a URI or identifier
#         return self.stream_reader.get_object_by_identifier(uri)

#     def put_object(self, obj: Any, dataspace: Optional[str] = None) -> Optional[str]:
#         """
#         Add an object to the EPC stream.

#         Note: The dataspace parameter is ignored for EPC storage.

#         Args:
#             obj: The energyml object to add
#             dataspace: Ignored for EPC storage

#         Returns:
#             The URI of the added object if successful, None otherwise
#         """
#         try:
#             if self.stream_reader.add_object(obj) is not None:
#                 uri = get_obj_uri(obj)
#                 return str(uri) if uri else None
#         except Exception:
#             return None

#     def delete_object(self, uri: Union[str, ETPUri]) -> bool:
#         """
#         Delete an object from the EPC stream.

#         Args:
#             uri: The URI or identifier of the object to delete

#         Returns:
#             True if the object was found and deleted, False otherwise
#         """
#         return self.stream_reader.remove_object(str(uri))

#     def get_array(self, uri: Union[str, ETPUri], path_in_resource: str) -> Optional[np.ndarray]:
#         """
#         Get array from HDF5 external file associated with this EPC stream.

#         Args:
#             uri: The URI of the object containing the array reference
#             path_in_resource: The path within the HDF5 file

#         Returns:
#             The data array as a numpy array, or None if not found
#         """
#         return self.stream_reader.read_array(uri, path_in_resource)

#     def put_array(
#         self,
#         uri: Union[str, ETPUri],
#         path_in_resource: str,
#         array: np.ndarray,
#     ) -> bool:
#         """
#         Put array to HDF5 external file associated with this EPC stream.

#         Note: This functionality requires additional HDF5 writing implementation.

#         Args:
#             uri: The URI of the object that will reference the array
#             path_in_resource: The path within the HDF5 file
#             array: The numpy array to store

#         Returns:
#             True if successful

#         Raises:
#             NotImplementedError: Array writing to EPC/HDF5 is not yet fully implemented
#         """
#         success = False
#         try:
#             success = self.stream_reader.write_array(uri, path_in_resource, array)
#         except ValueError:
#             pass
#         if not success:
#             self.stream_reader.add_rels_for_object(
#                 uri,
#                 relationships=[
#                     create_h5_external_relationship(
#                         h5_path=re.sub(
#                             pattern=r"\.epc$",
#                             repl=".h5",
#                             string=str(self.stream_reader.epc_file_path),
#                             flags=re.IGNORECASE,
#                         )
#                     )
#                 ],
#             )
#             success = self.stream_reader.write_array(uri, path_in_resource, array)
#         return success

#     def list_objects(self, dataspace: Optional[str] = None) -> List[str]:
#         """
#         List all object URIs in the EPC stream.

#         Note: The dataspace parameter is ignored for EPC storage.
#         This method is memory-efficient as it uses cached metadata.

#         Args:
#             dataspace: Ignored for EPC storage

#         Returns:
#             List of object URIs
#         """
#         # Get metadata without loading full objects
#         return [
#             f"eml:///{content_type_to_qualified_type(m.content_type)}({m.uuid})"
#             for m in self.stream_reader.list_object_metadata()
#         ]

#     def close(self):
#         """
#         Close the EPC stream and release resources.

#         This clears the cache and closes the underlying file handle.
#         """
#         self.stream_reader.clear_cache()

#     def save(self, file_path: str):
#         """
#         Save the EPC stream to a file.

#         Note: This converts the stream to a full Epc instance before saving,
#         which loads all objects into memory.

#         Args:
#             file_path: The path where the EPC file should be saved
#         """
#         # copy the epc file to the new location
#         if file_path is not None:
#             shutil.copy(self.stream_reader.epc_file_path, file_path)

#     def get_statistics(self):
#         """
#         Get streaming statistics for monitoring performance.

#         Returns:
#             EpcStreamingStats object with cache hits, misses, and memory usage
#         """
#         return self.stream_reader.get_statistics()

#     def start_transaction(self):
#         """EPC storage does not support transactions."""
#         pass

#     def commit_transaction(self) -> Tuple[bool, Optional[str]]:
#         """EPC storage does not support transactions."""
#         try:
#             self.save(self.stream_reader.epc_file_path)
#             return True, None
#         except Exception as e:
#             return False, str(e)

#     def rollback_transaction(self):
#         """EPC storage does not support transactions."""
#         pass


# def create_storage(source: Union[str, ETPClient, Epc, EpcStreamReader]) -> EnergymlWorkspace:
#     """
#     Factory function to create an appropriate storage interface from various sources.

#     This convenience function automatically determines the correct storage implementation
#     based on the type of source provided.

#     Args:
#         source: Can be:
#             - ETPClient instance: Creates ETPStorage
#             - Epc instance: Creates EPCStorage
#             - EpcStreamReader instance: Creates EPCStreamStorage
#             - str (file path): Loads EPC file and creates EPCStorage

#     Returns:
#         An EnergymlStorage implementation (ETPStorage, EPCStorage, or EPCStreamStorage)

#     Raises:
#         ValueError: If the source type is not supported

#     Example:
#         ```python
#         # From ETP client
#         storage = create_storage(etp_client)

#         # From EPC instance
#         storage = create_storage(epc_instance)

#         # From EPC stream reader
#         from energyml.utils.epc_stream import EpcStreamReader
#         stream_reader = EpcStreamReader("large_file.epc", cache_size=50)
#         storage = create_storage(stream_reader)

#         # From file path
#         storage = create_storage("path/to/file.epc")
#         ```
#     """
#     # Import here to avoid circular dependency
#     from py_etp_client.etpclient import ETPClient

#     if isinstance(source, ETPClient):
#         return ETPStorage(source)
#     elif isinstance(source, Epc):
#         return EPCStorage(source)
#     elif isinstance(source, EpcStreamReader):
#         return EPCStreamStorage(source)
#     elif isinstance(source, str):
#         epc = Epc.read_file(source)
#         if epc is None:
#             raise ValueError(f"Failed to read EPC file: {source}")
#         return EPCStorage(epc)
#     else:
#         supported_types = "ETPClient, Epc, EpcStreamReader, or str (file path)"
#         raise ValueError(f"Unsupported source type: {type(source)}. Expected {supported_types}.")
