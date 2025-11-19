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
import re
import shutil
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
from energyml.utils.uri import Uri as ETPUri, parse_uri
from energyml.utils.introspection import get_obj_identifier, get_obj_uri
from energyml.utils.epc import Epc, create_h5_external_relationship
from energyml.utils.epc_stream import EpcStreamReader
from energyml.utils.constants import content_type_to_qualified_type

from py_etp_client.etpclient import ETPClient


class EnergymlWorkspace(ABC):
    """
    Abstract base class for energyml data storage operations.

    This interface defines a common API for interacting with energyml objects and arrays,
    regardless of whether they are stored on an ETP server or in a local EPC file.

    All implementations must provide methods for:
    - Getting, putting, and deleting energyml objects
    - Reading and writing data arrays
    - Listing available objects
    - Closing the storage connection
    """

    @abstractmethod
    def get_object(self, uri: Union[str, ETPUri]) -> Optional[Any]:
        """
        Retrieve a deserialized energyml object by URI.

        Args:
            uri: The URI of the object to retrieve

        Returns:
            The deserialized energyml object, or None if not found
        """
        pass

    @abstractmethod
    def put_object(self, obj: Any, dataspace: Optional[str] = None) -> Optional[str]:
        """
        Store an energyml object.

        Args:
            obj: The energyml object to store
            dataspace: Optional dataspace name (used for ETP storage)

        Returns:
            The URI of the added object if successful, None otherwise
        """
        pass

    @abstractmethod
    def delete_object(self, uri: Union[str, ETPUri]) -> bool:
        """
        Delete an energyml object by URI.

        Args:
            uri: The URI of the object to delete

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def get_array(self, uri: Union[str, ETPUri], path_in_resource: str) -> Optional[np.ndarray]:
        """
        Get a data array from storage.

        Args:
            uri: The URI of the object containing the array
            path_in_resource: The path to the array within the resource (e.g., HDF5 path)

        Returns:
            The data array as a numpy array, or None if not found
        """
        pass

    def read_array(self, proxy: Union[str, ETPUri, Any], path_in_external: str) -> Optional[np.ndarray]:
        """
        Get array from HDF5 external file associated with this EPC stream.

        Args:
            proxy: The URI of the object containing the array reference or the object itself
            path_in_external: The path within the HDF5 file
        return self.stream_reader.read_array(proxy, path_in_external)
        Returns:
            The data array as a numpy array, or None if not found
        """
        if not isinstance(proxy, (str, ETPUri)):
            uri = get_obj_uri(obj=proxy, dataspace=self.dataspace if hasattr(self, "dataspace") else None)
        else:
            uri = proxy
        return self.get_array(uri, path_in_external)

    @abstractmethod
    def put_array(
        self,
        uri: Union[str, ETPUri],
        path_in_resource: str,
        array: np.ndarray,
    ) -> bool:
        """
        Put a data array to storage.

        Args:
            uri: The URI of the object containing the array
            path_in_resource: The path to the array within the resource (e.g., HDF5 path)
            array: The numpy array to store

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def list_objects(self, dataspace: Optional[str] = None) -> List[str]:
        """
        List available object URIs.

        Args:
            dataspace: Optional dataspace filter (used for ETP storage)

        Returns:
            List of object URIs
        """
        pass

    @abstractmethod
    def close(self):
        """Close the storage connection and release resources."""
        pass

    @abstractmethod
    def start_transaction(self):
        """Start a transaction if supported by the storage backend."""
        pass

    @abstractmethod
    def commit_transaction(self) -> Tuple[bool, Optional[str]]:
        """Commit the current transaction if supported by the storage backend."""
        return False, "Not implemented"

    @abstractmethod
    def rollback_transaction(self):
        """Rollback the current transaction if supported by the storage backend."""
        pass


