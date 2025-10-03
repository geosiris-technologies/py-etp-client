# Copyright (c) 2022-2023 Geosiris.
# SPDX-License-Identifier: Apache-2.0
from dataclasses import dataclass, field
from urllib.parse import urlparse, urlunparse
import logging
from typing import Any, Dict, List
from enum import Enum
from dotenv import load_dotenv
import os
import json
import yaml

from energyml.utils.epc import gen_uuid
from py_etp_client.auth import AuthConfigs, AuthMethod, EnvironmentSettable, JsonSerializable

from energyml.utils.constants import snake_case
from typing import Optional

# Documentation generation functions (imported for backward compatibility)
from py_etp_client.docs import (
    gen_serverconfig_env_vars_table,
    gen_authconfig_env_vars_table,
    gen_all_config_env_vars_tables,
)


ETP_CONFIG_FILE_PATH = "ETP_CONFIG_FILE_PATH"
ETP_CONFIG_LIST_FILE_PATH = "ETP_CONFIG_LIST_FILE_PATH"
ETP_CONFIG_ID = "ETP_CONFIG_ID"

ETP_CONFIGS_DEFAULT_PATH = "configs/all_server_configs.json"


@dataclass
class ServerConfig(AuthConfigs, EnvironmentSettable):
    @classmethod
    def from_dict(cls, d: dict) -> "ServerConfig":
        # Remove 'include' if present
        d = dict(d)
        # all key snake_case to lower case with underscores
        d.pop("include", None)
        d = {snake_case(k): v for k, v in d.items()}

        # filter keys to only those in the dataclass
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        # logging.info(f"Creating ServerConfig from dict with keys: {list(d.keys())}")

        return cls(**{k: v for k, v in d.items() if k in valid_keys})

    @classmethod
    def from_file(cls, file_path: Optional[str] = None) -> "ServerConfig":
        if file_path is None:
            file_path = (
                os.getenv(ETP_CONFIG_LIST_FILE_PATH, None)
                or os.getenv(ETP_CONFIG_FILE_PATH)
                or os.getenv(
                    "INI_FILE_PATH",
                )
                or ETP_CONFIGS_DEFAULT_PATH
            )
        try:
            ext = os.path.splitext(file_path)[1].lower()
            with open(file_path, "r") as f:
                if ext in (".yml", ".yaml"):
                    d = yaml.safe_load(f)
                elif ext == ".json":
                    d = json.load(f)
                else:
                    raise ValueError(f"Unsupported config file extension: {ext}")
            if "configs" in d or "include" in d:
                raise ValueError("File contains multiple configs, use ServerConfigs.read_configs() instead.")
            return cls.from_dict(d)
        except Exception as e:
            # trying to load from list of configs
            server_configs = ServerConfigs.read_configs(file_path)
            if server_configs:
                config_id = os.getenv(ETP_CONFIG_ID, None)
                logging.info(f"ETP_CONFIG_ID : {config_id}")
                if config_id and len(server_configs.configs) > 1:
                    cfg = server_configs.get_by_id(config_id)
                    if cfg:
                        return cfg
                    else:
                        raise ValueError(f"Config with id or name '{config_id}' not found in {file_path}")
                elif len(server_configs.configs) >= 1:
                    logging.info(
                        f"Warning: Loaded {len(server_configs.configs)} configs from {file_path}. Using the first one. To select a specific config, set the ETP_CONFIG_ID environment variable."
                    )
                    return list(server_configs.configs.values())[0]
            else:
                logging.error(f"Failed to load configs from {file_path}: {e}")
                raise

    _id: str = field(default="", metadata={"description": "Unique identifier for the server configuration"})
    name: str = field(default="", metadata={"description": "Human-readable name for the server configuration"})
    url: str = field(default="", metadata={"description": "ETP server URL (including protocol and port)"})
    timeout: int = field(default=30, metadata={"description": "Connection timeout in seconds"})
    max_web_socket_frame_payload_size: int = field(
        default=900000, metadata={"description": "Maximum WebSocket frame payload size in bytes"}
    )
    max_web_socket_message_payload_size: int = field(
        default=900000, metadata={"description": "Maximum WebSocket message payload size in bytes"}
    )
    verify_ssl: bool = field(default=False, metadata={"description": "Whether to verify SSL certificates"})
    auto_reconnect: bool = field(
        default=True, metadata={"description": "Whether to automatically reconnect on connection loss"}
    )
    use_transactions: bool = field(default=False, metadata={"description": "Whether to use ETP transactions"})
    token_expires_at: float = field(default=0.0, metadata={"description": "Token expiration timestamp (epoch time)"})
    supported_data_objects: List[str] = field(
        default_factory=list, metadata={"description": "List of supported ETP data object types"}
    )
    supported_protocols: List[str] = field(
        default_factory=list, metadata={"description": "List of supported ETP protocol versions"}
    )
    # OSDU
    additional_headers: Dict[str, str] = field(
        default_factory=dict, metadata={"description": "Additional HTTP headers to include in requests"}
    )
    acl_owners: List[str] = field(default_factory=list, metadata={"description": "OSDU ACL owners list"})
    acl_viewers: List[str] = field(default_factory=list, metadata={"description": "OSDU ACL viewers list"})
    legal_tags: List[str] = field(default_factory=list, metadata={"description": "OSDU legal tags list"})
    data_countries: List[str] = field(default_factory=list, metadata={"description": "OSDU data countries list"})

    def __post_init__(self):
        super().__post_init__()
        if not self._id or len(self._id) == 0:
            self._id = gen_uuid()

        # logging.debug(f"Initialized ServerConfig with id: {self._id}")
        # logging.debug(f"ServerConfig details: {self.to_dict()}")

        # Use environment variables if values are not provided
        self.name = self.name or os.getenv("SERVER_NAME", "")
        self.url = self.url or os.getenv("URL", "localhost")
        self.timeout = self.timeout if self.timeout is not None else int(os.getenv("TIMEOUT", 30))
        self.max_web_socket_frame_payload_size = (
            self.max_web_socket_frame_payload_size
            if self.max_web_socket_frame_payload_size is not None
            else int(os.getenv("MAX_WEB_SOCKET_FRAME_PAYLOAD_SIZE", 900000))
        )
        self.max_web_socket_message_payload_size = (
            self.max_web_socket_message_payload_size
            if self.max_web_socket_message_payload_size is not None
            else int(os.getenv("MAX_WEB_SOCKET_MESSAGE_PAYLOAD_SIZE", 900000))
        )
        self.verify_ssl = (
            self.verify_ssl if self.verify_ssl is not None else os.getenv("VERIFY_SSL", "false").lower() == "true"
        )
        self.auto_reconnect = (
            self.auto_reconnect
            if self.auto_reconnect is not None
            else os.getenv("AUTO_RECONNECT", "true").lower() == "true"
        )
        self.use_transactions = (
            self.use_transactions
            if self.use_transactions is not None
            else os.getenv("USE_TRANSACTIONS", "false").lower() == "true"
        )
        self.token_expires_at = (
            self.token_expires_at if self.token_expires_at is not None else float(os.getenv("TOKEN_EXPIRES_AT", 0.0))
        )

        # List and dict fields from env (expecting JSON or comma-separated)
        def parse_env_list(var, default):
            val = os.getenv(var)
            if val is None:
                return default
            try:
                return json.loads(val)
            except Exception:
                return [v.strip() for v in val.split(",") if v.strip()]

        def parse_env_dict(var, default):
            val = os.getenv(var)
            if val is None:
                return default
            try:
                return json.loads(val)
            except Exception:
                return default

        self.supported_data_objects = self.supported_data_objects or parse_env_list("SUPPORTED_DATA_OBJECTS", [])
        self.supported_protocols = self.supported_protocols or parse_env_list("SUPPORTED_PROTOCOLS", [])
        self.additional_headers = self.additional_headers or parse_env_dict("ADDITIONAL_HEADERS", {})
        self.acl_owners = self.acl_owners or parse_env_list("ACL_OWNERS", [])
        self.acl_viewers = self.acl_viewers or parse_env_list("ACL_VIEWERS", [])
        self.legal_tags = self.legal_tags or parse_env_list("LEGAL_TAGS", [])
        self.data_countries = self.data_countries or parse_env_list("DATA_COUNTRIES", [])

    def to_dict(self) -> Dict:
        d = super().to_dict()
        # updating using class fields introspection
        for field_name in self.__dataclass_fields__:
            if field_name not in d:
                if isinstance(getattr(self, field_name), Enum):
                    d[field_name] = getattr(self, field_name).value
                elif isinstance(getattr(self, field_name), JsonSerializable):
                    d[field_name] = getattr(self, field_name).to_dict()
                else:
                    d[field_name] = getattr(self, field_name)
        return d


