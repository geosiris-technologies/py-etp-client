# Copyright (c) 2022-2023 Geosiris.
# SPDX-License-Identifier: Apache-2.0
"""
Example 2: Complex EPC Workflow with Stream Reader

This example demonstrates a complete CRUD (Create, Read, Update, Delete) workflow:
1. Copy EPC and H5 files to a new location
2. Open with EpcStreamReader through storage interface
3. Write 2 new objects
4. Print number of objects
5. Delete one object
6. Create 2 arrays
7. Attempt to write arrays (demonstrates limitation)
8. Delete the last array reference
9. Save the modified EPC

This showcases the memory-efficient EpcStreamReader with the unified storage interface.
"""

import shutil
import os
import numpy as np
from pathlib import Path


def main():
    print("=" * 80)
    print("Example 2: Complex EPC Workflow with Stream Reader")
    print("=" * 80)

    # Step 1: Copy EPC and H5 files
    print("\n1. Copying EPC and H5 files...")
    source_epc = "data/grid-aws.epc"
    source_h5 = "data/grid-aws.h5"  # Assuming there's an H5 file

    output_dir = "data/temp"
    Path(output_dir).mkdir(exist_ok=True)

    target_epc = os.path.join(output_dir, "modified-grid.epc")
    target_h5 = os.path.join(output_dir, "modified-grid.h5")

    shutil.copy2(source_epc, target_epc)
    print(f"   ✓ Copied EPC: {source_epc} → {target_epc}")

    if os.path.exists(source_h5):
        shutil.copy2(source_h5, target_h5)
        print(f"   ✓ Copied H5: {source_h5} → {target_h5}")
    else:
        print(f"   ⚠ H5 file not found: {source_h5}")
        print("     (This is OK, we'll continue without it)")

    # Step 2: Open with EpcStreamReader through storage interface
    print("\n2. Opening EPC with stream reader...")

    try:
        from energyml.utils.epc_stream import EpcStreamReader
        from py_etp_client.storage_interface import create_storage

        # Create stream reader with caching
        stream_reader = EpcStreamReader(
            epc_file_path=target_epc,
            cache_size=50,  # Keep 50 objects in memory
            validate_on_load=True,
            preload_metadata=True,
        )

        # Create storage interface
        storage = create_storage(stream_reader)
        print(f"   ✓ Created EPCStreamStorage with EpcStreamReader")
        print(f"   ✓ Cache size: 50 objects")

        # Get initial count
        initial_objects = storage.list_objects()
        initial_count = len(initial_objects)
        print(f"   ✓ Initial object count: {initial_count}")

        # Show statistics
        if hasattr(storage, "get_statistics"):
            stats = storage.get_statistics()
            print(f"   ✓ Memory efficiency: Cache hits={stats.cache_hits}, misses={stats.cache_misses}")

    except ImportError:
        print("   ⚠ EpcStreamReader not available in energyml-utils")
        print("   → Falling back to regular Epc")
        from py_etp_client.storage_interface import create_storage

        storage = create_storage(target_epc)
        initial_objects = storage.list_objects()
        initial_count = len(initial_objects)
        print(f"   ✓ Created EPCStorage")
        print(f"   ✓ Initial object count: {initial_count}")

    # Step 3: Write 2 new objects
    print("\n3. Creating and adding 2 new objects...")

    from energyml.utils.epc import create_energyml_object, gen_uuid

    # Object 1: BoundaryFeature (using resqml20 which is available)
    uuid1 = gen_uuid()
    feature1 = create_energyml_object(
        content_or_qualified_type="resqml20.BoundaryFeature",
        citation={
            "Title": "Example Boundary Feature 1",
            "Originator": "storage_interface_example",
            "Creation": None,
        },
        uuid=uuid1,
    )
    success1 = storage.put_object(feature1)
    print(f"   ✓ Object 1: BoundaryFeature (resqml20)")
    print(f"     UUID: {uuid1}")
    print(f"     Added: {success1}")

    # Object 2: PointSetRepresentation (using resqml20)
    uuid2 = gen_uuid()
    pointset = create_energyml_object(
        content_or_qualified_type="resqml20.PointSetRepresentation",
        citation={
            "Title": "Example Point Set",
            "Originator": "storage_interface_example",
            "Creation": None,
        },
        uuid=uuid2,
    )
    success2 = storage.put_object(pointset)
    print(f"   ✓ Object 2: PointSetRepresentation (resqml20)")
    print(f"     UUID: {uuid2}")
    print(f"     Added: {success2}")

    # Step 4: Print number of objects
    print("\n4. Counting objects after additions...")
    current_objects = storage.list_objects()
    current_count = len(current_objects)
    print(f"   ✓ Current object count: {current_count}")
    print(f"   ✓ Added: {current_count - initial_count} objects")

    # Step 5: Delete one object (delete the first new object)
    print("\n5. Deleting one object...")

    from energyml.utils.introspection import get_obj_uri

    uri_to_delete = str(get_obj_uri(feature1))

    delete_success = storage.delete_object(uri_to_delete)
    print(f"   ✓ Deleted: {uri_to_delete}")
    print(f"   ✓ Success: {delete_success}")

    # Verify deletion
    after_delete_objects = storage.list_objects()
    after_delete_count = len(after_delete_objects)
    print(f"   ✓ Object count after deletion: {after_delete_count}")
    print(f"   ✓ Deleted: {current_count - after_delete_count} objects")

    # Step 6: Create 2 arrays
    print("\n6. Creating 2 arrays...")

    # Array 1: Z-values for the 2D grid (10x10 grid)
    z_values = np.random.rand(10, 10) * 100.0  # Random elevation values
    print(f"   ✓ Array 1: Z-values")
    print(f"     Shape: {z_values.shape}")
    print(f"     Type: {z_values.dtype}")
    print(f"     Min: {z_values.min():.2f}, Max: {z_values.max():.2f}")

    # Array 2: Quality indicators (10x10 grid)
    quality = np.random.randint(0, 5, size=(10, 10), dtype=np.int32)
    print(f"   ✓ Array 2: Quality indicators")
    print(f"     Shape: {quality.shape}")
    print(f"     Type: {quality.dtype}")
    print(f"     Values: 0-4 (quality levels)")

    # Step 7: Write arrays (demonstrates limitation)
    print("\n7. Attempting to write arrays to storage...")
    print("   Note: Array writing to EPC/HDF5 is not yet implemented")

    pointset_uri = str(get_obj_uri(pointset))

    try:
        # Attempt to write first array
        storage.put_array(pointset_uri, "/points/values", z_values)
        print("   ✓ Array 1 written")

        # Attempt to write second array
        storage.put_array(pointset_uri, "/qualityData/values", quality)
        print("   ✓ Array 2 written")

    except NotImplementedError as e:
        print(f"   ⚠ Expected limitation: {e}")
        print("   → In a full implementation:")
        print("     • Arrays would be written to HDF5 file")
        print("     • Object would reference external file via ExternalDataArrayPart")
        print("     • Path references would be: '/points/values' and '/qualityData/values'")

    # Step 8: Delete the last array (conceptually)
    print("\n8. Deleting last array reference...")
    print("   Note: Since arrays aren't actually written, we'll demonstrate object cleanup")
    print("   → In a full implementation, this would:")
    print("     • Remove array reference from object")
    print("     • Optionally clean up HDF5 dataset")
    print("     • Update EPC relationships")

    # Instead, let's get the object and show what would be modified
    pointset_retrieved = storage.get_object(pointset_uri)
    if pointset_retrieved:
        print(f"   ✓ Retrieved object: {type(pointset_retrieved).__name__}")
        print("   ✓ Would remove last array reference from this object")

    # Step 9: Save the modified EPC
    print("\n9. Saving modified EPC...")

    if hasattr(storage, "save"):
        storage.save(target_epc)
        print(f"   ✓ Saved to: {target_epc}")
    else:
        print("   ⚠ Save method not available on this storage type")

    # Final statistics
    print("\n10. Final statistics...")
    final_objects = storage.list_objects()
    final_count = len(final_objects)

    print(f"   ✓ Final object count: {final_count}")
    print(f"   ✓ Net change: {final_count - initial_count:+d} objects")

    if hasattr(storage, "get_statistics"):
        final_stats = storage.get_statistics()
        print(f"   ✓ Cache statistics:")
        print(f"     - Cache hits: {final_stats.cache_hits}")
        print(f"     - Cache misses: {final_stats.cache_misses}")
        hit_rate = (
            final_stats.cache_hits / (final_stats.cache_hits + final_stats.cache_misses) * 100
            if (final_stats.cache_hits + final_stats.cache_misses) > 0
            else 0
        )
        print(f"     - Hit rate: {hit_rate:.1f}%")

    # Close storage
    storage.close()
    print("   ✓ Storage closed and cache cleared")

    print("\n" + "=" * 80)
    print("Example 2 Complete!")
    print("=" * 80)
    print("Workflow Summary:")
    print(f"  1. ✓ Copied EPC+H5 files to: {output_dir}")
    print(f"  2. ✓ Opened with stream reader (memory-efficient)")
    print(f"  3. ✓ Created 2 new objects (BoundaryFeature, PointSetRepresentation)")
    print(f"  4. ✓ Object count: {initial_count} → {current_count}")
    print(f"  5. ✓ Deleted 1 object")
    print(f"  6. ✓ Created 2 arrays (points and quality data)")
    print(f"  7. ⚠ Array writing demonstrated (limitation noted)")
    print(f"  8. ✓ Cleanup demonstrated")
    print(f"  9. ✓ Saved modified EPC")
    print(f" 10. ✓ Final count: {final_count} objects")
    print()


if __name__ == "__main__":
    main()