class ETPStorage(EnergymlWorkspace):
    """
    ETP server-based storage implementation.

    This implementation uses an ETPClient to interact with energyml data stored on
    an ETP server. It handles data objects, arrays, and dataspaces through the ETP protocol.

    Args:
        client: An initialized ETPClient instance
    """

    CACHED_URIS: Optional[Dict[str, List[str]]]

    def __init__(
        self, client: "ETPClient", dataspace: Optional[str] = None, use_cache: bool = True, default_timeout: int = 30
    ):  # noqa: F821
        """
        Initialize ETP storage with a client.

        Args:
            client: An ETPClient instance (should be started before use)
        """
        self.client = client
        self.dataspace = dataspace
        self.CACHED_URIS = {} if use_cache else None
        self.use_cache = use_cache
        self.default_timeout = default_timeout

    def get_object(self, uri: Union[str, ETPUri]) -> Optional[Any]:
        """
        Retrieve an object from the ETP server.

        Args:
            uri: The URI of the object to retrieve

        Returns:
            The deserialized energyml object, or None if not found or on error
        """
        _uri = uri if isinstance(uri, ETPUri) else parse_uri(uri)  # type: ignore
        if _uri is not None and _uri.dataspace is None and self.dataspace is not None:
            _uri.dataspace = self.dataspace
        result = self.client.get_data_object_as_obj(_uri, format_="xml", timeout=self.default_timeout)
        return result if not isinstance(result, Exception) else None

    def put_object(self, obj: Any, dataspace: Optional[str] = None) -> Optional[str]:
        """
        Store an object on the ETP server.

        Args:
            obj: The energyml object to store
            dataspace: The dataspace name (defaults to empty string)

        Returns:
            The URI of the added object if successful, None otherwise
        """
        result = self.client.put_data_object_obj(obj, dataspace or self.dataspace, timeout=self.default_timeout)
        return str(get_obj_uri(obj, self.dataspace)) if len(result) > 0 else None

    def delete_object(self, uri: Union[str, ETPUri]) -> bool:
        """
        Delete an object from the ETP server.

        Args:
            uri: The URI of the object to delete

        Returns:
            True if the deletion was successful
        """
        _uri = uri if isinstance(uri, ETPUri) else parse_uri(uri)  # type: ignore
        if _uri is not None and _uri.dataspace is None and self.dataspace is not None:
            _uri.dataspace = self.dataspace
        result = self.client.delete_data_object(_uri, timeout=self.default_timeout)
        return len(result) > 0

    def get_array(self, uri: Union[str, ETPUri], path_in_resource: str) -> Optional[np.ndarray]:
        """
        Get a data array from the ETP server.

        Args:
            uri: The URI of the object containing the array
            path_in_resource: The path to the array within the resource

        Returns:
            The data array as a numpy array, or None if not found
        """
        _uri = uri if isinstance(uri, ETPUri) else parse_uri(uri)  # type: ignore
        if _uri is not None and _uri.dataspace is None and self.dataspace is not None:
            _uri.dataspace = self.dataspace
        return self.client.get_data_array_safe(_uri, path_in_resource, timeout=self.default_timeout)

    def put_array(
        self,
        uri: Union[str, ETPUri],
        path_in_resource: str,
        array: np.ndarray,
    ) -> bool:
        """
        Put a data array to the ETP server.

        Args:
            uri: The URI of the object containing the array
            path_in_resource: The path to the array within the resource
            array: The numpy array to store

        Returns:
            True if the array was successfully stored
        """
        _uri = uri if isinstance(uri, ETPUri) else parse_uri(uri)  # type: ignore
        if _uri is not None and _uri.dataspace is None and self.dataspace is not None:
            _uri.dataspace = self.dataspace
        result = self.client.put_data_array_safe(_uri, path_in_resource, array, timeout=self.default_timeout)
        return result is not None and len(result) > 0

    def list_objects(self, dataspace: Optional[str] = None) -> List[str]:
        """
        List available object URIs from the ETP server.

        Args:
            dataspace: Optional dataspace URI to filter results

        Returns:
            List of object URIs
        """

        if dataspace is None:
            dataspace = self.dataspace

        resources = self.client.get_resources(uri=dataspace, depth=1, timeout=self.default_timeout)
        uris = [r.uri for r in resources if hasattr(r, "uri")]

        if self.use_cache:
            if self.CACHED_URIS is None:
                self.CACHED_URIS = {}
            self.CACHED_URIS[dataspace or ""] = uris

        return uris

    def close(self):
        """Close the ETP client connection."""
        self.client.close()

    def start_transaction(self):
        """Start a transaction on the ETP client."""
        self.client.start_transaction(self.dataspace, timeout=self.default_timeout)

    def commit_transaction(self) -> Tuple[bool, Optional[str]]:
        """Commit the current transaction on the ETP client."""
        return self.client.commit_transaction_get_msg(timeout=self.default_timeout)

    def rollback_transaction(self):
        """Rollback the current transaction on the ETP client."""
        self.client.rollback_transaction(timeout=self.default_timeout)


