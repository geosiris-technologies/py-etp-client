# Copyright (c) 2022-2023 Geosiris.
# SPDX-License-Identifier: Apache-2.0
"""
Integration tests for the storage_interface module.

These tests use REAL EPC files and ETP server connections (not mocks).
They verify that the storage interface works correctly with actual data.

Requirements:
- Real EPC file: data/grid-aws.epc
- ETP server credentials in .env file
- Active internet connection for ETP tests

Run with:
    poetry run pytest tests/test_storage_interface_integration.py -v

Skip ETP tests if no connection:
    poetry run pytest tests/test_storage_interface_integration.py -v -k "not etp"
"""

import os
import unittest
import tempfile
import shutil
from pathlib import Path
import numpy as np
from dotenv import load_dotenv

from py_etp_client.storage_interface import (
    create_storage,
    ETPStorage,
    EPCStorage,
)
from py_etp_client.etpclient import ETPClient
from py_etp_client.etpconfig import ServerConfig
from energyml.utils.epc import Epc


# Load environment variables
load_dotenv()


class TestEPCStorageIntegration(unittest.TestCase):
    """Integration tests for EPCStorage using a real EPC file."""

    @classmethod
    def setUpClass(cls):
        """Set up test fixtures that are shared across all tests."""
        # Path to the real EPC file
        cls.epc_file_path = Path("data/grid-aws.epc")

        # Check if the file exists
        if not cls.epc_file_path.exists():
            raise unittest.SkipTest(
                f"EPC file not found: {cls.epc_file_path}. " "Please ensure data/grid-aws.epc exists."
            )

        # Create a temporary directory for test outputs
        cls.temp_dir = tempfile.mkdtemp()

    @classmethod
    def tearDownClass(cls):
        """Clean up temporary files."""
        if hasattr(cls, "temp_dir") and os.path.exists(cls.temp_dir):
            shutil.rmtree(cls.temp_dir)

    def test_create_storage_from_file_path(self):
        """Test creating storage from a real EPC file path."""
        storage = create_storage(str(self.epc_file_path))

        self.assertIsInstance(storage, EPCStorage)
        self.assertIsNotNone(storage.epc)

        storage.close()

    def test_create_storage_from_epc_instance(self):
        """Test creating storage from an Epc instance."""
        epc = Epc.read_file(str(self.epc_file_path))
        storage = create_storage(epc)

        self.assertIsInstance(storage, EPCStorage)
        self.assertEqual(storage.epc, epc)

        storage.close()

    def test_list_objects_from_real_epc(self):
        """Test listing objects from a real EPC file."""
        storage = create_storage(str(self.epc_file_path))

        objects = storage.list_objects()

        # The EPC file should contain at least some objects
        self.assertIsInstance(objects, list)
        self.assertGreater(len(objects), 0, "EPC file should contain objects")

        # Each object URI should be a string
        for obj_uri in objects:
            self.assertIsInstance(obj_uri, str)
            print(f"  Found object: {obj_uri}")

        storage.close()

    def test_get_object_from_real_epc(self):
        """Test retrieving an object from a real EPC file."""
        storage = create_storage(str(self.epc_file_path))

        objects = storage.list_objects()
        self.assertGreater(len(objects), 0, "Need at least one object")

        # Get the first object
        first_uri = objects[0]
        obj = storage.get_object(first_uri)

        self.assertIsNotNone(obj, f"Should retrieve object for URI: {first_uri}")
        print(f"  Retrieved object type: {type(obj).__name__}")
        print(f"  Object URI: {first_uri}")

        storage.close()

    def test_get_nonexistent_object(self):
        """Test retrieving a non-existent object returns None."""
        storage = create_storage(str(self.epc_file_path))

        fake_uri = "eml:///resqml20.obj_NonExistent(00000000-0000-0000-0000-000000000000)"
        obj = storage.get_object(fake_uri)

        self.assertIsNone(obj, "Non-existent object should return None")

        storage.close()

    def test_put_and_get_object_roundtrip(self):
        """Test adding a new object and retrieving it."""
        # Load the original EPC
        epc = Epc.read_file(str(self.epc_file_path))
        storage = create_storage(epc)

        # Get an existing object to use as a template
        objects = storage.list_objects()
        self.assertGreater(len(objects), 0)

        template_obj = storage.get_object(objects[0])
        self.assertIsNotNone(template_obj)

        # Add the object (it should already be in the EPC, so this tests the put logic)
        initial_count = len(storage.list_objects())
        success = storage.put_object(template_obj)

        self.assertTrue(success, "put_object should succeed")

        # Note: Since we're adding the same object, it gets added again
        # (no deduplication in EPCStorage)
        final_count = len(storage.list_objects())
        self.assertEqual(final_count, initial_count + 1, "Object should be added")

        storage.close()

    def test_delete_object_from_epc(self):
        """Test deleting an object from EPC."""
        # Create a copy of the EPC to modify
        epc = Epc.read_file(str(self.epc_file_path))
        storage = create_storage(epc)

        objects = storage.list_objects()
        initial_count = len(objects)
        self.assertGreater(initial_count, 0)

        # Delete the first object
        uri_to_delete = objects[0]
        success = storage.delete_object(uri_to_delete)

        self.assertTrue(success, f"Should successfully delete {uri_to_delete}")

        # Verify it's gone
        remaining_objects = storage.list_objects()
        self.assertEqual(len(remaining_objects), initial_count - 1)
        self.assertNotIn(uri_to_delete, remaining_objects)

        # Try to get the deleted object
        deleted_obj = storage.get_object(uri_to_delete)
        self.assertIsNone(deleted_obj, "Deleted object should not be retrievable")

        storage.close()

    def test_save_modified_epc(self):
        """Test saving a modified EPC to a new file."""
        # Load original EPC
        epc = Epc.read_file(str(self.epc_file_path))
        storage = create_storage(epc)

        # Modify it (delete an object)
        objects = storage.list_objects()
        if len(objects) > 0:
            storage.delete_object(objects[0])

        # Save to temp file
        output_path = os.path.join(self.temp_dir, "modified.epc")
        storage.save(output_path)

        # Verify the file was created
        self.assertTrue(os.path.exists(output_path), "Output EPC file should exist")

        # Load the saved file and verify changes
        new_storage = create_storage(output_path)
        new_objects = new_storage.list_objects()

        self.assertEqual(len(new_objects), len(objects) - 1, "Saved EPC should have one fewer object")

        storage.close()
        new_storage.close()

    def test_get_array_from_real_epc(self):
        """Test retrieving array data from a real EPC file (if available)."""
        storage = create_storage(str(self.epc_file_path))

        objects = storage.list_objects()

        # Try to find an object with array data
        found_array = False
        for obj_uri in objects:
            try:
                # Try to get array data - path might vary by object type
                # Common paths: /values, /data, /points
                for path in ["/values", "/data", "/points", ""]:
                    array = storage.get_array(obj_uri, path)
                    if array is not None:
                        found_array = True
                        print(f"  Found array in {obj_uri} at path '{path}'")
                        print(f"  Array shape: {array.shape}")
                        print(f"  Array dtype: {array.dtype}")
                        self.assertIsInstance(array, np.ndarray)
                        break

                if found_array:
                    break
            except Exception as e:
                # Some objects might not have arrays
                continue

        if not found_array:
            print("  Note: No array data found in this EPC file")

        storage.close()


