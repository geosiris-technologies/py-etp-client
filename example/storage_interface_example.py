# Copyright (c) 2022-2023 Geosiris.
# SPDX-License-Identifier: Apache-2.0
"""
Example demonstrating the unified storage interface for ETP and EPC.

This example shows how to use the same API for working with energyml data
whether it's stored on an ETP server or in a local EPC file.
"""

import numpy as np
from py_etp_client.storage_interface import create_storage, EnergymlWorkspace
from py_etp_client.etpclient import ETPClient
from energyml.utils.epc import Epc


def demo_with_etp_server():
    """Example using ETP server storage."""
    print("=" * 60)
    print("Example 1: Using ETP Server Storage")
    print("=" * 60)

    # Create and start ETP client
    client = ETPClient(url="wss://your-etp-server.com", spec=None)
    client.start()

    # Create storage interface from ETP client
    storage = create_storage(client)

    # Now use the unified interface
    print("\n1. Listing dataspaces and objects:")
    objects = storage.list_objects("my-dataspace")
    for obj_uri in objects[:5]:  # Show first 5
        print(f"  - {obj_uri}")

    print("\n2. Getting an object:")
    if objects:
        obj = storage.get_object(objects[0])
        if obj:
            print(f"  Retrieved object: {type(obj).__name__}")

    print("\n3. Getting a data array:")
    if objects:
        array = storage.get_array(objects[0], "/values")
        if array is not None:
            print(f"  Array shape: {array.shape}, dtype: {array.dtype}")

    print("\n4. Putting a new object:")
    # new_obj = create_your_energyml_object()
    # success = storage.put_object(new_obj, "my-dataspace")
    # print(f"  Put object: {'Success' if success else 'Failed'}")

    # Clean up
    storage.close()
    print("\nETP storage closed.")


def demo_with_epc_file():
    """Example using local EPC file storage."""
    print("\n" + "=" * 60)
    print("Example 2: Using Local EPC File Storage")
    print("=" * 60)

    # Option A: Create storage from file path
    storage = create_storage("path/to/your/file.epc")

    # Option B: Create storage from existing Epc instance
    # epc = Epc.read_file("path/to/your/file.epc")
    # storage = create_storage(epc)

    # Use the same unified interface!
    print("\n1. Listing objects in EPC:")
    objects = storage.list_objects()
    for obj_uri in objects[:5]:  # Show first 5
        print(f"  - {obj_uri}")

    print("\n2. Getting an object from EPC:")
    if objects:
        obj = storage.get_object(objects[0])
        if obj:
            print(f"  Retrieved object: {type(obj).__name__}")

    print("\n3. Reading array from HDF5:")
    if objects:
        array = storage.get_array(objects[0], "/values")
        if array is not None:
            print(f"  Array shape: {array.shape}, dtype: {array.dtype}")

    print("\n4. Adding a new object to EPC:")
    # new_obj = create_your_energyml_object()
    # success = storage.put_object(new_obj)
    # print(f"  Added object: {'Success' if success else 'Failed'}")

    # Save changes back to file (EPC-specific method)
    from py_etp_client.storage_interface import EPCStorage

    if isinstance(storage, EPCStorage):
        # storage.save("path/to/output.epc")
        print("\nEPC saved (uncomment to actually save).")

    storage.close()
    print("EPC storage closed.")


def demo_polymorphic_function():
    """Example of a function that works with any storage type."""
    print("\n" + "=" * 60)
    print("Example 3: Polymorphic Function (Works with Both!)")
    print("=" * 60)

    def process_energyml_data(storage: EnergymlWorkspace, dataspace: str = None):
        """
        This function works with ANY storage implementation!

        Args:
            storage: Can be ETPStorage or EPCStorage
            dataspace: Optional dataspace filter
        """
        print(f"\nProcessing data from {type(storage).__name__}...")

        # List all objects
        objects = storage.list_objects(dataspace)
        print(f"Found {len(objects)} objects")

        # Process each object
        for uri in objects[:3]:  # Process first 3
            obj = storage.get_object(uri)
            if obj:
                print(f"  Processing: {uri}")

                # Try to get associated array data
                array = storage.get_array(uri, "/values")
                if array is not None:
                    print(f"    Array data: shape={array.shape}, dtype={array.dtype}")
                    print(f"    Stats: min={array.min()}, max={array.max()}, mean={array.mean()}")

    # This function works with BOTH ETP and EPC storage!
    print("\nUsing with ETP:")
    # etp_client = ETPClient(url="wss://server.com", spec=None)
    # etp_client.start()
    # etp_storage = create_storage(etp_client)
    # process_energyml_data(etp_storage, "my-dataspace")
    # etp_storage.close()
    print("  (Commented out - requires actual ETP server)")

    print("\nUsing with EPC:")
    # epc_storage = create_storage("path/to/file.epc")
    # process_energyml_data(epc_storage)
    # epc_storage.close()
    print("  (Commented out - requires actual EPC file)")


def demo_data_migration():
    """Example: Copy data from ETP server to local EPC file."""
    print("\n" + "=" * 60)
    print("Example 4: Data Migration (ETP → EPC)")
    print("=" * 60)

    def migrate_data(source: EnergymlWorkspace, target: EnergymlWorkspace, dataspace: str = None):
        """
        Copy all objects and arrays from source to target storage.

        Args:
            source: Source storage (e.g., ETP)
            target: Target storage (e.g., EPC)
            dataspace: Optional dataspace to migrate
        """
        print(f"Migrating from {type(source).__name__} to {type(target).__name__}...")

        # Get all objects from source
        objects = source.list_objects(dataspace)
        print(f"Found {len(objects)} objects to migrate")

        migrated = 0
        for uri in objects:
            # Get object from source
            obj = source.get_object(uri)
            if obj:
                # Put object to target
                if target.put_object(obj):
                    migrated += 1
                    print(f"  ✓ Migrated: {uri}")

                # Note: Array data is typically embedded in the object
                # or referenced via HDF5 external files
                # You may need custom logic for array migration

        print(f"\nMigration complete: {migrated}/{len(objects)} objects")

    # Example usage (commented out)
    # etp_storage = create_storage(ETPClient(url="wss://server.com", spec=None))
    # epc_storage = create_storage(Epc())  # New empty EPC
    # migrate_data(etp_storage, epc_storage, "my-dataspace")
    # epc_storage.save("migrated_data.epc")
    # etp_storage.close()
    # epc_storage.close()

    print("  (Commented out - requires actual ETP server and file path)")


if __name__ == "__main__":
    print("\n")
    print("╔════════════════════════════════════════════════════════════╗")
    print("║     Unified Storage Interface Examples                     ║")
    print("║     Works with both ETP Server and EPC Files!              ║")
    print("╚════════════════════════════════════════════════════════════╝")

    # Uncomment the examples you want to run:

    # demo_with_etp_server()  # Requires ETP server connection
    # demo_with_epc_file()    # Requires EPC file path
    demo_polymorphic_function()
    demo_data_migration()

    print("\n" + "=" * 60)
    print("Examples completed!")
    print("=" * 60)
    print("\nNote: Most examples are commented out because they require:")
    print("  - An actual ETP server connection")
    print("  - An actual EPC file path")
    print("\nUncomment and modify the paths/URLs to run with real data.")