class ServerConfigs(JsonSerializable):
    configs: Dict[str, ServerConfig] = field(default_factory=dict)

    """
    Holds a list of ServerConfig objects and provides methods to load from file(s), lookup by id or name.
    """

    def __init__(self, configs: Optional[Dict[str, ServerConfig]] = None):
        # if parameter is not read from env file path, load from default location
        if configs is None:
            file_path = (
                os.getenv(ETP_CONFIG_LIST_FILE_PATH, None)
                or os.getenv(
                    "INI_FILE_PATH",
                )
                or ETP_CONFIGS_DEFAULT_PATH
            )
            if os.path.exists(file_path):
                self.configs = self._read_configs(file_path)
            else:
                logging.warning(f"Config file {file_path} not found. Initializing empty ServerConfigs.")
                self.configs: Dict[str, ServerConfig] = {}
        else:
            self.configs: Dict[str, ServerConfig] = {cfg._id: cfg for cfg in configs.values()}

    @classmethod
    def read_configs(cls, file_path: str) -> "ServerConfigs":
        return cls(cls._read_configs(file_path))

    @classmethod
    def _read_configs(cls, file_path: str) -> Dict[str, ServerConfig]:
        """
        Reads a YAML or JSON file. If 'include' is present, loads all referenced files and aggregates ServerConfig objects.
        """

        def load_file(path):
            ext = os.path.splitext(path)[1].lower()
            with open(path, "r") as f:
                if ext in (".yml", ".yaml"):
                    return yaml.safe_load(f)
                elif ext == ".json":
                    return json.load(f)
                else:
                    raise ValueError(f"Unsupported config file extension: {ext}")

        configs = {}
        base_dir = os.path.dirname(file_path)
        main_config = load_file(file_path)
        if isinstance(main_config, dict) and ("include" in main_config or "configs" in main_config):
            for rel_path in main_config.get("include", []):
                sub_path = os.path.join(base_dir, rel_path)
                if os.path.exists(sub_path):
                    sub_config = load_file(sub_path)
                    if isinstance(sub_config, dict):
                        c = ServerConfig.from_dict(sub_config)
                        configs[c._id] = c
                    elif isinstance(sub_config, list):
                        for c in sub_config:
                            _c = ServerConfig.from_dict(c)
                            configs[_c._id] = _c
                else:
                    print(f"Warning: Included config file {sub_path} not found. Skipping.")
            if "configs" in main_config:
                # print("Found 'configs' in main config")
                for c in main_config["configs"].values():
                    # print("Processing config:", c)
                    _c = ServerConfig.from_dict(c)
                    configs[_c._id] = _c
        elif isinstance(main_config, dict):
            _c = ServerConfig.from_dict(main_config)
            configs[_c._id] = _c
        elif isinstance(main_config, list):
            for c in main_config:
                _c = ServerConfig.from_dict(c)
                configs[_c._id] = _c
        return configs

    def get_by_id(self, id_or_name: str) -> Optional[ServerConfig]:
        """
        Get a ServerConfig by its _id, or if not found, by its name (case-insensitive).
        """
        if id_or_name in self.configs:
            return self.configs[id_or_name]
        # Try to find by name (case-insensitive)
        for cfg in self.configs.values():
            if cfg.name.lower() == id_or_name.lower():
                return cfg
        return None

    def all(self) -> Dict[str, ServerConfig]:
        return self.configs

    def __repr__(self):
        return f"ServerConfigs({self.configs})"

    def to_dict(self) -> Dict[str, Any]:
        """
        Converts the ServerConfigs object to a dictionary.
        """
        return {cfg_id: self.configs[cfg_id].to_dict() for cfg_id in self.configs.keys()}


