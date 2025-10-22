# Copyright (c) 2022-2023 Geosiris.
# SPDX-License-Identifier: Apache-2.0
"""
Unit tests for the storage_interface module.

Tests both ETPStorage and EPCStorage implementations of the EnergymlStorage interface.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch, PropertyMock
import numpy as np
from typing import List

from py_etp_client.storage_interface import (
    EnergymlWorkspace,
    ETPStorage,
    EPCStorage,
    create_storage,
)


class TestEnergymlStorageInterface(unittest.TestCase):
    """Test that the abstract interface defines the expected methods."""

    def test_interface_has_required_methods(self):
        """Verify the abstract interface defines all required methods."""
        required_methods = [
            "get_object",
            "put_object",
            "delete_object",
            "get_array",
            "put_array",
            "list_objects",
            "close",
        ]
        for method in required_methods:
            self.assertTrue(
                hasattr(EnergymlWorkspace, method),
                f"EnergymlStorage missing required method: {method}",
            )

    def test_cannot_instantiate_abstract_class(self):
        """Verify that the abstract base class cannot be instantiated directly."""
        with self.assertRaises(TypeError):
            EnergymlWorkspace()


class TestETPStorage(unittest.TestCase):
    """Test suite for ETPStorage implementation."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_client = Mock()
        self.storage = ETPStorage(self.mock_client)
        self.test_uri = "eml:///dataspace('test-ds')/resqml20.obj_TestObject(12345)"

    def test_init(self):
        """Test ETPStorage initialization."""
        self.assertEqual(self.storage.client, self.mock_client)

    def test_get_object_success(self):
        """Test successful object retrieval."""
        mock_obj = Mock()
        self.mock_client.get_data_object_as_obj.return_value = mock_obj

        result = self.storage.get_object(self.test_uri)

        self.assertEqual(result, mock_obj)
        self.mock_client.get_data_object_as_obj.assert_called_once_with(self.test_uri, format_="xml")

    def test_get_object_returns_exception(self):
        """Test object retrieval when server returns an exception."""
        self.mock_client.get_data_object_as_obj.return_value = Exception("Not found")

        result = self.storage.get_object(self.test_uri)

        self.assertIsNone(result)

    def test_get_object_not_found(self):
        """Test object retrieval when object doesn't exist."""
        self.mock_client.get_data_object_as_obj.return_value = None

        result = self.storage.get_object(self.test_uri)

        self.assertIsNone(result)

    def test_put_object_success(self):
        """Test successful object storage."""
        mock_obj = Mock()
        self.mock_client.put_data_object_obj.return_value = ["success"]

        result = self.storage.put_object(mock_obj, "test-dataspace")

        self.assertTrue(result)
        self.mock_client.put_data_object_obj.assert_called_once_with(mock_obj, "test-dataspace")

    def test_put_object_with_no_dataspace(self):
        """Test object storage with no dataspace specified."""
        mock_obj = Mock()
        self.mock_client.put_data_object_obj.return_value = ["success"]

        result = self.storage.put_object(mock_obj)

        self.assertTrue(result)
        self.mock_client.put_data_object_obj.assert_called_once_with(mock_obj, "")

    def test_put_object_failure(self):
        """Test object storage failure."""
        mock_obj = Mock()
        self.mock_client.put_data_object_obj.return_value = []

        result = self.storage.put_object(mock_obj)

        self.assertFalse(result)

    def test_delete_object_success(self):
        """Test successful object deletion."""
        self.mock_client.delete_data_object.return_value = {self.test_uri: True}

        result = self.storage.delete_object(self.test_uri)

        self.assertTrue(result)
        self.mock_client.delete_data_object.assert_called_once_with(self.test_uri)

    def test_delete_object_failure(self):
        """Test object deletion failure."""
        self.mock_client.delete_data_object.return_value = {self.test_uri: False}

        result = self.storage.delete_object(self.test_uri)

        self.assertFalse(result)

    def test_delete_object_empty_response(self):
        """Test object deletion with empty response."""
        self.mock_client.delete_data_object.return_value = {}

        result = self.storage.delete_object(self.test_uri)

        self.assertFalse(result)

    def test_get_array_success(self):
        """Test successful array retrieval."""
        test_array = np.array([1, 2, 3, 4, 5])
        self.mock_client.get_data_array_safe.return_value = test_array

        result = self.storage.get_array(self.test_uri, "/values")

        self.assertIsNotNone(result)
        if result is not None:
            np.testing.assert_array_equal(result, test_array)
        self.mock_client.get_data_array_safe.assert_called_once_with(self.test_uri, "/values")

    def test_get_array_not_found(self):
        """Test array retrieval when array doesn't exist."""
        self.mock_client.get_data_array_safe.return_value = None

        result = self.storage.get_array(self.test_uri, "/values")

        self.assertIsNone(result)

    def test_put_array_success(self):
        """Test successful array storage."""
        test_array = np.array([1, 2, 3, 4, 5])
        self.mock_client.put_data_array_safe.return_value = ["success"]

        result = self.storage.put_array(self.test_uri, "/values", test_array)

        self.assertTrue(result)
        self.mock_client.put_data_array_safe.assert_called_once_with(self.test_uri, "/values", test_array)

    def test_put_array_failure(self):
        """Test array storage failure."""
        test_array = np.array([1, 2, 3, 4, 5])
        self.mock_client.put_data_array_safe.return_value = None

        result = self.storage.put_array(self.test_uri, "/values", test_array)

        self.assertFalse(result)

    def test_put_array_empty_response(self):
        """Test array storage with empty response."""
        test_array = np.array([1, 2, 3, 4, 5])
        self.mock_client.put_data_array_safe.return_value = []

        result = self.storage.put_array(self.test_uri, "/values", test_array)

        self.assertFalse(result)

    def test_list_objects_success(self):
        """Test successful object listing."""
        mock_resource1 = Mock()
        mock_resource1.uri = "eml:///dataspace('test')/resqml20.obj1(123)"
        mock_resource2 = Mock()
        mock_resource2.uri = "eml:///dataspace('test')/resqml20.obj2(456)"

        self.mock_client.get_resources.return_value = [
            mock_resource1,
            mock_resource2,
        ]

        result = self.storage.list_objects("test-dataspace")

        self.assertEqual(len(result), 2)
        self.assertIn(mock_resource1.uri, result)
        self.assertIn(mock_resource2.uri, result)
        self.mock_client.get_resources.assert_called_once_with(uri="test-dataspace", depth=1)

    def test_list_objects_no_dataspace(self):
        """Test object listing without dataspace filter."""
        self.mock_client.get_resources.return_value = []

        result = self.storage.list_objects()

        self.assertEqual(result, [])
        self.mock_client.get_resources.assert_called_once_with(uri=None, depth=1)

    def test_list_objects_filters_resources_without_uri(self):
        """Test that list_objects filters out resources without uri attribute."""
        mock_resource1 = Mock()
        mock_resource1.uri = "eml:///dataspace('test')/resqml20.obj1(123)"
        mock_resource2 = Mock(spec=[])  # No uri attribute

        self.mock_client.get_resources.return_value = [
            mock_resource1,
            mock_resource2,
        ]

        result = self.storage.list_objects()

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], mock_resource1.uri)

    def test_close(self):
        """Test storage close."""
        self.storage.close()

        self.mock_client.close.assert_called_once()


