# Copyright (c) 2022-2023 Geosiris.
# SPDX-License-Identifier: Apache-2.0
import base64
from dataclasses import dataclass, asdict, field, Field
from enum import Enum
from abc import ABC
import logging
import os
import re
from typing import Optional, Dict, Any, get_origin
from datetime import datetime
import requests
import json
import time
from energyml.utils.constants import snake_case
from energyml.utils.introspection import is_primitive, is_enum


from base64 import b64encode


class AuthError(Exception):
    """Base class for authentication errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)


class AzureADError(AuthError):
    """Azure AD specific authentication errors."""

    ERROR_MESSAGES = {
        "invalid_resource": (
            "The specified Azure AD resource was not found. This usually means:\n"
            "1. The application hasn't been properly registered in Azure AD\n"
            "2. The required API permissions haven't been granted\n"
            "3. The scope URL might be incorrect\n\n"
            "Suggested actions:\n"
            "- Verify the application registration in Azure Portal\n"
            "- Check if admin consent has been granted for the API permissions\n"
            "- Verify the scope URL is correct for your Azure service\n"
            "- Contact your Azure administrator if the issue persists"
        ),
        "invalid_client": (
            "Client authentication failed. This usually means:\n"
            "1. The client ID or secret is incorrect\n"
            "2. The client secret has expired\n"
            "3. The application registration is invalid\n\n"
            "Suggested actions:\n"
            "- Verify your client ID and secret are correct\n"
            "- Check if the client secret has expired in Azure Portal\n"
            "- Verify the application registration status"
        ),
        "unauthorized_client": (
            "The application is not authorized to request tokens. This usually means:\n"
            "1. The application doesn't have the required permissions\n"
            "2. The tenant ID is incorrect\n"
            "3. The application is registered in a different tenant\n\n"
            "Suggested actions:\n"
            "- Verify the tenant ID is correct\n"
            "- Check application permissions in Azure Portal\n"
            "- Ensure the application is registered in the correct tenant"
        ),
    }

    def __init__(
        self,
        message: str,
        error_code: str,
        response_data: Optional[Dict[str, Any]] = None,
    ):
        self.error_code = error_code
        self.response_data = response_data or {}

        # Get detailed message for known error codes
        detailed_message = self.ERROR_MESSAGES.get(
            error_code,
            "An unknown Azure AD error occurred. Please check your configuration.",
        )

        # Combine error details
        full_message = (
            f"{message}\n\n"
            f"Error Code: {error_code}\n"
            f"Correlation ID: {response_data.get('correlation_id', 'N/A')}\n"
            f"Timestamp: {response_data.get('timestamp', 'N/A')}\n\n"
            f"Details:\n{detailed_message}"
        )

        super().__init__(full_message, response_data)


class AuthMethod(Enum):
    NONE = "none"
    BASIC = "basic"
    OAUTH2 = "oauth2"
    AZURE_AD = "azure_ad"
    AWS_COGNITO = "aws_cognito"
    GCP_OAUTH = "gcp_oauth"
    BEARER_TOKEN = "bearer_token"

    def __new__(cls, value):
        obj = object.__new__(cls)
        obj._value_ = value
        return obj

    @classmethod
    def _missing_(cls, value):
        """Handle missing values by trying to match with flexible names."""
        if isinstance(value, str):
            value_lower = value.lower()
            for member in cls:
                if (
                    member.value == value
                    or member.name.lower() == value_lower
                    or member.name.lower().startswith(value_lower)
                ):
                    return member
        return None


class JsonSerializable:
    def to_dict(self) -> dict:
        raise NotImplementedError

    def to_json(self, pretty: bool = True) -> str:
        return json.dumps(self.to_dict(), indent=2 if pretty else None)

    @classmethod
    def from_dict(cls, d: dict) -> "JsonSerializable":
        # Remove 'include' if present
        d = dict(d)
        # all key snake_case to lower case with underscores
        d.pop("include", None)
        d = {snake_case(k): v for k, v in d.items()}

        # filter keys to only those in the dataclass
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        # logging.info(f"Creating ServerConfig from dict with keys: {list(d.keys())}")

        return cls(**{k: v for k, v in d.items() if k in valid_keys})


@dataclass
class EnvironmentSettable:
    @classmethod
    def from_env(cls):
        """Load configuration from environment variables if set."""
        instance = cls()

        for field_name in cls._field_names_list():
            env_var = f"{cls._env_var_prefix()}{field_name.upper()}"
            if env_var in os.environ:
                attr_type = cls.__dataclass_fields__[field_name].type
                if attr_type == bool:
                    setattr(instance, field_name, os.environ[env_var].lower() in ("1", "true", "yes", "on"))
                elif is_primitive(attr_type):
                    setattr(instance, field_name, attr_type(os.environ[env_var]))
                else:
                    setattr(instance, field_name, json.loads(os.environ[env_var]))

        for f_set in cls._field_settable():
            assert f_set.type and hasattr(f_set.type, "from_env")
            setattr(instance, f_set.name, f_set.type.from_env())

        return instance

    @classmethod
    def list_env_vars(cls):
        """List relevant environment variables for this config."""

        res = [cls._field_to_env_var(field_name=field_name) for field_name in cls._field_names_list()]
        for f_set in cls._field_settable():
            res.extend(f_set.type.list_env_vars())
        return res

    @classmethod
    def _field_names_list(cls):
        # only for str, int, float, bool or enum types. List and dict are included but will be set as json str in env
        return [
            field_name
            for field_name in cls.__dataclass_fields__.keys()
            if is_primitive(cls.__dataclass_fields__[field_name].type)
            or cls._is_list_or_dict_type(cls.__dataclass_fields__[field_name].type)
        ]

    @classmethod
    def _is_list_or_dict_type(cls, field_type):
        """Check if a field type is list, dict, or their typing equivalents (List[T], Dict[K, V], etc.)"""
        # Check for basic list/dict types
        if field_type in [list, dict]:
            return True

        # Check for typing annotations like List[str], Dict[str, int], etc.
        origin = get_origin(field_type)
        if origin in [list, dict]:
            return True

        return False

    @classmethod
    def _field_settable(cls) -> list[Field]:
        settable_fields = []
        for field_name in cls.__dataclass_fields__.keys():
            field_type = cls.__dataclass_fields__[field_name].type
            if hasattr(field_type, "__mro__") and EnvironmentSettable in field_type.__mro__:
                settable_fields.append(cls.__dataclass_fields__[field_name])
        return settable_fields

    @classmethod
    def _env_var_prefix(cls) -> str:
        # removing Config or AuthConfig suffixes from class name
        return re.sub(r"(Config|AuthConfig)$", "", cls.__name__).upper() + "_"
        # return snake_case(cls.__name__).replace("_auth_config", "").upper().replace("config", "").upper() + "_"

    @classmethod
    def _field_to_env_var(cls, field_name: str) -> str:
        return f"{cls._env_var_prefix()}{field_name.upper()}"

    def to_dotenv(self, keep_empty: bool = False) -> str:
        """Convert the dataclass to a dotenv formatted string."""
        lines = []
        for field_name in self._field_names_list():
            value = getattr(self, field_name)
            if value is not None and (keep_empty or value != ""):
                if is_enum(type(value)):
                    value = value.value
                lines.append(
                    f"{self._field_to_env_var(field_name)}={value if is_primitive(type(value)) else json.dumps(value)}"
                )
        for f_set in self._field_settable():
            nested_instance = getattr(self, f_set.name)
            if nested_instance is not None and hasattr(nested_instance, "to_dotenv"):
                lines.append(nested_instance.to_dotenv(keep_empty=keep_empty))
        return "\n".join(lines)


@dataclass
class AuthConfig(JsonSerializable, ABC, EnvironmentSettable):
    cached_token: str = field(default="", metadata={"description": "Cached authentication token"})
    token_expires_at: float = field(default=0.0, metadata={"description": "Token expiration time (epoch time)"})

    # @classmethod
    # def from_env(cls):
    #     """Load configuration from environment variables if set."""
    #     for field_name in cls.__dataclass_fields__:
    #         env_var = f"{cls._env_var_prefix()}{field_name.upper()}"
    #         if env_var in os.environ:
    #             setattr(cls, field_name, os.environ[env_var])

    #     # also add parent class fields
    #     for field_name in AuthConfig.__dataclass_fields__:
    #         env_var = f"{AuthConfig._env_var_prefix()}{field_name.upper()}"
    #         if env_var in os.environ:
    #             setattr(cls, field_name, os.environ[env_var])

    # @classmethod
    # def list_env_vars(cls):
    #     """List relevant environment variables for this config."""
    #     fields = cls.__dataclass_fields__
    #     if len(fields) != len(AuthConfig.__dataclass_fields__):
    #         # remove keys from parent class
    #         parent_fields = AuthConfig.__dataclass_fields__
    #         fields = [f for f in fields if f not in parent_fields]
    #     return [cls._field_to_env_var(field_name=field_name) for field_name in fields]

    # @classmethod
    # def _env_var_prefix(cls) -> str:
    #     # removing Config or AuthConfig suffixes from class name
    #     return re.sub(r"(Config|AuthConfig)$", "", cls.__name__).upper() + "_"
    #     # return snake_case(cls.__name__).replace("_auth_config", "").upper().replace("config", "").upper() + "_"

    # @classmethod
    # def _field_to_env_var(cls, field_name: str) -> str:
    #     return f"{cls._env_var_prefix()}{field_name.upper()}"


@dataclass
class BasicAuthConfig(AuthConfig):
    """
    Configuration for HTTP Basic Authentication.
    Stores username and password for basic auth scenarios.
    """

    username: str = field(default="", metadata={"description": "Username for basic authentication"})
    password: str = field(default="", metadata={"description": "Password for basic authentication"})

    def to_dict(self) -> dict:
        return {
            "username": self.username,
            "password": self.password,
        }


@dataclass
class OAuth2Config(AuthConfig):
    """
    Configuration for OAuth2 authentication.
    Stores client credentials and optional refresh token, token URL, and scope.
    Used for generic OAuth2 flows.
    """

    client_id: str = field(default="", metadata={"description": "OAuth2 client ID"})
    client_secret: str = field(default="", metadata={"description": "OAuth2 client secret"})
    refresh_token: str = field(default="", metadata={"description": "OAuth2 refresh token (optional)"})

    def to_dict(self) -> dict:
        return {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

    token_url: str = field(default="", metadata={"description": "OAuth2 token endpoint URL"})
    scope: str = field(default="", metadata={"description": "OAuth2 scopes (space-separated)"})


@dataclass
class AzureADConfig(AuthConfig):
    """
    Configuration for Azure Active Directory authentication.
    Stores tenant ID, client credentials, and scope for Azure AD OAuth2 flows.
    """

    tenant_id: str = field(default="", metadata={"description": "Azure AD tenant ID"})
    client_id: str = field(default="", metadata={"description": "Azure AD application (client) ID"})
    client_secret: str = field(default="", metadata={"description": "Azure AD client secret"})
    scope: str = field(default="", metadata={"description": "Azure AD scopes (space-separated)"})

    def to_dict(self) -> dict:
        return {
            "tenant_id": self.tenant_id,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": self.scope,
        }


@dataclass
class AWSCognitoConfig(AuthConfig):
    """
    Configuration for AWS Cognito authentication.
    Stores user pool, app client, region, and user credentials for AWS Cognito flows.
    """

    user_pool_id: str = field(default="", metadata={"description": "AWS Cognito user pool ID"})
    app_client_id: str = field(default="", metadata={"description": "AWS Cognito app client ID"})
    client_secret: str = field(default="", metadata={"description": "AWS Cognito app client secret"})
    aws_region: str = field(default="", metadata={"description": "AWS region for Cognito"})
    username: str = field(default="", metadata={"description": "Cognito username"})
    password: str = field(default="", metadata={"description": "Cognito password"})
    refresh_token: str = field(default="", metadata={"description": "Cognito refresh token (optional)"})

    def to_dict(self) -> dict:
        return {
            "user_pool_id": self.user_pool_id,
            "app_client_id": self.app_client_id,
            "client_secret": self.client_secret,
            "aws_region": self.aws_region,
            "username": self.username,
            "password": self.password,
        }


@dataclass
class GCPOAuthConfig(AuthConfig):
    """
    Configuration for Google Cloud Platform OAuth authentication.
    Stores project ID, service account key, and scope for GCP OAuth2 flows.
    """

    gcp_project_id: str = field(default="", metadata={"description": "GCP project ID"})
    service_account_key: str = field(
        default="", metadata={"description": "GCP service account key (JSON string or file path)"}
    )
    scope: str = field(default="", metadata={"description": "GCP OAuth2 scopes (space-separated)"})

    def to_dict(self) -> dict:
        return {
            "gcp_project_id": self.gcp_project_id,
            "service_account_key": self.service_account_key,
            "scope": self.scope,
        }


@dataclass
class BearerTokenConfig(AuthConfig):
    """
    Configuration for Bearer Token authentication.
    Used when a static or pre-fetched bearer token is provided directly.
    """

    def to_dict(self) -> dict:
        return {
            "bearer_token": self.cached_token,
        }


@dataclass
class AuthConfigs(JsonSerializable, EnvironmentSettable):
    auth_method: AuthMethod = AuthMethod.BASIC
    basic: BasicAuthConfig = field(default_factory=BasicAuthConfig)
    oauth2: OAuth2Config = field(default_factory=OAuth2Config)
    azure_ad: AzureADConfig = field(default_factory=AzureADConfig)
    aws_cognito: AWSCognitoConfig = field(default_factory=AWSCognitoConfig)
    gcp_oauth: GCPOAuthConfig = field(default_factory=GCPOAuthConfig)
    bearer_token: BearerTokenConfig = field(default_factory=BearerTokenConfig)

    def __post_init__(self):
        # logging.debug(f"AuthConfigs initialized with method: {self.auth_method}")
        if isinstance(self.basic, dict):
            self.basic = BasicAuthConfig.from_dict(self.basic)  # type: ignore
        if isinstance(self.oauth2, dict):
            self.oauth2 = OAuth2Config.from_dict(self.oauth2)  # type: ignore
        if isinstance(self.azure_ad, dict):
            self.azure_ad = AzureADConfig.from_dict(self.azure_ad)  # type: ignore
        if isinstance(self.aws_cognito, dict):
            self.aws_cognito = AWSCognitoConfig.from_dict(self.aws_cognito)  # type: ignore
        if isinstance(self.gcp_oauth, dict):
            self.gcp_oauth = GCPOAuthConfig.from_dict(self.gcp_oauth)  # type: ignore
        if isinstance(self.bearer_token, dict):
            self.bearer_token = BearerTokenConfig.from_dict(self.bearer_token)  # type: ignore

        if not isinstance(self.auth_method, AuthMethod):
            self.auth_method = AuthMethod(self.auth_method)  # type: ignore

        # logging.debug(
        #     f"AuthConfigs details: {self.basic}, {self.oauth2}, {self.azure_ad}, {self.aws_cognito}, {self.gcp_oauth}, {self.bearer_token}"
        # )

    def get_active_config(self) -> AuthConfig:
        if self.auth_method == AuthMethod.BASIC:
            return self.basic
        elif self.auth_method == AuthMethod.OAUTH2:
            return self.oauth2
        elif self.auth_method == AuthMethod.AZURE_AD:
            return self.azure_ad
        elif self.auth_method == AuthMethod.AWS_COGNITO:
            return self.aws_cognito
        elif self.auth_method == AuthMethod.GCP_OAUTH:
            return self.gcp_oauth
        elif self.auth_method == AuthMethod.BEARER_TOKEN:
            return self.bearer_token
        else:
            raise ValueError(f"Unsupported auth method: {self.auth_method}")

    def to_dict(self) -> dict:
        return {
            "auth_method": self.auth_method.value if self.auth_method is not None else None,
            "basic": self.basic.to_dict() if self.basic is not None else None,
            "oauth2": self.oauth2.to_dict() if self.oauth2 is not None else None,
            "azure_ad": self.azure_ad.to_dict() if self.azure_ad is not None else None,
            "aws_cognito": self.aws_cognito.to_dict() if self.aws_cognito is not None else None,
            "gcp_oauth": self.gcp_oauth.to_dict() if self.gcp_oauth is not None else None,
            "bearer_token": self.bearer_token.to_dict() if self.bearer_token is not None else None,
        }


class TokenManager:
    """Manages authentication tokens for various auth methods."""

    def __init__(self):
        self.session = requests.Session()

    def get_token(self, config: AuthConfigs) -> Optional[str]:
        """Get authentication token based on the configured method."""
        if config.auth_method == AuthMethod.BASIC:
            return self._get_basic_auth_token(config.basic)
        elif config.auth_method == AuthMethod.OAUTH2:
            return self._get_oauth2_token(config.oauth2)
        elif config.auth_method == AuthMethod.AZURE_AD:
            return self._get_azure_ad_token(config.azure_ad)
        elif config.auth_method == AuthMethod.AWS_COGNITO:
            return self._get_aws_cognito_token(config.aws_cognito)
        elif config.auth_method == AuthMethod.GCP_OAUTH:
            return self._get_gcp_oauth_token(config.gcp_oauth)
        elif config.auth_method == AuthMethod.BEARER_TOKEN:
            return config.bearer_token.cached_token
        elif config.auth_method == AuthMethod.NONE:
            return None
        else:
            raise ValueError(f"Unsupported auth method: {config.auth_method}")

    def is_token_valid(self, config: AuthConfigs) -> bool:
        """Check if the cached token is still valid."""
        cfg = config.get_active_config()
        if not cfg.cached_token:
            return False

        if cfg.token_expires_at == 0.0:
            return True  # Token doesn't expire (e.g., basic auth)

        # Check if token expires in next 30 seconds (buffer)
        return time.time() < (cfg.token_expires_at - 30)

    def refresh_token_if_needed(self, config: AuthConfigs) -> Optional[str]:
        """Refresh token if needed and return current valid token."""
        if self.is_token_valid(config):
            return config.get_active_config().cached_token

        return self.get_token(config)

    def _get_basic_auth_token(self, config: BasicAuthConfig) -> Optional[str]:
        """Generate basic authentication token."""
        if not config.username or not config.password:
            return None

        credentials = f"{config.username}:{config.password}"
        encoded_credentials = base64.b64encode(credentials.encode("utf-8")).decode("utf-8")
        token = f"Basic {encoded_credentials}"

        # Cache the token (basic auth doesn't expire)
        config.cached_token = token
        config.token_expires_at = 0.0

        return token

    def _get_oauth2_token(self, config: OAuth2Config) -> Optional[str]:
        """Get OAuth2 token using client credentials flow."""
        if not all([config.client_id, config.client_secret, config.token_url]):
            return None
        logging.info("Requesting OAuth2 token from %s", config)
        try:
            # Prepare token request
            data = {
                "grant_type": "client_credentials",
                "client_id": config.client_id,
                "client_secret": config.client_secret,
            }

            if config.scope:
                data["scope"] = config.scope

            headers = {"Content-Type": "application/x-www-form-urlencoded"}

            response = self.session.post(config.token_url, data=data, headers=headers, timeout=30)
            response.raise_for_status()

            token_data = response.json()
            access_token = token_data.get("access_token")

            if access_token:
                token = f"Bearer {access_token}"

                # Cache token with expiration
                config.cached_token = token
                expires_in = token_data.get("expires_in", 3600)
                config.token_expires_at = time.time() + expires_in

                # Store refresh token if available
                if "refresh_token" in token_data:
                    config.refresh_token = token_data["refresh_token"]

                return token

        except Exception as e:
            print(f"OAuth2 token request failed: {e}")

        return None

    def _get_azure_ad_token(self, config: AzureADConfig) -> Optional[str]:
        """Get Azure AD token using client credentials flow."""

        if not all([config.tenant_id, config.client_id, config.client_secret]):
            missing_fields = [
                field
                for field, value in {
                    "tenant_id": config.tenant_id,
                    "client_id": config.client_id,
                    "client_secret": config.client_secret,
                }.items()
                if not value
            ]
            msg = f"Azure AD config missing required fields: {', '.join(missing_fields)}"
            logging.error(msg)
            raise AzureADError(msg, "configuration_error", {})

        try:
            # Azure AD token endpoint
            token_url = f"https://login.microsoftonline.com/{config.tenant_id}" "/oauth2/v2.0/token"

            # Use configured scope or fall back to default
            scope = config.scope
            if scope:
                logging.info("Using configured Azure AD scope: %s", scope)
            else:
                logging.warning("No scope configured, using default scope")

            # logging.debug(
            #     "Requesting Azure AD token for client %s with scope %s",
            #     config.client_id,
            #     scope,
            # )

            data = {
                "grant_type": "client_credentials",
                "client_id": config.client_id,
                "client_secret": config.client_secret,
                "scope": scope,
            }

            headers = {"Content-Type": "application/x-www-form-urlencoded"}

            response = self.session.post(token_url, data=data, headers=headers, timeout=30)

            try:
                response.raise_for_status()
            except requests.exceptions.HTTPError as http_err:
                try:
                    response_data = response.json()
                except ValueError:
                    response_data = {
                        "error": "unknown_error",
                        "error_description": str(http_err),
                    }

                error_code = response_data.get("error", "unknown_error")
                error_desc = response_data.get("error_description", str(http_err))

                logging.error(
                    "Azure AD token request failed (%s): %s - %s",
                    response.status_code,
                    error_code,
                    error_desc,
                )

                # Enhance error data
                response_data["http_status"] = str(response.status_code)
                response_data["request_url"] = token_url
                response_data["timestamp"] = datetime.now().isoformat()

                msg = f"Azure AD auth failed (HTTP {response.status_code})"
                raise AzureADError(msg, error_code, response_data) from http_err

            token_data = response.json()
            access_token = token_data.get("access_token")

            if access_token:
                token = f"Bearer {access_token}"

                # Cache token with expiration
                config.cached_token = token
                expires_in = token_data.get("expires_in", 3600)
                config.token_expires_at = time.time() + expires_in

                # logging.debug(f"Azure AD token obtained successfully, expires in {expires_in} seconds")
                return token
            # else:
            # logging.debug("Azure AD token response missing access_token")

        except Exception as e:
            logging.debug(f"Azure AD token request failed: {e}")
            import traceback

            traceback.print_exc()

        return None

    def _get_aws_cognito_token(self, config: AWSCognitoConfig) -> Optional[str]:
        """Get AWS Cognito token."""
        if not all(
            [
                config.aws_region,
                config.user_pool_id,
                config.app_client_id,
                config.username,
                config.password,
            ]
        ):
            return None

        try:
            import boto3
            import hmac
            import hashlib
            from botocore.exceptions import ClientError

            client = boto3.client("cognito-idp", region_name=config.aws_region)

            # Prepare auth parameters
            auth_parameters = {
                "USERNAME": config.username,
                "PASSWORD": config.password,
            }

            # If client secret is provided, compute SECRET_HASH
            if config.client_secret:
                # SECRET_HASH = Base64(HMAC_SHA256(Username + ClientId, ClientSecret))
                message = config.username + config.app_client_id
                secret_hash = base64.b64encode(
                    hmac.new(config.client_secret.encode(), message.encode(), hashlib.sha256).digest()
                ).decode()
                auth_parameters["SECRET_HASH"] = secret_hash

            # Initiate auth
            response = client.initiate_auth(
                ClientId=config.app_client_id,
                AuthFlow="USER_PASSWORD_AUTH",
                AuthParameters=auth_parameters,
            )

            if "AuthenticationResult" in response:
                auth_result = response["AuthenticationResult"]
                access_token = auth_result.get("AccessToken")

                if access_token:
                    token = f"Bearer {access_token}"

                    # Cache token with expiration
                    config.cached_token = token
                    expires_in = auth_result.get("ExpiresIn", 3600)
                    config.token_expires_at = time.time() + expires_in

                    # Store refresh token
                    if "RefreshToken" in auth_result:
                        config.refresh_token = auth_result["RefreshToken"]

                    return token

        except ImportError:
            logging.error("boto3 not available for AWS Cognito authentication")
        except Exception as e:
            logging.error(f"AWS Cognito token request failed: {e}")

        return None

    def _get_gcp_oauth_token(self, config: GCPOAuthConfig) -> Optional[str]:
        """Get GCP OAuth token using service account."""
        if not all([config.gcp_project_id, config.service_account_key]):
            return None

        try:
            # This is a simplified implementation
            # In practice, you'd use google-auth library
            from google.auth.transport.requests import Request
            from google.oauth2 import service_account

            # Parse service account key
            if config.service_account_key.startswith("{"):
                # JSON string
                key_data = json.loads(config.service_account_key)
            else:
                # File path
                with open(config.service_account_key, "r") as f:
                    key_data = json.load(f)

            # Create credentials
            credentials = service_account.Credentials.from_service_account_info(
                key_data,
                scopes=([config.scope] if config.scope else ["https://www.googleapis.com/auth/cloud-platform"]),
            )

            # Refresh token
            credentials.refresh(Request())

            if credentials.token:
                token = f"Bearer {credentials.token}"

                # Cache token with expiration
                config.cached_token = token
                if credentials.expiry:
                    config.token_expires_at = credentials.expiry.timestamp()

                return token

        except ImportError:
            logging.error("google-auth not available for GCP authentication")
        except Exception as e:
            logging.error(f"GCP OAuth token request failed: {e}")

        return None

    def test_connection(self, config: AuthConfigs, test_url: str = None) -> tuple[bool, str]:
        """Test authentication by attempting to get a token."""
        try:
            token = self.get_token(config)
            if not token:
                return False, "Failed to obtain authentication token"

            # Optionally test the token against a URL
            if test_url:
                headers = {"Authorization": token}
                response = self.session.get(test_url, headers=headers, timeout=10)
                if response.status_code == 401:
                    return False, "Token authentication failed (401 Unauthorized)"
                elif response.status_code == 403:
                    return False, "Token authentication failed (403 Forbidden)"

            return True, "Authentication successful"

        except Exception as e:
            return False, f"Authentication test failed: {str(e)}"


def _gen_markdown_table_for_env_variables(a_class: type = AuthConfig) -> str:
    """Generate a markdown table listing all environment variables for all AuthConfig subclasses."""

    lines = []
    lines.append("| Class | Environment Variable | Description |")
    lines.append("|-------|----------------------|-------------|")

    for cls in a_class.__subclasses__():
        for field_name, field_obj in cls.__dataclass_fields__.items():
            # Skip parent class fields that are common to all (except for BearerTokenConfig where cached_token is relevant)
            if field_name in ["cached_token", "token_expires_at"] and cls.__name__ != "BearerTokenConfig":
                continue

            env_var = f"{cls._env_var_prefix()}{field_name.upper()}"

            # Get description from field metadata
            description = field_obj.metadata.get("description", f"Configuration field for {field_name}")

            lines.append(f"| {cls.__name__} | `{env_var}` | {description} |")

    return "\n".join(lines)


if __name__ == "__main__":
    import dotenv

    dotenv.load_dotenv(".env")
    logging.basicConfig(level=logging.DEBUG)
    # Example usage

    # print(_gen_markdown_table_for_env_variables(AuthConfig))
    from py_etp_client.etpconfig import ServerConfig

    print(_gen_markdown_table_for_env_variables(ServerConfig))
    # print(AuthConfigs.list_env_vars())
    # print(AuthConfigs._field_settable())

    # print(AuthConfigs.from_env().to_json())

    # print(AuthConfigs.list_env_vars())

    # print(AuthMethod("azure_ad"))
    # print(AuthMethod("azure"))
