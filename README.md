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


## Example of use : 

Check "example" folder for a example project that uses this library.

To test the example : 
Create an .env file in the example folder with the following content : 

```env
INI_FILE_PATH=../configs/sample.yml 
```

Then create the corresponding yaml file : 
```yaml
# sample.yml
PORT: 443
URL: wss://....
USERNAME: username
PASSWORD: pwd
ADDITIONAL_HEADERS:
  - data-partition-id: osdu
TOKEN: ACCESS_TOKEN
TOKEN_URL: https://.../token
TOKEN_GRANT_TYPE: ...
TOKEN_SCOPE: ...
TOKEN_REFRESH_TOKEN: ...
```

Finally run the client script : 
```bash
poetry install
poetry run client
```


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

It is also possible to create an AuthConfig (subclass) from environment variables.

| Class | Environment Variable | Description |
|-------|----------------------|-------------|
| BasicAuthConfig | `BASIC_USERNAME` | Username for basic authentication |
| BasicAuthConfig | `BASIC_PASSWORD` | Password for basic authentication |
| OAuth2Config | `OAUTH2_CLIENT_ID` | OAuth2 client ID |
| OAuth2Config | `OAUTH2_CLIENT_SECRET` | OAuth2 client secret |
| OAuth2Config | `OAUTH2_REFRESH_TOKEN` | OAuth2 refresh token (optional) |
| OAuth2Config | `OAUTH2_TOKEN_URL` | OAuth2 token endpoint URL |
| OAuth2Config | `OAUTH2_SCOPE` | OAuth2 scopes (space-separated) |
| AzureADConfig | `AZUREAD_TENANT_ID` | Azure AD tenant ID |
| AzureADConfig | `AZUREAD_CLIENT_ID` | Azure AD application (client) ID |
| AzureADConfig | `AZUREAD_CLIENT_SECRET` | Azure AD client secret |
| AzureADConfig | `AZUREAD_SCOPE` | Azure AD scopes (space-separated) |
| AWSCognitoConfig | `AWSCOGNITO_USER_POOL_ID` | AWS Cognito user pool ID |
| AWSCognitoConfig | `AWSCOGNITO_APP_CLIENT_ID` | AWS Cognito app client ID |
| AWSCognitoConfig | `AWSCOGNITO_CLIENT_SECRET` | AWS Cognito app client secret |
| AWSCognitoConfig | `AWSCOGNITO_AWS_REGION` | AWS region for Cognito |
| AWSCognitoConfig | `AWSCOGNITO_USERNAME` | Cognito username |
| AWSCognitoConfig | `AWSCOGNITO_PASSWORD` | Cognito password |
| AWSCognitoConfig | `AWSCOGNITO_REFRESH_TOKEN` | Cognito refresh token (optional) |
| GCPOAuthConfig | `GCPO_GCP_PROJECT_ID` | GCP project ID |
| GCPOAuthConfig | `GCPO_SERVICE_ACCOUNT_KEY` | GCP service account key (JSON string or file path) |
| GCPOAuthConfig | `GCPO_SCOPE` | GCP OAuth2 scopes (space-separated) |
| BearerTokenConfig | `BEARERTOKEN_CACHED_TOKEN` | Cached authentication token |
| BearerTokenConfig | `BEARERTOKEN_TOKEN_EXPIRES_AT` | Token expiration time (epoch time) |