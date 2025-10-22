# Copyright (c) 2022-2023 Geosiris.
# SPDX-License-Identifier: Apache-2.0
"""
Example 1: Create TriangulatedSetRepresentation with Array Data

This example demonstrates:
1. Loading an existing EPC file through the storage interface
2. Creating a new resqml22.TriangulatedSetRepresentation object using energyml.utils.epc.create_energyml_object
3. Adding the object to the storage
4. Creating a new array (simulating triangle vertex data)
5. Attempting to write the array (demonstrates current limitation)
6. Saving the modified EPC

Note: Array writing to EPC/HDF5 is not yet implemented in EPCStorage,
      but this example shows the intended workflow.
"""

import numpy as np
from py_etp_client.storage_interface import create_storage
from energyml.utils.epc import create_energyml_object, gen_uuid


def main():
    print("=" * 80)
    print("Example 1: Create TriangulatedSetRepresentation")
    print("=" * 80)

    # Step 1: Load existing EPC through storage interface
    print("\n1. Loading EPC file through storage interface...")
    epc_path = "data/grid-aws.epc"
    storage = create_storage(epc_path)
    print(f"   ✓ Storage created from: {epc_path}")

    # List existing objects
    objects = storage.list_objects()
    print(f"   ✓ Found {len(objects)} existing objects")
    for obj_uri in objects[:3]:  # Show first 3
        print(f"     - {obj_uri}")

    # Step 2: Create a new TriangulatedSetRepresentation
    print("\n2. Creating new TriangulatedSetRepresentation object...")

    # Generate a UUID for the new object
    new_uuid = gen_uuid()

    # Create citation metadata
    citation = {
        "Title": "Example Triangulated Surface",
        "Originator": "storage_interface_example",
        "Creation": None,  # Will be set automatically
    }

    # Create the object using the energyml utility function
    triangulated_set = create_energyml_object(
        content_or_qualified_type="resqml22.TriangulatedSetRepresentation", citation=citation, uuid=new_uuid
    )

    print(f"   ✓ Created TriangulatedSetRepresentation")
    print(f"     UUID: {new_uuid}")
    print(f"     Type: {type(triangulated_set).__name__}")
    print(f"     Citation: {citation['Title']}")

    # Set some basic properties
    # Note: In a real scenario, you would set up the complete structure
    # including the InterpretedFeature reference, LocalDepth3dCrs, etc.

    # Step 3: Add the object to storage
    print("\n3. Adding object to storage...")
    success = storage.put_object(triangulated_set)
    if success:
        print("   ✓ Object successfully added to storage")
    else:
        print("   ✗ Failed to add object to storage")
        return

    # Verify it was added
    objects_after = storage.list_objects()
    print(f"   ✓ Storage now contains {len(objects_after)} objects (was {len(objects)})")

    # Step 4: Create array data for the triangulation
    print("\n4. Creating triangle vertex data...")

    # Example: Create a simple triangulated surface (a pyramid with 4 triangles)
    # Vertices: 5 points (4 base corners + 1 apex)
    vertices = np.array(
        [
            [0.0, 0.0, 0.0],  # Base corner 1
            [100.0, 0.0, 0.0],  # Base corner 2
            [100.0, 100.0, 0.0],  # Base corner 3
            [0.0, 100.0, 0.0],  # Base corner 4
            [50.0, 50.0, 50.0],  # Apex
        ],
        dtype=np.float64,
    )

    # Triangle connectivity: 4 triangles
    # Each row is [vertex1_index, vertex2_index, vertex3_index]
    triangles = np.array(
        [
            [0, 1, 4],  # Triangle 1: base corners 1, 2, and apex
            [1, 2, 4],  # Triangle 2: base corners 2, 3, and apex
            [2, 3, 4],  # Triangle 3: base corners 3, 4, and apex
            [3, 0, 4],  # Triangle 4: base corners 4, 1, and apex
        ],
        dtype=np.int32,
    )

    print(f"   ✓ Created vertex array: shape={vertices.shape}, dtype={vertices.dtype}")
    print(f"     Vertices (first 3):")
    for i, vertex in enumerate(vertices[:3]):
        print(f"       Vertex {i}: ({vertex[0]:.1f}, {vertex[1]:.1f}, {vertex[2]:.1f})")

    print(f"   ✓ Created triangle array: shape={triangles.shape}, dtype={triangles.dtype}")
    print(f"     Triangles (first 2):")
    for i, tri in enumerate(triangles[:2]):
        print(f"       Triangle {i}: vertices [{tri[0]}, {tri[1]}, {tri[2]}]")

    # Step 5: Attempt to write array (demonstrates current limitation)
    print("\n5. Attempting to write array data...")
    print("   Note: Array writing to EPC/HDF5 is not yet implemented in EPCStorage")

    from energyml.utils.introspection import get_obj_uri

    obj_uri = str(get_obj_uri(triangulated_set))

    try:
        # This will raise NotImplementedError
        storage.put_array(obj_uri, "/points/values", vertices)
        print("   ✓ Array successfully written")
    except NotImplementedError as e:
        print(f"   ⚠ Expected limitation: {e}")
        print("   → In a full implementation, arrays would be written to HDF5")
        print("   → The object would reference the external HDF5 file")

    # Step 6: Save the modified EPC
    print("\n6. Saving modified EPC...")
    output_path = "data/output_with_triangulated_set.epc"

    # Access the underlying EPC to save (EPCStorage has a save method)
    if hasattr(storage, "save"):
        storage.save(output_path)
        print(f"   ✓ Saved to: {output_path}")
    else:
        print("   ⚠ Save method not available on this storage type")

    # Step 7: Verify the saved file
    print("\n7. Verifying saved file...")
    verify_storage = create_storage(output_path)
    final_objects = verify_storage.list_objects()
    print(f"   ✓ Saved file contains {len(final_objects)} objects")

    # Find our new object
    our_object_found = False
    for obj_uri in final_objects:
        if new_uuid in obj_uri:
            our_object_found = True
            print(f"   ✓ Found our new object: {obj_uri}")
            break

    if not our_object_found:
        print(f"   ⚠ Could not find object with UUID: {new_uuid}")

    verify_storage.close()
    storage.close()

    print("\n" + "=" * 80)
    print("Example 1 Complete!")
    print("=" * 80)
    print("\nSummary:")
    print(f"  • Loaded EPC with {len(objects)} objects")
    print(f"  • Created resqml22.TriangulatedSetRepresentation")
    print(f"  • Added object to storage (new count: {len(objects_after)})")
    print(f"  • Created vertex and triangle arrays")
    print(f"  • Demonstrated array writing limitation")
    print(f"  • Saved modified EPC to: {output_path}")
    print(f"  • Verified saved file contains {len(final_objects)} objects")
    print()


if __name__ == "__main__":
    main()