class EPCStorage(EnergymlWorkspace):
    """
    EPC file-based storage implementation.

    This implementation uses an Epc object to interact with energyml data stored in
    a local EPC file. Arrays are stored in associated HDF5 external files.

    Args:
        epc: An initialized Epc instance
    """

    def __init__(self, epc: Epc):
        """
        Initialize EPC storage with an Epc instance.

        Args:
            epc: An Epc instance (can be created from file or new)
        """
        self.epc = epc

    def get_object(self, uri: Union[str, ETPUri]) -> Optional[Any]:
        """
        Retrieve an object from the EPC file.

        Args:
            uri: The URI or identifier of the object to retrieve

        Returns:
            The energyml object, or None if not found
        """
        return self.epc.get_object_by_identifier(str(uri))

    def put_object(self, obj: Any, dataspace: Optional[str] = None) -> Optional[str]:
        """
        Add an object to the EPC file.

        Note: The dataspace parameter is ignored for EPC storage.

        Args:
            obj: The energyml object to add
            dataspace: Ignored for EPC storage

        Returns:
            The URI of the added object if successful, None otherwise
        """
        try:
            if self.epc.add_object(obj):
                uri = get_obj_uri(obj)
                return str(uri) if uri else None
        except Exception:
            return None

    def delete_object(self, uri: Union[str, ETPUri]) -> bool:
        """
        Delete an object from the EPC file.

        Args:
            uri: The URI or identifier of the object to delete

        Returns:
            True if the object was found and deleted, False otherwise
        """
        self.epc.remove_object(str(uri))
        return True

    def get_array(self, uri: Union[str, ETPUri], path_in_resource: str) -> Optional[np.ndarray]:
        """
        Get array from HDF5 external file associated with this EPC.

        Args:
            uri: The URI of the object containing the array reference
            path_in_resource: The path within the HDF5 file

        Returns:
            The data array as a numpy array, or None if not found
        """
        return self.epc.read_array(uri, path_in_resource)

    def put_array(
        self,
        uri: Union[str, ETPUri],
        path_in_resource: str,
        array: np.ndarray,
    ) -> bool:
        """
        Put array to HDF5 external file associated with this EPC.

        Note: This functionality requires additional HDF5 writing implementation.

        Args:
            uri: The URI of the object that will reference the array
            path_in_resource: The path within the HDF5 file
            array: The numpy array to store

        Returns:
            True if successful

        Raises:
            NotImplementedError: Array writing to EPC/HDF5 is not yet fully implemented
        """
        # TODO: Implement HDF5 writing using datasets_io functions
        success = self.epc.write_array(uri, path_in_resource, array)
        if not success:
            self.epc.add_rels_for_object(
                uri,
                relationships=[
                    create_h5_external_relationship(
                        h5_path=re.sub(
                            pattern=r"\.epc$",
                            repl=".h5",
                            string=str(self.epc.epc_file_path),
                            flags=re.IGNORECASE,
                        )
                    )
                ],
            )
            success = self.epc.write_array(uri, path_in_resource, array)
        return success

    def list_objects(self, dataspace: Optional[str] = None) -> List[str]:
        """
        List all object identifiers in the EPC file.

        Note: The dataspace parameter is ignored for EPC storage.

        Args:
            dataspace: Ignored for EPC storage

        Returns:
            List of object identifiers
        """

        return [str(get_obj_uri(obj)) for obj in self.epc.energyml_objects]

    def close(self):
        """
        Close the EPC storage.

        Note: EPC files don't require explicit closing, but this method is provided
        for interface consistency.
        """
        pass

    def save(self, file_path: str):
        """
        Save the EPC to a file.

        Args:
            file_path: The path where the EPC file should be saved
        """
        self.epc.export_file(file_path)

    def start_transaction(self):
        """EPC storage does not support transactions."""
        pass

    def commit_transaction(self) -> Tuple[bool, Optional[str]]:
        """EPC storage does not support transactions."""
        try:
            self.save(self.epc.epc_file_path)
            return True, None
        except Exception as e:
            return False, str(e)

    def rollback_transaction(self):
        """EPC storage does not support transactions."""
        pass


