# Unified Storage Interface

A unified interface for working with energyml data regardless of whether it comes from an ETP server or a local EPC file.

## Overview

The storage interface provides a common API for:
- **ETPStorage**: Working with data on an ETP server
- **EPCStorage**: Working with data in local EPC files

This allows you to write functions that work with energyml data without knowing the underlying storage mechanism.

## Installation

The storage interface is included in the `py-etp-client` package. No additional installation is required.

## Quick Start

### Using with ETP Server

```python
from py_etp_client.storage_interface import create_storage
from py_etp_client.etpclient import ETPClient

# Create and start ETP client
client = ETPClient(url="wss://your-server.com", spec=None)
client.start()

# Create storage interface
storage = create_storage(client)

# Use the unified API
objects = storage.list_objects("my-dataspace")
obj = storage.get_object(objects[0])
array = storage.get_array(objects[0], "/values")

storage.close()
```

### Using with EPC File

```python
from py_etp_client.storage_interface import create_storage

# Create storage from file path
storage = create_storage("path/to/file.epc")

# Use the same API!
objects = storage.list_objects()
obj = storage.get_object(objects[0])
array = storage.get_array(objects[0], "/values")

storage.close()
```

## API Reference

### Common Interface Methods

All storage implementations provide these methods:

#### `get_object(uri: str) -> Optional[Any]`
Retrieve a deserialized energyml object by URI.

```python
obj = storage.get_object("eml:///dataspace('ds')/resqml20.obj(uuid)")
```

#### `put_object(obj: Any, dataspace: Optional[str] = None) -> bool`
Store an energyml object.

```python
success = storage.put_object(my_obj, dataspace="my-dataspace")
```

#### `delete_object(uri: str) -> bool`
Delete an energyml object by URI.

```python
success = storage.delete_object(uri)
```

#### `get_array(uri: str, path_in_resource: str) -> Optional[np.ndarray]`
Get a data array from storage.

```python
array = storage.get_array(uri, "/values")
```

#### `put_array(uri: str, path_in_resource: str, array: np.ndarray) -> bool`
Put a data array to storage.

```python
import numpy as np
array = np.array([1, 2, 3, 4, 5])
success = storage.put_array(uri, "/values", array)
```

**Note**: `put_array` for EPCStorage is not yet implemented as it requires HDF5 writing functionality.

#### `list_objects(dataspace: Optional[str] = None) -> List[str]`
List available object URIs.

```python
# ETP: list objects in a dataspace
objects = storage.list_objects("my-dataspace")

# EPC: list all objects
objects = storage.list_objects()
```

#### `close()`
Close the storage connection and release resources.

```python
storage.close()
```

### EPC-Specific Methods

EPCStorage provides an additional method:

#### `save(file_path: str)`
Save the EPC to a file.

```python
from py_etp_client.storage_interface import EPCStorage

if isinstance(storage, EPCStorage):
    storage.save("output.epc")
```

## Factory Function

### `create_storage(source) -> EnergymlStorage`

Automatically creates the appropriate storage implementation based on the source type.

**Parameters:**
- `source`: Can be:
  - `ETPClient` instance → creates `ETPStorage`
  - `Epc` instance → creates `EPCStorage`
  - `str` (file path) → loads EPC file and creates `EPCStorage`

**Returns:** An `EnergymlStorage` implementation

**Examples:**

```python
# From ETP client
storage = create_storage(etp_client)

# From EPC instance
storage = create_storage(epc_instance)

# From file path
storage = create_storage("data.epc")
```

## Advanced Usage

### Writing Polymorphic Functions

Write functions that work with any storage type:

```python
from py_etp_client.storage_interface import EnergymlStorage

def analyze_data(storage: EnergymlStorage, dataspace: str = None):
    """Works with both ETP and EPC storage!"""
    objects = storage.list_objects(dataspace)
    
    for uri in objects:
        obj = storage.get_object(uri)
        array = storage.get_array(uri, "/values")
        
        if array is not None:
            print(f"Processing {uri}")
            print(f"  Shape: {array.shape}")
            print(f"  Mean: {array.mean()}")

# Use with ETP
etp_storage = create_storage(etp_client)
analyze_data(etp_storage, "dataspace1")

# Use with EPC
epc_storage = create_storage("file.epc")
analyze_data(epc_storage)
```

### Data Migration

Copy data between storage types:

```python
def migrate_data(source: EnergymlStorage, target: EnergymlStorage):
    """Copy all objects from source to target."""
    objects = source.list_objects()
    
    for uri in objects:
        obj = source.get_object(uri)
        if obj:
            target.put_object(obj)
            print(f"Migrated: {uri}")

# Migrate from ETP to EPC
etp_storage = create_storage(etp_client)
epc_storage = create_storage(Epc())  # Empty EPC

migrate_data(etp_storage, epc_storage)
epc_storage.save("migrated.epc")
```

## Implementation Details

### ETPStorage

- Uses `ETPClient` methods internally
- Supports dataspaces for organizing objects
- Arrays are read/written through ETP data array protocols
- Requires an active ETP connection

### EPCStorage

- Uses `Epc` object internally
- All objects stored in a single collection
- Arrays are read from HDF5 external files
- Array writing is not yet implemented (requires HDF5 write support)
- Dataspace parameter is ignored (EPC files don't have dataspaces)

## Testing

Run the unit tests:

```bash
poetry run pytest tests/test_storage_interface.py -v
```

All 46 tests should pass, covering:
- Abstract interface validation
- ETPStorage operations
- EPCStorage operations
- Factory function
- Interface compatibility

## Examples

See `example/storage_interface_example.py` for complete examples including:
1. Using ETP server storage
2. Using local EPC file storage
3. Writing polymorphic functions
4. Data migration between storage types

## Limitations

### Current Limitations

1. **Array Writing to EPC**: `put_array()` for EPCStorage is not yet implemented. This requires additional HDF5 writing logic.

2. **Dataspace Support in EPC**: EPC files don't have native dataspace support. The `dataspace` parameter is ignored for EPCStorage.

3. **Transaction Support**: The current interface doesn't expose ETP transaction support (StartTransaction, CommitTransaction, etc.).

### Future Enhancements

Potential improvements:
- Implement HDF5 array writing for EPCStorage
- Add transaction support to the interface
- Add batch operations for efficiency
- Add metadata query methods
- Add support for partial array reads/writes

## Contributing

Contributions are welcome! When contributing:
1. Maintain interface compatibility between implementations
2. Add tests for new functionality
3. Update this documentation
4. Follow the existing code style

## License

Copyright (c) 2022-2023 Geosiris.
SPDX-License-Identifier: Apache-2.0