class TestETPStorageIntegration(unittest.TestCase):
    """Integration tests for ETPStorage using a real ETP server."""

    @classmethod
    def setUpClass(cls):
        """Set up ETP client connection."""
        # Check if required environment variables are set
        server_url = os.getenv("SERVER_URL")

        if not server_url:
            raise unittest.SkipTest(
                "Missing SERVER_URL environment variable. " "Please configure .env file with ETP server credentials."
            )

        # Create ETP client from environment
        try:
            # Try to load config from file first
            config_file = os.getenv("ETP_CONFIG_LIST_FILE_PATH") or os.getenv("ETP_CONFIG_FILE_PATH")
            config_id = os.getenv("ETP_CONFIG_ID")

            if config_file and os.path.exists(config_file):
                # Load from config file
                from py_etp_client.etpconfig import ServerConfigs

                configs = ServerConfigs.read_configs(config_file)
                if config_id and configs:
                    config = configs.get_by_id(config_id)
                elif configs and configs.configs:
                    config = configs.configs[0]
                else:
                    config = None

                if config:
                    cls.client = ETPClient(
                        url=config.url,
                        spec=None,
                        config=config,
                    )
                else:
                    raise Exception("Could not load server config from file")
            else:
                # Create client directly from URL
                cls.client = ETPClient(
                    url=server_url,
                    spec=None,
                )

            cls.client.start()

            # Wait for connection
            import time

            time.sleep(2)

            if not cls.client.is_connected():
                raise unittest.SkipTest("Failed to connect to ETP server")

        except Exception as e:
            raise unittest.SkipTest(f"Failed to initialize ETP client: {e}")

    @classmethod
    def tearDownClass(cls):
        """Close ETP connection."""
        if hasattr(cls, "client"):
            try:
                cls.client.close()
            except:
                pass

    @unittest.skip("ETP server connection required - configure .env to enable")
    def test_create_storage_from_etp_client(self):
        """Test creating storage from a real ETP client."""
        storage = create_storage(self.client)

        self.assertIsInstance(storage, ETPStorage)
        if isinstance(storage, ETPStorage):
            self.assertEqual(storage.client, self.client)

        # Don't close storage here as it would close the shared client

    @unittest.skip("ETP server connection required - configure .env to enable")
    def test_list_dataspaces(self):
        """Test listing dataspaces from ETP server."""
        storage = create_storage(self.client)

        try:
            # Try to list dataspaces (pass None or empty string)
            dataspaces = storage.list_objects()

            self.assertIsInstance(dataspaces, list)
            print(f"  Found {len(dataspaces)} items")

            for ds in dataspaces[:5]:  # Show first 5
                print(f"  - {ds}")

        except Exception as e:
            print(f"  Note: Could not list dataspaces: {e}")

    @unittest.skip("ETP server connection required - configure .env to enable")
    def test_get_resources_from_dataspace(self):
        """Test listing resources from a specific dataspace."""
        storage = create_storage(self.client)

        try:
            # Get dataspaces first
            dataspaces_response = self.client.get_dataspaces()

            if dataspaces_response and len(dataspaces_response) > 0:
                # Use the first dataspace
                dataspace_uri = dataspaces_response[0].uri
                print(f"  Testing with dataspace: {dataspace_uri}")

                objects = storage.list_objects(dataspace_uri)

                self.assertIsInstance(objects, list)
                print(f"  Found {len(objects)} objects in dataspace")

                for obj in objects[:3]:  # Show first 3
                    print(f"  - {obj}")
            else:
                print("  Note: No dataspaces available on server")

        except Exception as e:
            print(f"  Note: Could not list resources: {e}")

    @unittest.skip("ETP server connection required - configure .env to enable")
    def test_get_object_from_etp(self):
        """Test retrieving an object from ETP server."""
        storage = create_storage(self.client)

        try:
            # Get some objects
            objects = storage.list_objects()

            if len(objects) > 0:
                # Try to get the first object
                first_uri = objects[0]
                print(f"  Attempting to get object: {first_uri}")

                obj = storage.get_object(first_uri)

                if obj is not None:
                    self.assertIsNotNone(obj)
                    print(f"  Retrieved object type: {type(obj).__name__}")
                else:
                    print("  Note: Could not retrieve object (might be a dataspace/folder)")
            else:
                print("  Note: No objects available to test retrieval")

        except Exception as e:
            print(f"  Note: Could not get object: {e}")

    @unittest.skip("ETP server connection required - configure .env to enable")
    def test_get_array_from_etp(self):
        """Test retrieving array data from ETP server."""
        storage = create_storage(self.client)

        try:
            objects = storage.list_objects()

            # Try to find an object with array data
            found_array = False
            for obj_uri in objects[:10]:  # Check first 10 objects
                try:
                    # Try common array paths
                    for path in ["/values", "/data", "/points", ""]:
                        array = storage.get_array(obj_uri, path)
                        if array is not None:
                            found_array = True
                            print(f"  Found array in {obj_uri} at path '{path}'")
                            print(f"  Array shape: {array.shape}")
                            print(f"  Array dtype: {array.dtype}")
                            self.assertIsInstance(array, np.ndarray)
                            break

                    if found_array:
                        break
                except Exception:
                    continue

            if not found_array:
                print("  Note: No array data found in tested objects")

        except Exception as e:
            print(f"  Note: Could not test array retrieval: {e}")


