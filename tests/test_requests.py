# Copyright (c) 2022-2023 Geosiris.
# SPDX-License-Identifier: Apache-2.0
import numpy as np
from py_etp_client.etp_requests import get_array_class_from_dtype

from py_etp_client import (
    ArrayOfInt,
    ArrayOfLong,
    ArrayOfBoolean,
    ArrayOfFloat,
    ArrayOfDouble,
    ArrayOfBytes,
    ArrayOfString,
    AnyArray,
)


def test_get_array_class_from_dtype():

    # Following line result depends on numpy version. For numpy <2 returns int and for numpy >=2 returns long
    # assert get_array_class_from_dtype(str(np.array([1, 2, 3]).dtype)) == ArrayOfLong
    assert get_array_class_from_dtype("int32") == ArrayOfInt
    assert get_array_class_from_dtype("long") == ArrayOfLong
    assert get_array_class_from_dtype(str(np.array([True, False]).dtype)) == ArrayOfBoolean
    assert get_array_class_from_dtype(np.array([1.2, 0.2]).dtype) == ArrayOfDouble
    assert get_array_class_from_dtype("float64") == ArrayOfDouble
    assert get_array_class_from_dtype("float") == ArrayOfFloat
    assert get_array_class_from_dtype(str(np.array(["1.2", "0.2"]).dtype)) == ArrayOfString


# print(get_array_class_from_dtype(str(np.array([1, 2, 3]).dtype)))
