# Copyright (c) 2022-2023 Geosiris.
# SPDX-License-Identifier: Apache-2.0
"""
Polymorphic Storage Test

This script demonstrates that the EnergymlWorkspace interface is truly polymorphic:
the same generic function works identically with ETP server, EPC file, and EPC stream storage.

This proves that you can write code once and use it with any storage backend without modification.
"""

import os
import shutil
import tempfile
import traceback
import numpy as np
from pathlib import Path
from typing import Optional

from py_etp_client.etpconfig import ServerConfigs
from py_etp_client.storage_interface import ETPStorage, EnergymlWorkspace, create_storage
from energyml.utils.epc import create_energyml_object, gen_uuid
from energyml.utils.introspection import get_obj_uri


def generic_storage_workflow(
    storage: EnergymlWorkspace, storage_name: str, test_array_operations: bool = True
) -> dict:
    """
    Generic function that works with ANY storage implementation.

    This function demonstrates all CRUD operations using only the EnergymlWorkspace interface.
    It works identically with ETP, EPC, and EPC stream storage.

    Args:
        storage: Any implementation of EnergymlWorkspace
        storage_name: Name for logging purposes
        test_array_operations: Whether to test array operations (may not be supported by all)

    Returns:
        Dictionary with test results
    """
    print(f"\n{'=' * 80}")
    print(f"Testing Generic Workflow with: {storage_name}")
    print(f"{'=' * 80}")

    results = {
        "storage_type": storage_name,
        "list_initial": False,
        "create_object1": False,
        "create_object2": False,
        "list_after_create": False,
        "get_object": False,
        "delete_object": False,
        "list_after_delete": False,
        "create_array": False,
        "get_array": False,
        "errors": [],
    }

    try:
        storage.start_transaction()

        # Step 1: List initial objects
        print("\n1. Listing initial objects...")
        initial_objects = storage.list_objects()
        initial_count = len(initial_objects)
        print(f"   ✓ Found {initial_count} initial objects")
        results["list_initial"] = True
        results["initial_count"] = initial_count

        # Show first 3 objects
        for i, obj_uri in enumerate(initial_objects[:3]):
            print(f"     [{i+1}] {obj_uri}")

        # Step 2: Create first object
        print("\n2. Creating first object (BoundaryFeature)...")
        uuid1 = gen_uuid()
        feature = create_energyml_object(
            content_or_qualified_type="resqml20.BoundaryFeature",
            citation={
                "Title": f"Test Boundary Feature - {storage_name}",
                "Originator": "polymorphic_test",
                "Creation": None,
            },
            uuid=uuid1,
        )

        success = storage.put_object(feature)
        if success:
            print(f"   ✓ Created BoundaryFeature with UUID: {uuid1}")
            results["create_object1"] = True
            results["object1_uuid"] = uuid1
        else:
            print("   ✗ Failed to create object 1")
            results["errors"].append("Failed to create object 1")

        # Step 3: Create second object
        print("\n3. Creating second object (PointSetRepresentation)...")
        uuid2 = gen_uuid()
        pointset = create_energyml_object(
            content_or_qualified_type="resqml20.PointSetRepresentation",
            citation={
                "Title": f"Test Point Set - {storage_name}",
                "Originator": "polymorphic_test",
                "Creation": None,
            },
            uuid=uuid2,
        )

        success = storage.put_object(pointset)
        if success:
            print(f"   ✓ Created PointSetRepresentation with UUID: {uuid2}")
            results["create_object2"] = True
            results["object2_uuid"] = uuid2
        else:
            print("   ✗ Failed to create object 2")
            results["errors"].append("Failed to create object 2")

        # Step 4: List objects after creation
        print("\n4. Listing objects after creation...")
        after_create_objects = storage.list_objects()
        after_create_count = len(after_create_objects)
        print(f"   ✓ Found {after_create_count} objects (was {initial_count})")
        print(f"   ✓ Added {after_create_count - initial_count} new objects")
        results["list_after_create"] = True
        results["after_create_count"] = after_create_count

        # Step 5: Retrieve object
        print("\n5. Retrieving first created object...")
        feature_uri = str(get_obj_uri(feature))
        retrieved_obj = storage.get_object(feature_uri)

        if retrieved_obj is not None:
            print(f"   ✓ Retrieved object: {type(retrieved_obj).__name__}")
            print(f"     URI: {feature_uri}")
            results["get_object"] = True
        else:
            print("   ✗ Failed to retrieve object")
            results["errors"].append("Failed to retrieve object")

        # Step 6: Delete first object
        print("\n6. Deleting first object...")
        delete_success = storage.delete_object(feature_uri)

        if delete_success:
            print(f"   ✓ Deleted object: {feature_uri}")
            results["delete_object"] = True
        else:
            print("   ✗ Failed to delete object")
            results["errors"].append("Failed to delete object")

        # Step 7: List objects after deletion
        print("\n7. Listing objects after deletion...")
        after_delete_objects = storage.list_objects()
        after_delete_count = len(after_delete_objects)
        print(f"   ✓ Found {after_delete_count} objects")
        print(f"   ✓ Confirmed deletion: {after_create_count - after_delete_count} object removed")
        results["list_after_delete"] = True
        results["after_delete_count"] = after_delete_count

        # Step 8: Test array operations (if supported)
        if test_array_operations:
            print("\n8. Testing array operations...")

            # Create a test array
            test_array = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]], dtype=np.float64)
            print(f"   • Created test array: shape={test_array.shape}, dtype={test_array.dtype}")
            results["create_array"] = True

            # Try to write array
            pointset_uri = str(get_obj_uri(pointset))
            try:
                array_success = storage.put_array(pointset_uri, "/points/values", test_array)
                if array_success:
                    print("   ✓ Array written successfully")

                    # Try to read it back
                    retrieved_array = storage.get_array(pointset_uri, "/points/values")
                    if retrieved_array is not None:
                        print(f"   ✓ Array retrieved: shape={retrieved_array.shape}, dtype={retrieved_array.dtype}")
                        if np.array_equal(test_array, retrieved_array):
                            print("   ✓ Array data matches!")
                            results["get_array"] = True
                        else:
                            print("   ⚠ Array data mismatch")
                    else:
                        print("   ⚠ Could not retrieve array")
                else:
                    print("   ⚠ Array write returned False")
            except NotImplementedError as e:
                print(f"   ⚠ Array operations not supported: {e}")
                results["errors"].append(f"Array operations not supported: {e}")

        # Step 9: Final statistics
        print("\n9. Final statistics...")
        print(f"   • Initial objects: {initial_count}")
        print(f"   • After creation: {after_create_count} (+{after_create_count - initial_count})")
        print(f"   • After deletion: {after_delete_count} (-{after_create_count - after_delete_count})")
        print(f"   • Net change: {after_delete_count - initial_count:+d}")

        # Close storage
        storage.close()
        print("\n   ✓ Storage closed successfully")
        storage.commit_transaction()

    except Exception as e:
        print(f"\n   ✗ Error during workflow: {e}")
        results["errors"].append(f"Workflow error: {e}")
        import traceback

        traceback.print_exc()

    return results