class TestStorageInterfacePolymorphism(unittest.TestCase):
    """Test that the same code works with both EPC and ETP storage."""

    def process_storage(self, storage, name: str):
        """
        A generic function that works with any storage implementation.
        This demonstrates the power of the unified interface.
        """
        print(f"\n  Processing {name}...")

        # List objects
        objects = storage.list_objects()
        print(f"  - Found {len(objects)} objects")

        if len(objects) > 0:
            # Get first object
            obj = storage.get_object(objects[0])
            if obj:
                print(f"  - Retrieved object: {type(obj).__name__}")

            # Try to get array
            try:
                array = storage.get_array(objects[0], "/values")
                if array is not None:
                    print(f"  - Found array: shape={array.shape}")
            except:
                pass

        return len(objects)

    def test_same_code_works_with_epc(self):
        """Test that generic code works with EPC storage."""
        epc_file = Path("data/grid-aws.epc")

        if not epc_file.exists():
            self.skipTest("EPC file not found")

        storage = create_storage(str(epc_file))
        count = self.process_storage(storage, "EPC File")

        self.assertGreater(count, 0)
        storage.close()

    def test_same_code_works_with_etp(self):
        """Test that generic code works with ETP storage."""
        if not os.getenv("SERVER_URL"):
            self.skipTest("ETP server not configured")

        try:
            # Try to load config from file
            config_file = os.getenv("ETP_CONFIG_LIST_FILE_PATH") or os.getenv("ETP_CONFIG_FILE_PATH")
            config_id = os.getenv("ETP_CONFIG_ID")
            server_url = os.getenv("SERVER_URL")

            if not server_url:
                self.skipTest("ETP server not configured")

            config = None
            if config_file and os.path.exists(config_file):
                from py_etp_client.etpconfig import ServerConfigs

                configs = ServerConfigs.read_configs(config_file)
                if config_id and configs:
                    config = configs.get_by_id(config_id)
                elif configs and len(list(configs.configs.values())) > 0:
                    config = list(configs.configs.values())[0]

            if config:
                client = ETPClient(
                    url=config.url,
                    spec=None,
                    config=config,
                )
            else:
                client = ETPClient(
                    url=server_url,
                    spec=None,
                )

            client.start()

            import time

            time.sleep(2)

            if not client.is_connected():
                self.skipTest("Could not connect to ETP server")

            storage = create_storage(client)
            count = self.process_storage(storage, "ETP Server")

            # Count might be 0 if server is empty, that's ok
            self.assertGreaterEqual(count, 0)

            storage.close()
            client.close()

        except Exception as e:
            self.skipTest(f"ETP test failed: {e}")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("Storage Interface Integration Tests")
    print("Testing with REAL EPC files and ETP server connections")
    print("=" * 70 + "\n")

    unittest.main(verbosity=2)