class EPCStreamStorage(EnergymlWorkspace):
    """
    Memory-efficient EPC stream-based storage implementation.

    This implementation uses EpcStreamReader for lazy loading and caching,
    making it ideal for handling very large EPC files with thousands of objects.

    Features:
    - Lazy loading: Objects loaded only when accessed
    - Smart caching: LRU cache with configurable size
    - Memory monitoring: Track memory usage and cache efficiency
    - Same interface as EPCStorage for seamless switching

    Args:
        stream_reader: An EpcStreamReader instance
    """

    def __init__(self, stream_reader: EpcStreamReader):  # noqa: F821
        """
        Initialize stream-based storage.

        Args:
            stream_reader: An EpcStreamReader instance
        """
        self.stream_reader: EpcStreamReader = stream_reader

    def get_object(self, uri: Union[str, ETPUri]) -> Optional[Any]:
        """
        Retrieve an object from the EPC stream.

        Args:
            uri: The URI or identifier of the object to retrieve

        Returns:
            The deserialized energyml object, or None if not found
        """
        # Determine if input is a URI or identifier
        return self.stream_reader.get_object_by_identifier(uri)

    def put_object(self, obj: Any, dataspace: Optional[str] = None) -> Optional[str]:
        """
        Add an object to the EPC stream.

        Note: The dataspace parameter is ignored for EPC storage.

        Args:
            obj: The energyml object to add
            dataspace: Ignored for EPC storage

        Returns:
            The URI of the added object if successful, None otherwise
        """
        try:
            if self.stream_reader.add_object(obj) is not None:
                uri = get_obj_uri(obj)
                return str(uri) if uri else None
        except Exception:
            return None

    def delete_object(self, uri: Union[str, ETPUri]) -> bool:
        """
        Delete an object from the EPC stream.

        Args:
            uri: The URI or identifier of the object to delete

        Returns:
            True if the object was found and deleted, False otherwise
        """
        return self.stream_reader.remove_object(str(uri))

    def get_array(self, uri: Union[str, ETPUri], path_in_resource: str) -> Optional[np.ndarray]:
        """
        Get array from HDF5 external file associated with this EPC stream.

        Args:
            uri: The URI of the object containing the array reference
            path_in_resource: The path within the HDF5 file

        Returns:
            The data array as a numpy array, or None if not found
        """
        return self.stream_reader.read_array(uri, path_in_resource)

    def put_array(
        self,
        uri: Union[str, ETPUri],
        path_in_resource: str,
        array: np.ndarray,
    ) -> bool:
        """
        Put array to HDF5 external file associated with this EPC stream.

        Note: This functionality requires additional HDF5 writing implementation.

        Args:
            uri: The URI of the object that will reference the array
            path_in_resource: The path within the HDF5 file
            array: The numpy array to store

        Returns:
            True if successful

        Raises:
            NotImplementedError: Array writing to EPC/HDF5 is not yet fully implemented
        """
        success = False
        try:
            success = self.stream_reader.write_array(uri, path_in_resource, array)
        except ValueError:
            pass
        if not success:
            self.stream_reader.add_rels_for_object(
                uri,
                relationships=[
                    create_h5_external_relationship(
                        h5_path=re.sub(
                            pattern=r"\.epc$",
                            repl=".h5",
                            string=str(self.stream_reader.epc_file_path),
                            flags=re.IGNORECASE,
                        )
                    )
                ],
            )
            success = self.stream_reader.write_array(uri, path_in_resource, array)
        return success

    def list_objects(self, dataspace: Optional[str] = None) -> List[str]:
        """
        List all object URIs in the EPC stream.

        Note: The dataspace parameter is ignored for EPC storage.
        This method is memory-efficient as it uses cached metadata.

        Args:
            dataspace: Ignored for EPC storage

        Returns:
            List of object URIs
        """
        # Get metadata without loading full objects
        return [
            f"eml:///{content_type_to_qualified_type(m.content_type)}({m.uuid})"
            for m in self.stream_reader.list_object_metadata()
        ]

    def close(self):
        """
        Close the EPC stream and release resources.

        This clears the cache and closes the underlying file handle.
        """
        self.stream_reader.clear_cache()

    def save(self, file_path: str):
        """
        Save the EPC stream to a file.

        Note: This converts the stream to a full Epc instance before saving,
        which loads all objects into memory.

        Args:
            file_path: The path where the EPC file should be saved
        """
        # copy the epc file to the new location
        if file_path is not None:
            shutil.copy(self.stream_reader.epc_file_path, file_path)

    def get_statistics(self):
        """
        Get streaming statistics for monitoring performance.

        Returns:
            EpcStreamingStats object with cache hits, misses, and memory usage
        """
        return self.stream_reader.get_statistics()

    def start_transaction(self):
        """EPC storage does not support transactions."""
        pass

    def commit_transaction(self) -> Tuple[bool, Optional[str]]:
        """EPC storage does not support transactions."""
        try:
            self.save(self.stream_reader.epc_file_path)
            return True, None
        except Exception as e:
            return False, str(e)

    def rollback_transaction(self):
        """EPC storage does not support transactions."""
        pass


