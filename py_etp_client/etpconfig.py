# Copyright (c) 2022-2023 Geosiris.
# SPDX-License-Identifier: Apache-2.0
from dotenv import load_dotenv
import os
import json
import yaml


class ETPConfig:
    # Load environment variables from .env file
    load_dotenv()

    # Access the environment variables

    PORT = os.getenv("PORT", "443")
    URL = os.getenv("URL")
    USERNAME = os.getenv("USERNAME")
    PASSWORD = os.getenv("PASSWORD")
    ADDITIONAL_HEADERS = os.getenv("ADDITIONAL_HEADERS")
    TOKEN = os.getenv("TOKEN")
    TOKEN_URL = os.getenv("TOKEN_URL")
    TOKEN_GRANT_TYPE = os.getenv("TOKEN_GRANT_TYPE")
    TOKEN_SCOPE = os.getenv("TOKEN_SCOPE")
    TOKEN_REFRESH_TOKEN = os.getenv("TOKEN_REFRESH_TOKEN")
    USE_REST = os.getenv("USE_REST", "false").lower() == "true"

    # Path to YAML file (from .env)
    INI_FILE_PATH = os.getenv("INI_FILE_PATH")

    def __init__(self):
        if self.INI_FILE_PATH:
            self.load_from_yml(self.INI_FILE_PATH)

    def load_from_yml(self, yml_file_path):
        """
        Load additional config from the YAML file and overwrite .env variables.
        """
        if os.path.exists(yml_file_path):
            with open(yml_file_path, "r") as yml_file:
                yml_config = yaml.safe_load(yml_file)
                for key, value in yml_config.items():
                    # Dynamically set attributes in the Config class
                    setattr(self, key, value)
        else:
            print(
                f"Warning: YAML file {yml_file_path} not found. Skipping YAML configuration."
            )

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
            "TOKEN": self.TOKEN,
            "TOKEN_URL": self.TOKEN_URL,
            "TOKEN_GRANT_TYPE": self.TOKEN_GRANT_TYPE,
            "TOKEN_SCOPE": self.TOKEN_SCOPE,
            "TOKEN_REFRESH_TOKEN": self.TOKEN_REFRESH_TOKEN,
            "USE_REST": self.USE_REST,
            "INI_FILE_PATH": self.INI_FILE_PATH,
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