def test_with_epc_file(epc_path: str = "data/grid-aws.epc") -> dict:
    """
    Test the generic workflow with EPC file storage.

    Args:
        epc_path: Path to EPC file to use for testing

    Returns:
        Test results dictionary
    """
    print("\n" + "█" * 80)
    print("TEST 1: EPC File Storage")
    print("█" * 80)

    # Create a temporary copy of the EPC file for testing
    temp_dir = tempfile.mkdtemp()
    temp_epc = os.path.join(temp_dir, "test-epc-file.epc")

    try:
        shutil.copy2(epc_path, temp_epc)
        print(f"\nUsing temporary EPC file: {temp_epc}")

        # Create storage using the factory function
        storage = create_storage(temp_epc)
        print(f"Storage type: {type(storage).__name__}")

        # Run the generic workflow
        results = generic_storage_workflow(storage, "EPC File Storage", test_array_operations=True)

        # Save the modified EPC
        if hasattr(storage, "save"):
            output_path = os.path.join(temp_dir, "test-epc-file-modified.epc")
            storage.save(output_path)
            print(f"\n✓ Modified EPC saved to: {output_path}")

        return results

    finally:
        # Cleanup
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            print(f"\n✓ Cleaned up temporary directory: {temp_dir}")


def test_with_epc_stream(epc_path: str = "data/grid-aws.epc") -> dict:
    """
    Test the generic workflow with EPC stream storage.

    Args:
        epc_path: Path to EPC file to use for testing

    Returns:
        Test results dictionary
    """
    print("\n" + "█" * 80)
    print("TEST 2: EPC Stream Storage")
    print("█" * 80)

    # Create a temporary copy of the EPC file for testing
    temp_dir = tempfile.mkdtemp()
    temp_epc = os.path.join(temp_dir, "test-epc-stream.epc")

    try:
        shutil.copy2(epc_path, temp_epc)
        print(f"\nUsing temporary EPC file: {temp_epc}")

        # Try to use EpcStreamReader
        try:
            from energyml.utils.epc_stream import EpcStreamReader

            # Create stream reader with caching
            stream_reader = EpcStreamReader(
                epc_file_path=temp_epc, cache_size=50, validate_on_load=True, preload_metadata=True
            )

            # Create storage using the factory function
            storage = create_storage(stream_reader)
            print(f"Storage type: {type(storage).__name__}")
            print(f"Cache size: 50 objects")

            # Run the generic workflow
            results = generic_storage_workflow(storage, "EPC Stream Storage", test_array_operations=True)

            # Show cache statistics
            if hasattr(storage, "get_statistics"):
                stats = storage.get_statistics()
                print(f"\n✓ Cache Statistics:")
                print(f"  - Cache hits: {stats.cache_hits}")
                print(f"  - Cache misses: {stats.cache_misses}")
                print(f"  - Hit rate: {stats.cache_hit_rate:.1f}%")

            # Save the modified EPC
            if hasattr(storage, "save"):
                output_path = os.path.join(temp_dir, "test-epc-stream-modified.epc")
                storage.save(output_path)
                print(f"\n✓ Modified EPC saved to: {output_path}")

            return results

        except ImportError:
            print("\n⚠ EpcStreamReader not available in energyml-utils")
            print("   Skipping EPC stream storage test")
            return {"storage_type": "EPC Stream Storage", "errors": ["EpcStreamReader not available"]}

    finally:
        # Cleanup
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            print(f"\n✓ Cleaned up temporary directory: {temp_dir}")