class ETPConfig:
    """
    deprecated: use ServerConfig instead
    """

    # Load environment variables from .env file
    load_dotenv()

    # Access the environment variables

    PORT = os.getenv("PORT", "443")
    URL: str = os.getenv("URL", "localhost")
    USERNAME = os.getenv("USERNAME")
    PASSWORD = os.getenv("PASSWORD")
    ADDITIONAL_HEADERS = os.getenv("ADDITIONAL_HEADERS")
    ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
    TOKEN_URL = os.getenv("TOKEN_URL")
    TOKEN_GRANT_TYPE = os.getenv("TOKEN_GRANT_TYPE")
    TOKEN_SCOPE = os.getenv("TOKEN_SCOPE")
    TOKEN_REFRESH_TOKEN = os.getenv("TOKEN_REFRESH_TOKEN")
    USE_REST = os.getenv("USE_REST", "false").lower() == "true"

    ACL_OWNERS = os.getenv("ACL_OWNERS", "[]")
    ACL_VIEWERS = os.getenv("ACL_VIEWERS", "[]")
    LEGAL_TAGS = os.getenv("LEGAL_TAGS", "[]")
    OTHER_RELEVANT_DATA_COUNTRIES = os.getenv("OTHER_RELEVANT_DATA_COUNTRIES", "[]")

    # Path to YAML file (from .env)
    INI_FILE_PATH = os.getenv("INI_FILE_PATH")

    def __init__(self, ini_file_path=None):
        """
        Initialize the ETPConfig class and load environment variables.
        If an INI_FILE_PATH is provided, load additional config from the YAML file.
        If the config file contains an 'include' key, load and merge all referenced files.
        """
        if ini_file_path is not None:
            self.load_from_yml(ini_file_path)
        elif self.INI_FILE_PATH:
            self.load_from_yml(self.INI_FILE_PATH)

    def load_from_yml(self, yml_file_path):
        """
        Load additional config from the YAML file and overwrite .env variables.
        If the file contains an 'include' key (list of files), load and merge all referenced files.
        """
        print("reading yml file")
        print(yml_file_path)
        if not os.path.exists(yml_file_path):
            print(f"Warning: YAML file {yml_file_path} not found. Skipping YAML configuration.")
            return

        with open(yml_file_path, "r") as yml_file:
            yml_config = yaml.safe_load(yml_file)

        # If 'include' key exists, merge all referenced files
        if isinstance(yml_config, dict) and "include" in yml_config:
            for rel_path in yml_config["include"]:
                # Support nested directories
                config_path = os.path.join(os.path.dirname(yml_file_path), rel_path)
                if os.path.exists(config_path):
                    with open(config_path, "r") as sub_file:
                        sub_config = yaml.safe_load(sub_file)
                        if sub_config:
                            for key, value in sub_config.items():
                                setattr(self, key, value)
                else:
                    print(f"Warning: Included YAML file {config_path} not found. Skipping.")
        # Merge top-level config (if not just an include file)
        if isinstance(yml_config, dict):
            for key, value in yml_config.items():
                if key != "include":
                    setattr(self, key, value)

    def to_dict(self):
        """
        Converts the Config object to a dictionary.
        """
        return {
            "PORT": self.PORT,
            "URL": self.URL,
            "USERNAME": self.USERNAME,
            "PASSWORD": self.PASSWORD,
            "ADDITIONAL_HEADERS": self.ADDITIONAL_HEADERS,
            "ACCESS_TOKEN": self.ACCESS_TOKEN,
            "TOKEN_URL": self.TOKEN_URL,
            "TOKEN_GRANT_TYPE": self.TOKEN_GRANT_TYPE,
            "TOKEN_SCOPE": self.TOKEN_SCOPE,
            "TOKEN_REFRESH_TOKEN": self.TOKEN_REFRESH_TOKEN,
            "USE_REST": self.USE_REST,
            "INI_FILE_PATH": self.INI_FILE_PATH,
            "ACL_OWNERS": self.ACL_OWNERS,
            "ACL_VIEWERS": self.ACL_VIEWERS,
            "LEGAL_TAGS": self.LEGAL_TAGS,
            "OTHER_RELEVANT_DATA_COUNTRIES": self.OTHER_RELEVANT_DATA_COUNTRIES,
        }

    def to_json(self):
        """
        Serializes the Config object to a JSON string.
        """
        return json.dumps(self.to_dict(), indent=4)

    def __repr__(self):
        """
        Custom string representation for print() or logging.
        """
        return f"Config({json.dumps(self.to_dict(), indent=4)})"

    @classmethod
    def get_config(cls):
        return cls().to_dict()

    def as_server_config(self) -> ServerConfig:
        """
        Convert this ETPConfig instance to a ServerConfig instance.
        """
        auth_kwargs = {
            "auth_method": (
                AuthMethod.BASIC
                if self.USERNAME and self.PASSWORD
                else AuthMethod.BEARER_TOKEN if self.ACCESS_TOKEN else AuthMethod.NONE
            ),
            "basic": (
                {"username": self.USERNAME, "password": self.PASSWORD} if self.USERNAME and self.PASSWORD else None
            ),
            "bearer_token": {"bearer_token": self.ACCESS_TOKEN} if self.ACCESS_TOKEN else None,
        }
        additional_headers = {}
        if self.ADDITIONAL_HEADERS:
            try:
                additional_headers = json.loads(self.ADDITIONAL_HEADERS)
            except Exception:
                print("Warning: ADDITIONAL_HEADERS is not valid JSON. Using empty dict.")

        url = self.URL
        if str(self.PORT) and str(self.PORT) not in url:
            # parse url using module urllib
            parsed = urlparse(url)
            netloc = f"{parsed.hostname}:{self.PORT}"
            parsed = parsed._replace(netloc=netloc)
            url = urlunparse(parsed)
        return ServerConfig(
            url=url,
            timeout=10,
            verify_ssl=True,
            additional_headers=additional_headers,
            acl_owners=json.loads(self.ACL_OWNERS) if self.ACL_OWNERS else [],
            acl_viewers=json.loads(self.ACL_VIEWERS) if self.ACL_VIEWERS else [],
            legal_tags=json.loads(self.LEGAL_TAGS) if self.LEGAL_TAGS else [],
            data_countries=(
                json.loads(self.OTHER_RELEVANT_DATA_COUNTRIES) if self.OTHER_RELEVANT_DATA_COUNTRIES else []
            ),
            **auth_kwargs,
        )


# Documentation generation functions moved to docs.py


# Deprecated function for backward compatibility
def _gen_serverconfig_env_vars_table():
    """Generate a markdown table listing all environment variables for ServerConfig."""
    return gen_serverconfig_env_vars_table()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    servs = ServerConfigs.read_configs("configs/all_server_configs.json")
    # azure_cfg = servs.get_by_id("azure")
    # print(azure_cfg.to_dotenv(keep_empty=True))

    # print(ServerConfig.list_env_vars())

    # print(gen_all_config_env_vars_tables())

    # print(servs.to_json(True))

    # # Test ETPConfig loading from .env and YAML
    # config = ETPConfig()
    # print(config)
    # print(config.as_server_config().to_json())

    # print("=" * 40)
    # print(servs.get_by_id("azure").to_json())

    # print(ServerConfig.from_env().to_json())

    # print(ServerConfig._field_names_list())

    for cfg in servs.all().values():
        print("=" * 10 + " " + cfg.name)
        print(cfg.to_dotenv(keep_empty=False))