class TestEPCStorage(unittest.TestCase):
    """Test suite for EPCStorage implementation."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_epc = Mock()
        self.mock_epc.energyml_objects = []
        self.storage = EPCStorage(self.mock_epc)
        self.test_uri = "eml:///resqml20.obj_TestObject(12345-abcde)"

    def test_init(self):
        """Test EPCStorage initialization."""
        self.assertEqual(self.storage.epc, self.mock_epc)

    # @patch("energyml.utils.introspection.get_obj_identifier")
    # def test_get_object_success(self, mock_get_identifier):
    #     """Test successful object retrieval from EPC."""
    #     mock_obj1 = Mock()
    #     mock_obj2 = Mock()
    #     self.mock_epc.energyml_objects = [mock_obj1, mock_obj2]

    #     mock_get_identifier.side_effect = ["other-uri", self.test_uri]

    #     result = self.storage.get_object(self.test_uri)

    #     self.assertEqual(result, mock_obj2)

    @patch("energyml.utils.introspection.get_obj_identifier")
    def test_get_object_not_found(self, mock_get_identifier):
        """Test object retrieval when object doesn't exist in EPC."""
        mock_obj = Mock()
        self.mock_epc.energyml_objects = [mock_obj]

        mock_get_identifier.return_value = "different-uri"

        result = self.storage.get_object(self.test_uri)

        self.assertIsNone(result)

    def test_put_object_success(self):
        """Test successful object addition to EPC."""
        mock_obj = Mock()

        result = self.storage.put_object(mock_obj)

        self.assertTrue(result)
        self.assertIn(mock_obj, self.mock_epc.energyml_objects)

    def test_put_object_ignores_dataspace(self):
        """Test that put_object ignores dataspace parameter for EPC."""
        mock_obj = Mock()

        result = self.storage.put_object(mock_obj, dataspace="ignored")

        self.assertTrue(result)
        self.assertIn(mock_obj, self.mock_epc.energyml_objects)

    def test_put_object_failure(self):
        """Test object addition failure."""
        mock_obj = Mock()
        # Make append raise an exception
        self.mock_epc.energyml_objects = Mock()
        self.mock_epc.energyml_objects.append.side_effect = Exception("Error")

        result = self.storage.put_object(mock_obj)

        self.assertFalse(result)

    # @patch("energyml.utils.introspection.get_obj_identifier")
    # def test_delete_object_success(self, mock_get_identifier):
    #     """Test successful object deletion from EPC."""
    #     mock_obj1 = Mock()
    #     mock_obj2 = Mock()
    #     self.mock_epc.energyml_objects = [mock_obj1, mock_obj2]

    #     mock_get_identifier.side_effect = ["other-uri", self.test_uri]

    #     result = self.storage.delete_object(self.test_uri)

    #     self.assertTrue(result)
    #     self.assertEqual(len(self.mock_epc.energyml_objects), 1)
    #     self.assertEqual(self.mock_epc.energyml_objects[0], mock_obj1)

    @patch("energyml.utils.introspection.get_obj_identifier")
    def test_delete_object_not_found(self, mock_get_identifier):
        """Test object deletion when object doesn't exist."""
        mock_obj = Mock()
        self.mock_epc.energyml_objects = [mock_obj]

        mock_get_identifier.return_value = "different-uri"

        result = self.storage.delete_object(self.test_uri)

        self.assertFalse(result)
        self.assertEqual(len(self.mock_epc.energyml_objects), 1)

    # @patch("energyml.utils.data.datasets_io.read_external_dataset_array")
    # @patch("energyml.utils.introspection.get_obj_identifier")
    # def test_get_array_success(self, mock_get_identifier, mock_read_array):
    #     """Test successful array retrieval from HDF5."""
    #     mock_obj = Mock()
    #     self.mock_epc.energyml_objects = [mock_obj]
    #     mock_get_identifier.return_value = self.test_uri

    #     test_array = np.array([1, 2, 3, 4, 5])
    #     mock_read_array.return_value = [test_array]

    #     result = self.storage.get_array(self.test_uri, "/values")

    #     self.assertIsNotNone(result)
    #     if result is not None:
    #         np.testing.assert_array_equal(result, test_array)
    #     mock_read_array.assert_called_once_with(energyml_array=mock_obj, root_obj=mock_obj, epc=self.mock_epc)

    @patch("energyml.utils.introspection.get_obj_identifier")
    def test_get_array_object_not_found(self, mock_get_identifier):
        """Test array retrieval when parent object doesn't exist."""
        mock_get_identifier.return_value = "different-uri"

        result = self.storage.get_array(self.test_uri, "/values")

        self.assertIsNone(result)

    @patch("energyml.utils.data.datasets_io.read_external_dataset_array")
    @patch("energyml.utils.introspection.get_obj_identifier")
    def test_get_array_read_failure(self, mock_get_identifier, mock_read_array):
        """Test array retrieval when read operation fails."""
        mock_obj = Mock()
        self.mock_epc.energyml_objects = [mock_obj]
        mock_get_identifier.return_value = self.test_uri

        mock_read_array.side_effect = Exception("Read error")

        result = self.storage.get_array(self.test_uri, "/values")

        self.assertIsNone(result)

    @patch("energyml.utils.data.datasets_io.read_external_dataset_array")
    @patch("energyml.utils.introspection.get_obj_identifier")
    def test_get_array_empty_result(self, mock_get_identifier, mock_read_array):
        """Test array retrieval when read returns empty list."""
        mock_obj = Mock()
        self.mock_epc.energyml_objects = [mock_obj]
        mock_get_identifier.return_value = self.test_uri

        mock_read_array.return_value = []

        result = self.storage.get_array(self.test_uri, "/values")

        self.assertIsNone(result)

    def test_put_array_not_implemented(self):
        """Test that put_array raises NotImplementedError."""
        test_array = np.array([1, 2, 3, 4, 5])

        with self.assertRaises(NotImplementedError):
            self.storage.put_array(self.test_uri, "/values", test_array)

    # @patch("energyml.utils.introspection.get_obj_identifier")
    # def test_list_objects_success(self, mock_get_identifier):
    #     """Test successful object listing from EPC."""
    #     mock_obj1 = Mock()
    #     mock_obj2 = Mock()
    #     self.mock_epc.energyml_objects = [mock_obj1, mock_obj2]

    #     uri1 = "eml:///resqml20.obj1(123)"
    #     uri2 = "eml:///resqml20.obj2(456)"
    #     mock_get_identifier.side_effect = [uri1, uri2]

    #     result = self.storage.list_objects()

    #     self.assertEqual(len(result), 2)
    #     self.assertIn(uri1, result)
    #     self.assertIn(uri2, result)

    # @patch("energyml.utils.introspection.get_obj_identifier")
    # def test_list_objects_ignores_dataspace(self, mock_get_identifier):
    #     """Test that list_objects ignores dataspace parameter for EPC."""
    #     mock_obj = Mock()
    #     self.mock_epc.energyml_objects = [mock_obj]

    #     uri = "eml:///resqml20.obj(123)"
    #     mock_get_identifier.return_value = uri

    #     result = self.storage.list_objects(dataspace="ignored")

    #     self.assertEqual(len(result), 1)
    #     self.assertEqual(result[0], uri)

    def test_list_objects_empty(self):
        """Test object listing with no objects."""
        self.mock_epc.energyml_objects = []

        result = self.storage.list_objects()

        self.assertEqual(result, [])

    def test_close(self):
        """Test storage close (no-op for EPC)."""
        # Should not raise any exceptions
        self.storage.close()

    def test_save(self):
        """Test EPC file save."""
        test_path = "/path/to/file.epc"

        self.storage.save(test_path)

        self.mock_epc.export_file.assert_called_once_with(test_path)