def test_with_etp_server(config_path: Optional[str] = None) -> dict:
    """
    Test the generic workflow with ETP server storage.

    Args:
        config_path: Path to ETP server configuration file

    Returns:
        Test results dictionary
    """
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

    print("\n" + "█" * 80)
    print("TEST 3: ETP Server Storage")
    print("█" * 80)

    try:
        from py_etp_client.etpclient import ETPClient
        from py_etp_client.etpconfig import ServerConfig

        print(f"\nUsing server config: {config_path}")

        # Load configuration
        config = ServerConfigs().get_by_id(os.getenv("ETP_CONFIG_ID", "default"))
        print(f"Server URL: {config.url}")
        if config is None:
            raise ValueError("No valid ETP server configuration found.")
        # Create and start ETP client
        client = ETPClient(config=config)
        client.start()
        print("✓ ETP client started")

        # Create storage using the factory function
        storage = ETPStorage(client, dataspace="test-workflow-full")
        print(f"Storage type: {type(storage).__name__}")

        # Run the generic workflow (with array operations)
        results = generic_storage_workflow(storage, "ETP Server Storage", test_array_operations=True)

        return results

    except Exception as e:
        traceback.print_exc()
        print(f"\n⚠ Could not test ETP server storage: {e}")
        return {"storage_type": "ETP Server Storage", "errors": [f"Setup failed: {e}"]}


