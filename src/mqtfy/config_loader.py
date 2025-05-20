# config_loader.py

import requests
from pathlib import Path
from importlib.metadata import version, PackageNotFoundError


def get_version():
    project_version = version("mqtfy")
    return f"v{project_version}"

def download_config_from_github(tag_version):
    """
    Downloads config.yaml from a GitHub repository (based on the version in pyproject.toml),
    if the file is not already present locally.
    """

    config_filename="config.yaml.example"
    new_filename = config_filename.replace(".example", "")

    target_path = Path(new_filename)

    url = f"https://raw.githubusercontent.com/freakern/MQtfy/{tag_version}/{config_filename}"

    print(f"Attempting to download {new_filename} from {url}...")

    response = requests.get(url)
    if response.status_code == 200:
        target_path.write_bytes(response.content)
        print(f"{new_filename} successfully downloaded.")
    else:
        raise RuntimeError(f"Download failed: {response.status_code} - {response.text}")