class TestCreateStorageFactory(unittest.TestCase):
    """Test suite for the create_storage factory function."""

    def test_create_storage_from_etp_client(self):
        """Test creating storage from ETPClient instance."""
        from py_etp_client.etpclient import ETPClient

        mock_client = Mock(spec=ETPClient)

        storage = create_storage(mock_client)

        self.assertIsInstance(storage, ETPStorage)
        if isinstance(storage, ETPStorage):
            self.assertEqual(storage.client, mock_client)

    def test_create_storage_from_epc_instance(self):
        """Test creating storage from Epc instance."""
        from energyml.utils.epc import Epc

        mock_epc = Mock(spec=Epc)
        mock_epc.energyml_objects = []

        storage = create_storage(mock_epc)

        self.assertIsInstance(storage, EPCStorage)
        if isinstance(storage, EPCStorage):
            self.assertEqual(storage.epc, mock_epc)

    @patch("energyml.utils.epc.Epc.read_file")
    def test_create_storage_from_file_path(self, mock_read_file):
        """Test creating storage from file path."""
        test_path = "/path/to/file.epc"
        mock_epc = Mock()
        mock_read_file.return_value = mock_epc

        storage = create_storage(test_path)

        self.assertIsInstance(storage, EPCStorage)
        if isinstance(storage, EPCStorage):
            self.assertEqual(storage.epc, mock_epc)
        mock_read_file.assert_called_once_with(test_path)

    def test_create_storage_invalid_type(self):
        """Test that create_storage raises ValueError for invalid types."""
        with self.assertRaises(ValueError) as context:
            create_storage(12345)

        self.assertIn("Unsupported source type", str(context.exception))

    def test_create_storage_none(self):
        """Test that create_storage raises ValueError for None."""
        with self.assertRaises(ValueError) as context:
            create_storage(None)

        self.assertIn("Unsupported source type", str(context.exception))


