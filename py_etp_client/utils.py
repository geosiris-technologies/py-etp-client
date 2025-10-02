# Copyright (c) 2022-2023 Geosiris.
# SPDX-License-Identifier: Apache-2.0

__H5PY_MODULE_EXISTS__ = False
from typing import Dict, List, Optional, Union

try:
    from typing import TypeAlias  # Python 3.10+
except ImportError:
    try:
        from typing_extensions import TypeAlias  # For older Python versions
    except ImportError:
        # Fallback for environments without typing_extensions
        # This is just for type checkers, runtime behavior is unchanged
        TypeAlias = type(None)  # type: ignore

from energyml.utils.uri import Uri as ETPUri
from py_etp_client import ProtocolException

try:
    import h5py

    __H5PY_MODULE_EXISTS__ = True

    def h5_list_datasets(h5_file_path) -> List[str]:  # type: ignore
        """
        List all datasets in an HDF5 file.
        :param h5_file_path: Path to the HDF5 file
        :return: List of dataset names in the HDF5 file
        """
        res = []
        with h5py.File(h5_file_path, "r") as f:  # type: ignore
            # Function to print the names of all datasets
            def list_datasets(name, obj):
                if isinstance(obj, h5py.Dataset):  # type: ignore # Check if the object is a dataset
                    res.append(name)

            # Visit all items in the HDF5 file and apply the list function
            f.visititems(list_datasets)
        return res

except Exception:
    h5py = None
    __H5PY_MODULE_EXISTS__ = False

    def h5_list_datasets(h5_file_path) -> List[str]:  # type: ignore
        raise ImportError("h5py module is not available.")


# # test if python >= 3.12
# if __import__("sys").version_info >= (3, 12):
#     type T_UriSingleOrGrouped = Union[str, ETPUri, List[str], List[ETPUri], Dict[str, str], Dict[str, ETPUri]]
# else:
# Type alias for URI inputs that can be single values or grouped collections
T_UriSingleOrGrouped: TypeAlias = Union[str, ETPUri, List[str], List[ETPUri], Dict[str, str], Dict[str, ETPUri]]


def get_valid_uri_str(uri: Optional[Union[str, ETPUri]]) -> str:
    """
    Get a valid URI string from a string or ETPUri object.
    :param uri: str or ETPUri
    :return: str
    """
    if uri is not None:
        if isinstance(uri, str):
            uri = uri.strip()
            if not uri.startswith("eml:///"):
                return f"eml:///dataspace('{uri}')"
            return uri
        elif isinstance(uri, ETPUri):
            return str(uri)
        else:
            raise ValueError("Input must be a string or ETPUri object.")
    return "eml:///"


def reshape_uris_as_str_list(
    uris: T_UriSingleOrGrouped,
) -> List[str]:
    """
    Reshape uris to a list of strings.
    :param uris: str, ETPUri, List[str] or List[ETPUri]
    :return: List of strings
    """
    if isinstance(uris, str):
        return [get_valid_uri_str(uris)]
    elif isinstance(uris, ETPUri):
        return [str(uris)]
    elif isinstance(uris, list):
        res = []
        for uri in uris:
            res.append(get_valid_uri_str(uri))
        return res
    elif isinstance(uris, dict):
        res = []
        for key, uri in uris.items():
            res.append(get_valid_uri_str(uri))
        return res
    else:
        raise ValueError("Input must be a string, ETPUri, list of strings or list of ETPUri objects.")


def reshape_uris_as_str_dict(
    uris: T_UriSingleOrGrouped,
) -> Dict[str, str]:
    """
    Reshape uris to a dict of strings.
    :param uris: str, ETPUri, List[str] or List[ETPUri]
    :return: Dict of strings
    """
    if isinstance(uris, str):
        return {"0": uris}
    elif isinstance(uris, ETPUri):
        return {"0": str(uris)}
    elif isinstance(uris, list):
        res = {}
        for i, uri in enumerate(uris):
            res[str(i)] = get_valid_uri_str(uri)
        return res
    elif isinstance(uris, dict):
        res = {}
        for key, uri in uris.items():
            res[key] = get_valid_uri_str(uri)
        return res
    else:
        raise ValueError("Input must be a string, ETPUri, list of strings or list of ETPUri objects.")


def pe_as_str(err: ProtocolException) -> str:
    """
    Get a string representation of a ProtocolException.
    :param err: ProtocolException
    :return: str
    """
    if err.error:
        return f"Error: {err.error.code} : {err.error.message}"
    elif err.errors:
        return f"Errors: {err.errors}"
    else:
        return "Unknown ProtocolException error."
