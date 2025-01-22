#!/usr/bin/env python3
"""
MyWhoosh to Garmin FIT file processor with multiple source support.

Supports local file system and Strava sources. Processes FIT files to add
missing metrics and uploads to Garmin Connect.
"""

import argparse
import importlib
import json
import logging
import os
import re
import subprocess
import sys
import tkinter as tk
from datetime import datetime
from getpass import getpass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import garth
from fit_tool.fit_file import FitFile
from fit_tool.fit_file_builder import FitFileBuilder
from fit_tool.profile.messages.file_creator_message import FileCreatorMessage
from fit_tool.profile.messages.lap_message import LapMessage
from fit_tool.profile.messages.record_message import (
    RecordMessage,
    RecordTemperatureField,
)
from fit_tool.profile.messages.session_message import SessionMessage
from garth.exc import GarthException, GarthHTTPError
from pydantic import BaseModel, ValidationError, FilePath, DirectoryPath
from tkinter import filedialog

from pydantic_settings import BaseSettings

# Constants
SCRIPT_DIR = Path(__file__).resolve().parent
MYWHOOSH_PREFIX_WINDOWS = "MyWhooshTechnologyService."
FILE_DIALOG_TITLE = "MyWhoosh2Garmin"
DEFAULT_CHUNK_SIZE = 4096
MAX_RETRIES = 3
RETRY_DELAY = 1  # Second


class BackupConfig(BaseModel):
    """Pydantic model for backup directory configuration."""
    backup_path: DirectoryPath


class GarminCredentials(BaseModel):
    """Pydantic model for Garmin login credentials."""
    username: str
    password: str


class Settings(BaseSettings):
    """Application settings loaded from environment or defaults."""
    tokens_path: Path = SCRIPT_DIR / ".garth"
    log_path: Path = SCRIPT_DIR / "myWhoosh2Garmin.log"
    json_config_path: Path = SCRIPT_DIR / "backup_path.json"
    installed_packages_file: Path = SCRIPT_DIR / "installed_packages.json"

    class Config:
        """Pydantic config for settings."""
        env_file = ".env"
        env_file_encoding = "utf-8"


def configure_logging(log_path: Path) -> logging.Logger:
    """
    Configure application logging.

    Args:
        log_path: Path to log file

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s"
    )

    file_handler = logging.FileHandler(log_path)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


class PackageManager:
    """Handles Python package dependencies and installations."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.installed_packages = self._load_installed_packages()

    def _load_installed_packages(self) -> set:
        """Load tracked installed packages from JSON file."""
        if self.settings.installed_packages_file.exists():
            with open(self.settings.installed_packages_file, "r") as f:
                return set(json.load(f))
        return set()

    def _save_installed_packages(self) -> None:
        """Save tracked installed packages to JSON file."""
        with open(self.settings.installed_packages_file, "w") as f:
            json.dump(list(self.installed_packages), f)

    @staticmethod
    def _get_pip_command() -> Optional[List[str]]:
        """Get valid pip command for current environment."""
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "--version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            return [sys.executable, "-m", "pip"]
        except subprocess.CalledProcessError:
            return None

    def ensure_packages(self, required_packages: List[str]) -> None:
        """
        Ensure required packages are installed.

        Args:
            required_packages: List of package names to verify

        Raises:
            RuntimeError: If package installation fails
        """
        for package in required_packages:
            if package in self.installed_packages:
                continue

            if not importlib.util.find_spec(package):
                self._install_package(package)

            try:
                __import__(package)
                self.installed_packages.add(package)
            except ModuleNotFoundError:
                raise RuntimeError(
                    f"Failed to import {package} after installation"
                )

        self._save_installed_packages()

    def _install_package(self, package: str) -> None:
        """Install a Python package using pip."""
        pip_command = self._get_pip_command()
        if pip_command:
            try:
                subprocess.check_call(pip_command + ["install", package])
            except subprocess.CalledProcessError as e:
                raise RuntimeError(f"Error installing {package}: {e}")
        else:
            raise RuntimeError("pip not available")