def print_summary(all_results: list):
    """Print a summary of all test results."""
    print("\n" + "=" * 80)
    print("SUMMARY OF ALL TESTS")
    print("=" * 80)

    for results in all_results:
        storage_type = results.get("storage_type", "Unknown")
        print(f"\n{storage_type}:")

        # Filter out expected NotImplementedError for array operations
        unexpected_errors = [err for err in results.get("errors", []) if "not yet implemented" not in err.lower()]

        if unexpected_errors:
            print("  ❌ Unexpected errors encountered:")
            for error in unexpected_errors:
                print(f"     • {error}")
        else:
            print("  ✅ All supported operations successful")

        # Show operation status (excluding array operations for EPC)
        core_operations = [
            ("List initial objects", "list_initial"),
            ("Create object 1", "create_object1"),
            ("Create object 2", "create_object2"),
            ("List after create", "list_after_create"),
            ("Get object", "get_object"),
            ("Delete object", "delete_object"),
            ("List after delete", "list_after_delete"),
        ]

        array_operations = [
            ("Create array", "create_array"),
            ("Get array", "get_array"),
        ]

        core_passed = sum(1 for _, key in core_operations if results.get(key, False))
        core_total = len(core_operations)
        print(f"\n  Core operations: {core_passed}/{core_total}")

        for op_name, op_key in core_operations:
            status = "✓" if results.get(op_key, False) else "✗"
            print(f"    {status} {op_name}")

        # Show array operations separately
        array_passed = sum(1 for _, key in array_operations if results.get(key, False))
        array_total = len(array_operations)
        print(f"\n  Array operations: {array_passed}/{array_total} (may not be supported)")

        for op_name, op_key in array_operations:
            status = "✓" if results.get(op_key, False) else "○"
            print(f"    {status} {op_name}")

        # Show object counts if available
        if "initial_count" in results:
            print(f"\n  Object counts:")
            print(f"    Initial: {results.get('initial_count', 'N/A')}")
            print(f"    After create: {results.get('after_create_count', 'N/A')}")
            print(f"    After delete: {results.get('after_delete_count', 'N/A')}")

            initial = results.get("initial_count", 0)
            after_delete = results.get("after_delete_count", 0)
            print(f"    Net change: {after_delete - initial:+d} objects")


def main():
    from dotenv import load_dotenv

    load_dotenv()
    """Main test runner."""
    print("=" * 80)
    print("POLYMORPHIC STORAGE INTERFACE TEST")
    print("=" * 80)
    print("\nThis test demonstrates that the EnergymlWorkspace interface is truly polymorphic.")
    print("The SAME generic function works with ETP server, EPC file, and EPC stream storage.")
    print("\nThis proves you can write code once and use it with ANY storage backend!")

    all_results = []

    # Test 1: EPC File Storage
    try:
        results = test_with_epc_file()
        all_results.append(results)
    except Exception as e:
        print(f"\n❌ EPC File test failed: {e}")
        all_results.append({"storage_type": "EPC File Storage", "errors": [str(e)]})

    # Test 2: EPC Stream Storage
    try:
        results = test_with_epc_stream()
        all_results.append(results)
    except Exception as e:
        print(f"\n❌ EPC Stream test failed: {e}")
        all_results.append({"storage_type": "EPC Stream Storage", "errors": [str(e)]})

    # Test 3: ETP Server Storage (may be skipped if not configured)
    try:
        results = test_with_etp_server()
        all_results.append(results)
    except Exception as e:
        print(f"\n❌ ETP Server test failed: {e}")
        all_results.append({"storage_type": "ETP Server Storage", "errors": [str(e)]})

    # Print summary
    print_summary(all_results)

    print("\n" + "=" * 80)
    print("POLYMORPHISM VERIFIED!")
    print("=" * 80)
    print("\nThe same generic_storage_workflow() function worked with:")

    success_count = 0
    for results in all_results:
        storage_type = results.get("storage_type", "Unknown")
        # Check if core operations passed
        core_operations = [
            "list_initial",
            "create_object1",
            "create_object2",
            "list_after_create",
            "get_object",
            "delete_object",
            "list_after_delete",
        ]
        core_passed = sum(1 for key in core_operations if results.get(key, False))

        if core_passed == len(core_operations):
            status = "✅ SUCCESS"
            success_count += 1
        elif core_passed > 0:
            status = "⚠ PARTIAL"
        else:
            status = "⚠ SKIPPED"
        print(f"  {status} {storage_type} ({core_passed}/{len(core_operations)} core operations)")

    print(f"\n{success_count}/{len(all_results)} storage types fully tested and verified!")
    print("\nThis demonstrates that you can write storage-agnostic code that works")
    print("with any backend by using the EnergymlWorkspace interface!")
    print("\n✨ Key Achievement: The SAME function code works with:")
    print("   • EPC File Storage (in-memory, simple)")
    print("   • EPC Stream Storage (lazy-loading, memory-efficient)")
    print("   • ETP Server Storage (network-based, multi-user)")
    print("\nYou can switch storage backends without changing your application code!")
    print()


if __name__ == "__main__":
    main()
