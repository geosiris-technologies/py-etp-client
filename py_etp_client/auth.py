# Copyright (c) 2022-2023 Geosiris.
# SPDX-License-Identifier: Apache-2.0
from base64 import b64encode


def basic_auth_encode(username: str, password: str):
    assert ":" not in username
    user_pass = f"{username}:{password}"
    return b64encode(user_pass.encode()).decode()