class GarminAuthenticator:
    """Handles Garmin Connect authentication using Garth library."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.garth = garth

    def authenticate(
            self,
            credentials: Optional[GarminCredentials] = None
    ) -> None:
        """
        Authenticate with Garmin Connect.

        Args:
            credentials: Optional credentials for new authentication

        Raises:
            RuntimeError: If authentication fails
        """
        try:
            if self._try_resume_session():
                return
            if credentials:
                self._full_authentication(credentials)
        except GarthException as e:
            raise RuntimeError(f"Authentication failed: {e}")

    def _try_resume_session(self) -> bool:
        """Attempt to resume existing session from saved tokens."""
        if self.settings.tokens_path.exists():
            self.garth.resume(self.settings.tokens_path)
            try:
                logger.info(f"Authenticated as: {self.garth.client.username}")
                return True
            except GarthException:
                logger.info("Session expired")
        return False

    def _full_authentication(self, credentials: GarminCredentials) -> None:
        """Perform full authentication with username/password."""
        try:
            self.garth.login(credentials.username, credentials.password)
            self.garth.save(self.settings.tokens_path)
            logger.info("Authentication successful")
        except GarthHTTPError:
            raise RuntimeError("Invalid credentials")


class FitFileProcessor:
    """Processes FIT files to add metrics and clean up data."""

    def __init__(self, backup_config: BackupConfig):
        self.backup_config = backup_config

    @staticmethod
    def calculate_avg(values: List[float]) -> float:
        """
        Calculate average of values list.

        Args:
            values: List of numerical values

        Returns:
            Average value or 0 for empty list
        """
        return sum(values) / len(values) if values else 0

    def process_file(self, fit_file_path: Path) -> Path:
        """
        Process a FIT file and save cleaned version.

        Args:
            fit_file_path: Path to input FIT file

        Returns:
            Path to processed FIT file
        """
        builder = FitFileBuilder()
        fit_file = FitFile.from_file(str(fit_file_path))
        cadence, power, hr = [], [], []

        for record in fit_file.records:
            message = record.message
            if isinstance(message, RecordMessage):
                self._process_record_message(message, cadence, power, hr)
            elif isinstance(message, SessionMessage):
                self._process_session_message(message, cadence, power, hr)
                cadence, power, hr = [], [], []

            builder.add(message)

        return self._save_processed_file(builder, fit_file_path)

    def _process_record_message(
            self,
            message: RecordMessage,
            cadence: List[float],
            power: List[float],
            hr: List[float]
    ) -> None:
        """Process individual record messages."""
        message.remove_field(RecordTemperatureField.ID)
        cadence.append(message.cadence or 0)
        power.append(message.power or 0)
        hr.append(message.heart_rate or 0)

    def _process_session_message(
            self,
            message: SessionMessage,
            cadence: List[float],
            power: List[float],
            hr: List[float]
    ) -> None:
        """Add calculated averages to session messages."""
        if not message.avg_cadence:
            message.avg_cadence = self.calculate_avg(cadence)
        if not message.avg_power:
            message.avg_power = self.calculate_avg(power)
        if not message.avg_heart_rate:
            message.avg_heart_rate = self.calculate_avg(hr)

    def _save_processed_file(
            self,
            builder: FitFileBuilder,
            original_path: Path
    ) -> Path:
        """
        Save processed FIT file with timestamp.

        Args:
            builder: Configured FitFileBuilder
            original_path: Original file path for naming

        Returns:
            Path to saved file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        new_filename = f"{original_path.stem}_{timestamp}.fit"
        new_path = self.backup_config.backup_path / new_filename
        builder.build().to_file(str(new_path))
        return new_path


class SourceHandler:
    """Base class for different FIT file sources."""

    def get_fit_files(self) -> List[Path]:
        """Retrieve FIT files from source."""
        raise NotImplementedError

    def upload(self, file_path: Path) -> None:
        """Upload processed file to source."""
        raise NotImplementedError


