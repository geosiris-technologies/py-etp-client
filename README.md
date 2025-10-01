<!--
Copyright (c) 2022-2023 Geosiris.
SPDX-License-Identifier: Apache-2.0
-->

# py-etp-client

[![License](https://img.shields.io/pypi/l/py-etp-client)](https://github.com/geosiris-technologies/py-etp-client/blob/main/LICENSE)
[![Documentation Status](https://readthedocs.org/projects/py-etp-client/badge/?version=latest)](https://py-etp-client.readthedocs.io/en/latest/?badge=latest)
[![Python CI](https://github.com/geosiris-technologies/py-etp-client/actions/workflows/ci-tests.yml/badge.svg)](https://github.com/geosiris-technologies/py-etp-client/actions/workflows/ci-tests.yml)
[![Python version](https://img.shields.io/pypi/pyversions/py-etp-client)](https://pypi.org/project/py-etp-client/)
[![PyPI Version](https://img.shields.io/pypi/v/py-etp-client)](https://badge.fury.io/py/py-etp-client)
[![Status](https://img.shields.io/pypi/status/py-etp-client)](https://pypi.org/project/py-etp-client/)
[![Codecov](https://codecov.io/gh/geosiris-technologies/py-etp-client/branch/main/graph/badge.svg)](https://codecov.io/gh/geosiris-technologies/py-etp-client)


An etp client python module to make an etp websocket connexion



## installation :

Pip:
```bash
pip install py-etp-client
```

Poetry
```bash
poetry add py-etp-client
```

## Usage : 


Check [example](https://github.com/geosiris-technologies/py-etp-client/tree/main/example/py_etp_client_example/main.py) for more information

### Interactive client (in example folder): 
You can for example run a interactive client with the following code : 

Install : 
```bash
poetry install
``` 

Run the client :

```bash
poetry run client
```


# Configuration and authetication
You can configure the client with a configuration file (yaml or json) or directly in code.
You can also use different authentication methods : 
- Basic authentication (username and password)
- OAuth2 (client ID and secret)
- Azure AD (client ID and secret)
- AWS Cognito (user pool ID and app client ID)
- GCP OAuth (service account key)
- Bearer token (pre-fetched token)

It is also possible to create configurations using environment variables.


## Server Configuration

These environment variables configure the ETP server connection and behavior:

| Environment Variable | Description |
|----------------------|-------------|
| `SERVER__ID` | Unique identifier for the server configuration |
| `SERVER_NAME` | Human-readable name for the server configuration |
| `SERVER_URL` | ETP server URL (including protocol and port) |
| `SERVER_TIMEOUT` | Connection timeout in seconds |
| `SERVER_MAX_WEB_SOCKET_FRAME_PAYLOAD_SIZE` | Maximum WebSocket frame payload size in bytes |
| `SERVER_MAX_WEB_SOCKET_MESSAGE_PAYLOAD_SIZE` | Maximum WebSocket message payload size in bytes |
| `SERVER_VERIFY_SSL` | Whether to verify SSL certificates |
| `SERVER_AUTO_RECONNECT` | Whether to automatically reconnect on connection loss |
| `SERVER_USE_TRANSACTIONS` | Whether to use ETP transactions |
| `SERVER_SUPPORTED_DATA_OBJECTS` | List of supported ETP data object types |
| `SERVER_SUPPORTED_PROTOCOLS` | List of supported ETP protocol versions |
| `SERVER_ADDITIONAL_HEADERS` | Additional HTTP headers to include in requests |
| `SERVER_ACL_OWNERS` | OSDU ACL owners list |
| `SERVER_ACL_VIEWERS` | OSDU ACL viewers list |
| `SERVER_LEGAL_TAGS` | OSDU legal tags list |
| `SERVER_DATA_COUNTRIES` | OSDU data countries list |
| `SERVER_AUTH_METHOD` | Authentication method to use (e.g., basic, oauth2, azure, aws, gcp, bearer) |

## Basic Authentication

Configure HTTP Basic Authentication credentials:

| Environment Variable | Description |
|----------------------|-------------|
| `BASIC_USERNAME` | Username for basic authentication |
| `BASIC_PASSWORD` | Password for basic authentication |

## OAuth2 Authentication

Configure OAuth2 client credentials flow:

| Environment Variable | Description |
|----------------------|-------------|
| `OAUTH2_CLIENT_ID` | OAuth2 client ID |
| `OAUTH2_CLIENT_SECRET` | OAuth2 client secret |
| `OAUTH2_REFRESH_TOKEN` | OAuth2 refresh token (optional) |
| `OAUTH2_TOKEN_URL` | OAuth2 token endpoint URL |
| `OAUTH2_SCOPE` | OAuth2 scopes (space-separated) |

## Azure Active Directory Authentication

Configure Azure AD authentication:

| Environment Variable | Description |
|----------------------|-------------|
| `AZUREAD_TENANT_ID` | Azure AD tenant ID |
| `AZUREAD_CLIENT_ID` | Azure AD application (client) ID |
| `AZUREAD_CLIENT_SECRET` | Azure AD client secret |
| `AZUREAD_SCOPE` | Azure AD scopes (space-separated) |

## AWS Cognito Authentication

Configure AWS Cognito authentication:

| Environment Variable | Description |
|----------------------|-------------|
| `AWSCOGNITO_USER_POOL_ID` | AWS Cognito user pool ID |
| `AWSCOGNITO_APP_CLIENT_ID` | AWS Cognito app client ID |
| `AWSCOGNITO_CLIENT_SECRET` | AWS Cognito app client secret |
| `AWSCOGNITO_AWS_REGION` | AWS region for Cognito |
| `AWSCOGNITO_USERNAME` | Cognito username |
| `AWSCOGNITO_PASSWORD` | Cognito password |
| `AWSCOGNITO_REFRESH_TOKEN` | Cognito refresh token (optional) |

## Google Cloud Platform Authentication

Configure GCP OAuth2 authentication:

| Environment Variable | Description |
|----------------------|-------------|
| `GCPO_GCP_PROJECT_ID` | GCP project ID |
| `GCPO_SERVICE_ACCOUNT_KEY` | GCP service account key (JSON string or file path) |
| `GCPO_SCOPE` | GCP OAuth2 scopes (space-separated) |

## Bearer Token Authentication

Configure static bearer token authentication:

| Environment Variable | Description |
|----------------------|-------------|
| `BEARERTOKEN_CACHED_TOKEN` | Cached authentication token |
| `BEARERTOKEN_TOKEN_EXPIRES_AT` | Token expiration time (epoch time) |

## Usage

### Setting Environment Variables

You can set these environment variables in several ways:

1. **System environment variables**:
   ```bash
   export SERVER_URL=wss://example.com/etp
   export SERVER_TIMEOUT=60
   ```

2. **`.env` file** (recommended for development):
   ```
   SERVER_URL=wss://example.com/etp
   SERVER_TIMEOUT=60
   AZUREAD_TENANT_ID=your-tenant-id
   AZUREAD_CLIENT_ID=your-client-id
   ```

3. **Programmatically**:
   ```python
   import os
   os.environ['SERVER_URL'] = 'wss://example.com/etp'
   ```

### Loading from Environment

```python
from py_etp_client.etpconfig import ServerConfig

# Load configuration from environment variables
config = ServerConfig.from_env()
```

### Complex Data Types

For list and dictionary fields, you can provide JSON strings:

```bash
export SERVER_SUPPORTED_DATA_OBJECTS='["resqml20.obj_Well", "resqml20.obj_WellboreGeometry"]'
export SERVER_ADDITIONAL_HEADERS='{"data-partition-id": "opendes", "Authorization": "Bearer token"}'
```
