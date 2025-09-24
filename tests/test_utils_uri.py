# Copyright (c) 2022-2023 Geosiris.
# SPDX-License-Identifier: Apache-2.0
import pytest
from py_etp_client.utils import get_valid_uri_str, reshape_uris_as_str_list
from energyml.utils.uri import Uri as ETPUri


class DummyUri:
    pass


def test_get_valid_uri_str_with_none():
    assert get_valid_uri_str(None) == "eml:///"


def test_get_valid_uri_str_with_valid_str():
    assert get_valid_uri_str("eml:///dataspace('myuri')") == "eml:///dataspace('myuri')"


def test_get_valid_uri_str_with_non_eml_str():
    assert get_valid_uri_str("myuri") == str(ETPUri(dataspace="myuri"))


def test_get_valid_uri_str_with_etpuri():
    uri = ETPUri(dataspace="myuri")
    assert get_valid_uri_str(uri) == str(uri)


def test_get_valid_uri_str_with_invalid_type():
    with pytest.raises(ValueError):
        get_valid_uri_str(123)  # type: ignore
    with pytest.raises(ValueError):
        get_valid_uri_str(DummyUri())  # type: ignore


def test_reshape_uris_as_str_list_with_str():
    assert reshape_uris_as_str_list("foo") == ["foo"]


def test_reshape_uris_as_str_list_with_etpuri():
    uri = ETPUri(dataspace="foo")
    assert reshape_uris_as_str_list(uri) == [str(uri)]


def test_reshape_uris_as_str_list_with_list_of_str():
    assert reshape_uris_as_str_list(["foo", "bar"]) == ["eml:///dataspace('foo')", "eml:///dataspace('bar')"]


def test_reshape_uris_as_str_list_with_list_of_etpuri():
    uris = [ETPUri(dataspace="foo"), ETPUri(dataspace="bar")]
    assert reshape_uris_as_str_list(uris) == [str(uris[0]), str(uris[1])]


def test_reshape_uris_as_str_list_with_dict_str():
    d = {"a": "foo", "b": "bar"}
    assert reshape_uris_as_str_list(d) == ["eml:///dataspace('foo')", "eml:///dataspace('bar')"]


def test_reshape_uris_as_str_list_with_dict_etpuri():
    d = {"a": ETPUri(dataspace="foo"), "b": ETPUri(dataspace="bar")}
    assert reshape_uris_as_str_list(d) == [str(d["a"]), str(d["b"])]


def test_reshape_uris_as_str_list_with_invalid_type():
    with pytest.raises(ValueError):
        reshape_uris_as_str_list(123)  # type: ignore
    with pytest.raises(ValueError):
        reshape_uris_as_str_list(DummyUri())  # type: ignore