class LocalSourceHandler(SourceHandler):
    """Handles local file system source."""

    def __init__(self, settings: Settings, backup_config: BackupConfig):
        self.settings = settings
        self.backup_config = backup_config
        self.fit_files_location = self._get_fitfile_location()

    def _get_fitfile_location(self) -> Path:
        """Get platform-specific FIT files directory."""
        if os.name == "posix":
            path = Path.home().joinpath(
                "Library/Containers/com.whoosh.whooshgame/Data",
                "Library/Application Support/Epic/MyWhoosh/Content/Data"
            )
        elif os.name == "nt":
            path = self._find_windows_path()
        else:
            raise RuntimeError("Unsupported OS")

        if not path.exists():
            raise FileNotFoundError(f"FIT files directory not found: {path}")
        return path

    def _find_windows_path(self) -> Path:
        """Find MyWhoosh directory on Windows."""
        base_path = Path.home() / "AppData/Local/Packages"
        for directory in base_path.iterdir():
            if directory.name.startswith(MYWHOOSH_PREFIX_WINDOWS):
                return directory / "LocalCache/Local/MyWhoosh/Content/Data"
        raise FileNotFoundError("MyWhoosh directory not found")

    def get_fit_files(self) -> List[Path]:
        """Get sorted list of FIT files from source."""
        return sorted(
            self.fit_files_location.glob("MyNewActivity-*.fit"),
            key=lambda f: tuple(map(int, re.findall(r"(\d+)", f.stem.split("-")[-1]))),
            reverse=True,
        )


class StravaSourceHandler(SourceHandler):
    """Handles Strava API source (skeleton implementation)."""

    def __init__(self, config: Dict):
        # TODO: Implement Strava API integration
        pass

    def get_fit_files(self) -> List[Path]:
        # TODO: Implement Strava file download
        return []


class UploadManager:
    """Manages file uploads to Garmin Connect."""

    def __init__(self, authenticator: GarminAuthenticator):
        self.authenticator = authenticator

    def upload_file(self, file_path: Path) -> None:
        """
        Upload file to Garmin Connect.

        Args:
            file_path: Path to file to upload

        Raises:
            GarthHTTPError: If upload fails
        """
        try:
            with open(file_path, "rb") as f:
                response = garth.client.upload(f)
                logger.info(f"Upload successful: {response}")
        except GarthHTTPError as e:
            logger.error(f"Upload failed: {e}")
            raise


def main() -> None:
    """Main application entry point."""
    settings = Settings()
    logger = configure_logging(settings.log_path)

    try:
        # Parse command line arguments
        parser = argparse.ArgumentParser(
            description="Upload workout data to Garmin Connect"
        )
        parser.add_argument(
            "--source",
            choices=["local", "strava"],
            default="local",
            help="Data source to use"
        )
        args = parser.parse_args()

        # Initialize dependencies
        PackageManager(settings).ensure_packages(["garth", "fit_tool"])

        # Load configuration
        backup_config = load_backup_config(settings.json_config_path)

        # Initialize source handler
        if args.source == "local":
            source_handler = LocalSourceHandler(settings, backup_config)
        else:
            source_handler = StravaSourceHandler({})

        # Process files
        fit_files = source_handler.get_fit_files()
        if not fit_files:
            logger.error("No FIT files found")
            return

        processor = FitFileProcessor(backup_config)
        processed_file = processor.process_file(fit_files[0])

        # Handle authentication
        authenticator = GarminAuthenticator(settings)
        try:
            authenticator.authenticate()
        except RuntimeError:
            credentials = prompt_credentials()
            authenticator.authenticate(credentials)

        # Upload processed file
        uploader = UploadManager(authenticator)
        uploader.upload_file(processed_file)

    except Exception as e:
        logger.error(f"Critical error: {e}")
        sys.exit(1)


def prompt_credentials() -> GarminCredentials:
    """Prompt user for Garmin credentials."""
    return GarminCredentials(
        username=input("Garmin username: "),
        password=getpass("Garmin password: "),
    )


def load_backup_config(config_path: Path) -> BackupConfig:
    """
    Load or create backup directory configuration.

    Args:
        config_path: Path to configuration file

    Returns:
        BackupConfig instance

    Raises:
        ValueError: If no directory selected
    """
    if config_path.exists():
        with open(config_path, "r") as f:
            return BackupConfig(**json.load(f))

    root = tk.Tk()
    root.withdraw()
    path = Path(filedialog.askdirectory(
        title=f"Select {FILE_DIALOG_TITLE} Directory"
    ))

    if not path:
        raise ValueError("No backup directory selected")

    with open(config_path, "w") as f:
        json.dump({"backup_path": str(path)}, f)

    return BackupConfig(backup_path=path)


if __name__ == "__main__":
    main()