class TestStorageInterfaceIntegration(unittest.TestCase):
    """Integration tests to verify both implementations share the same interface."""

    def test_both_implementations_have_same_methods(self):
        """Verify both implementations provide all interface methods."""
        mock_client = Mock()
        mock_epc = Mock()
        mock_epc.energyml_objects = []

        etp_storage = ETPStorage(mock_client)
        epc_storage = EPCStorage(mock_epc)

        # Get all public methods
        etp_methods = [m for m in dir(etp_storage) if not m.startswith("_")]
        epc_methods = [m for m in dir(epc_storage) if not m.startswith("_")]

        # Both should have the same set of methods (except save which is EPC-specific)
        common_methods = set(etp_methods) & set(epc_methods)
        required_methods = {
            "get_object",
            "put_object",
            "delete_object",
            "get_array",
            "put_array",
            "list_objects",
            "close",
        }

        self.assertTrue(
            required_methods.issubset(common_methods),
            f"Missing methods: {required_methods - common_methods}",
        )

    def test_both_implementations_accept_same_parameters(self):
        """Verify method signatures are compatible across implementations."""
        import inspect

        mock_client = Mock()
        mock_epc = Mock()
        mock_epc.energyml_objects = []

        etp_storage = ETPStorage(mock_client)
        epc_storage = EPCStorage(mock_epc)

        methods_to_check = [
            "get_object",
            "put_object",
            "delete_object",
            "get_array",
            "put_array",
            "list_objects",
        ]

        for method_name in methods_to_check:
            etp_method = getattr(etp_storage, method_name)
            epc_method = getattr(epc_storage, method_name)

            etp_sig = inspect.signature(etp_method)
            epc_sig = inspect.signature(epc_method)

            # Parameter names should match
            etp_params = list(etp_sig.parameters.keys())
            epc_params = list(epc_sig.parameters.keys())

            self.assertEqual(
                etp_params,
                epc_params,
                f"Parameter mismatch for {method_name}: {etp_params} vs {epc_params}",
            )


if __name__ == "__main__":
    unittest.main()
