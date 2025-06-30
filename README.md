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