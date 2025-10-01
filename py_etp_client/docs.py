# Copyright (c) 2022-2023 Geosiris.
# SPDX-License-Identifier: Apache-2.0

"""
Documentation generation utilities for py-etp-client configuration classes.

This module provides functions to generate markdown documentation tables
for environment variables used by ServerConfig and AuthConfig subclasses.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from py_etp_client.auth import AuthConfig


def gen_serverconfig_env_vars_table():
    """Generate a markdown table listing all environment variables for ServerConfig."""
    from py_etp_client.etpconfig import ServerConfig

    lines = []
    lines.append("| Environment Variable | Description |")
    lines.append("|----------------------|-------------|")

    for field_name, field_obj in ServerConfig.__dataclass_fields__.items():
        # Skip inherited fields from parent classes that are already documented
        if field_name in [
            "cached_token",
            "token_expires_at",
            "auth_method",
            "basic",
            "oauth2",
            "azure_ad",
            "aws_cognito",
            "gcp_oauth",
            "bearer_token",
        ]:
            continue

        env_var = f"{ServerConfig._env_var_prefix()}{field_name.upper()}"
        description = field_obj.metadata.get("description", f"Configuration field for {field_name}")
        lines.append(f"| `{env_var}` | {description} |")

    return "\n".join(lines)


def gen_authconfig_env_vars_table(auth_class: "AuthConfig"):
    """Generate a markdown table listing all environment variables for a specific AuthConfig subclass."""

    lines = []
    lines.append("| Environment Variable | Description |")
    lines.append("|----------------------|-------------|")

    for field_name, field_obj in auth_class.__dataclass_fields__.items():
        # Skip parent class fields that are common to all (except for BearerTokenConfig where cached_token is relevant)
        if field_name in ["cached_token", "token_expires_at"] and auth_class.__name__ != "BearerTokenConfig":
            continue

        env_var = f"{auth_class._env_var_prefix()}{field_name.upper()}"
        description = field_obj.metadata.get("description", f"Configuration field for {field_name}")
        lines.append(f"| `{env_var}` | {description} |")

    return "\n".join(lines)


def gen_all_config_env_vars_tables():
    """Generate comprehensive markdown documentation for all configuration classes."""
    from py_etp_client.auth import (
        AuthConfig,
        BasicAuthConfig,
        OAuth2Config,
        AzureADConfig,
        AWSCognitoConfig,
        GCPOAuthConfig,
        BearerTokenConfig,
    )

    sections = []

    # ServerConfig section
    sections.append("# Configuration Environment Variables")
    sections.append("")
    sections.append("This document lists all environment variables that can be used to configure the ETP client.")
    sections.append("")

    sections.append("## Server Configuration")
    sections.append("")
    sections.append("These environment variables configure the ETP server connection and behavior:")
    sections.append("")
    sections.append(gen_serverconfig_env_vars_table())
    sections.append("")

    # AuthConfig sections
    auth_classes = [
        (BasicAuthConfig, "Basic Authentication", "Configure HTTP Basic Authentication credentials:"),
        (OAuth2Config, "OAuth2 Authentication", "Configure OAuth2 client credentials flow:"),
        (AzureADConfig, "Azure Active Directory Authentication", "Configure Azure AD authentication:"),
        (AWSCognitoConfig, "AWS Cognito Authentication", "Configure AWS Cognito authentication:"),
        (GCPOAuthConfig, "Google Cloud Platform Authentication", "Configure GCP OAuth2 authentication:"),
        (BearerTokenConfig, "Bearer Token Authentication", "Configure static bearer token authentication:"),
    ]

    for auth_class, title, description in auth_classes:
        sections.append(f"## {title}")
        sections.append("")
        sections.append(description)
        sections.append("")
        sections.append(gen_authconfig_env_vars_table(auth_class))
        sections.append("")

    # General usage section
    sections.append("## Usage")
    sections.append("")
    sections.append("### Setting Environment Variables")
    sections.append("")
    sections.append("You can set these environment variables in several ways:")
    sections.append("")
    sections.append("1. **System environment variables**:")
    sections.append("   ```bash")
    sections.append("   export SERVER_URL=wss://example.com/etp")
    sections.append("   export SERVER_TIMEOUT=60")
    sections.append("   ```")
    sections.append("")
    sections.append("2. **`.env` file** (recommended for development):")
    sections.append("   ```")
    sections.append("   SERVER_URL=wss://example.com/etp")
    sections.append("   SERVER_TIMEOUT=60")
    sections.append("   AZUREAD_TENANT_ID=your-tenant-id")
    sections.append("   AZUREAD_CLIENT_ID=your-client-id")
    sections.append("   ```")
    sections.append("")
    sections.append("3. **Programmatically**:")
    sections.append("   ```python")
    sections.append("   import os")
    sections.append("   os.environ['SERVER_URL'] = 'wss://example.com/etp'")
    sections.append("   ```")
    sections.append("")
    sections.append("### Loading from Environment")
    sections.append("")
    sections.append("```python")
    sections.append("from py_etp_client.etpconfig import ServerConfig")
    sections.append("")
    sections.append("# Load configuration from environment variables")
    sections.append("config = ServerConfig.from_env()")
    sections.append("```")
    sections.append("")
    sections.append("### Complex Data Types")
    sections.append("")
    sections.append("For list and dictionary fields, you can provide JSON strings:")
    sections.append("")
    sections.append("```bash")
    sections.append('export SERVER_SUPPORTED_DATA_OBJECTS=\'["resqml20.obj_Well", "resqml20.obj_WellboreGeometry"]\'')
    sections.append(
        'export SERVER_ADDITIONAL_HEADERS=\'{"data-partition-id": "opendes", "Authorization": "Bearer token"}\''
    )
    return "\n".join(sections)


def generate_config_documentation_file(output_path: str = "CONFIG_ENV_VARS.md"):
    """
    Generate a complete markdown documentation file for all configuration environment variables.

    Args:
        output_path: Path where to save the markdown file
    """
    content = gen_all_config_env_vars_tables()

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    return output_path


if __name__ == "__main__":
    # Test the functions
    print("Testing documentation generation functions...")

    # Test individual functions
    print("ServerConfig table:")
    print(gen_serverconfig_env_vars_table())
    print("\n" + "=" * 50 + "\n")

    from py_etp_client.auth import BasicAuthConfig, AzureADConfig

    print("BasicAuthConfig table:")
    print(gen_authconfig_env_vars_table(BasicAuthConfig))
    print("\n" + "=" * 50 + "\n")

    print("AzureADConfig table:")
    print(gen_authconfig_env_vars_table(AzureADConfig))
    print("\n" + "=" * 50 + "\n")

    # Generate complete documentation
    output_file = generate_config_documentation_file()
    print(f"Complete documentation saved to: {output_file}")