def create_storage(source: Union[str, ETPClient, Epc, EpcStreamReader]) -> EnergymlWorkspace:
    """
    Factory function to create an appropriate storage interface from various sources.

    This convenience function automatically determines the correct storage implementation
    based on the type of source provided.

    Args:
        source: Can be:
            - ETPClient instance: Creates ETPStorage
            - Epc instance: Creates EPCStorage
            - EpcStreamReader instance: Creates EPCStreamStorage
            - str (file path): Loads EPC file and creates EPCStorage

    Returns:
        An EnergymlStorage implementation (ETPStorage, EPCStorage, or EPCStreamStorage)

    Raises:
        ValueError: If the source type is not supported

    Example:
        ```python
        # From ETP client
        storage = create_storage(etp_client)

        # From EPC instance
        storage = create_storage(epc_instance)

        # From EPC stream reader
        from energyml.utils.epc_stream import EpcStreamReader
        stream_reader = EpcStreamReader("large_file.epc", cache_size=50)
        storage = create_storage(stream_reader)

        # From file path
        storage = create_storage("path/to/file.epc")
        ```
    """
    # Import here to avoid circular dependency
    from py_etp_client.etpclient import ETPClient

    if isinstance(source, ETPClient):
        return ETPStorage(source)
    elif isinstance(source, Epc):
        return EPCStorage(source)
    elif isinstance(source, EpcStreamReader):
        return EPCStreamStorage(source)
    elif isinstance(source, str):
        epc = Epc.read_file(source)
        if epc is None:
            raise ValueError(f"Failed to read EPC file: {source}")
        return EPCStorage(epc)
    else:
        supported_types = "ETPClient, Epc, EpcStreamReader, or str (file path)"
        raise ValueError(f"Unsupported source type: {type(source)}. Expected {supported_types}.")
