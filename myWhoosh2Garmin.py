#!/usr/bin/env python3
"""
Script name: myWhoosh2Garmin.py
Usage: "python3 myWhoosh2Garmin.py"
Description:    Checks for MyNewActivity-<myWhooshVersion>.fit
                Adds avg power and heartrade
                Removes temperature
                Creates backup for the file with a timestamp as a suffix
Credits:        Garth by matin - for authenticating and uploading with Garmin Connect.
                https://github.com/matin/garth
                Fit_tool by mtucker - for parsing the fit file.
                https://bitbucket.org/stagescycling/python_fit_tool.git/src
                mw2gc by embeddedc - used as an example to fix the avg's. Helped a lot, thnx!
                https://github.com/embeddedc/mw2gc
"""
import os
import subprocess
import sys
import logging
from datetime import datetime
from getpass import getpass
from pathlib import Path
import importlib.util

def get_pip_command():
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return [sys.executable, "-m", "pip"]  # pip is available
    except subprocess.CalledProcessError:
        return None  # pip is not available

def install_package(package):
    pip_command = get_pip_command()
    if pip_command:
        try:
            print(f"Installing missing package: {package}")
            subprocess.check_call(pip_command + ["install", package], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as e:
            print(f"Error installing {package}: {e}")
    else:
        print("pip is not available. Unable to install packages.")

def ensure_packages():
    required_packages = [
        "garth",
        "fit_tool",
    ]
    for package in required_packages:
        if not importlib.util.find_spec(package):
            print(f"Installing missing package: {package}")
            install_package(package)


import garth
from garth.exc import GarthException, GarthHTTPError
from fit_tool.fit_file import FitFile
from fit_tool.fit_file_builder import FitFileBuilder
from fit_tool.profile.messages.file_creator_message import FileCreatorMessage
from fit_tool.profile.messages.record_message import (
    RecordMessage,
    RecordTemperatureField
)
from fit_tool.profile.messages.session_message import SessionMessage
from fit_tool.profile.messages.lap_message import LapMessage

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
file_handler = logging.FileHandler('myWhoosh2Garmin.log')
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

TOKENS_PATH = Path(".garth")
BACKUP_FOLDER = Path("MyWhooshFitBackup")
DEFAULT_ACTIVITY_NAME = "MyWhoosh"

def get_fitfile_location() -> Path:
    if os.name == "posix":  # macOS and Linux
        target_path = (
            Path.home()
            / "Library"
            / "Containers"
            / "com.whoosh.whooshgame"
            / "Data"
            / "Library"
            / "Application Support"
            / "Epic"
            / "MyWhoosh"
            / "Content"
            / "Data"
         )
        if target_path.is_dir():
            return target_path
    # elif os.name == "Windows":  # Windows
    #     home = Path(os.getenv("USERPROFILE"))
    #     target_dir = "MyWhooshTechnologyService.MyWhoosh_"
    #     for directory in home.iterdir():
    #         target_path = directory / target_dir
    #         if target_path.exists():
    #             return target_path
    else:
        raise RuntimeError("Unsupported operating system")


FITFILE_LOCATION = get_fitfile_location()


def get_credentials_for_garmin():
    username = input("Username: ")
    password = getpass("Password: ")
    logger.info("Authenticating...")
    try:
        garth.login(username, password)
        garth.save(".garth")
        logger.info("Successfully authenticated!")
    except GarthHTTPError:
        logger.info("Wrong credentials. Please check username and password.")
        sys.exit(1)


def authenticate_to_garmin():
    try:
        if TOKENS_PATH.exists():
            # Resume session if tokens file exists
            garth.resume(".garth")
            try:
                # Verify if the session is still valid
                logger.info(f"Authenticated as: {garth.client.username}")
            except GarthException:
                logger.info("Session expired. Re-authenticating...")
                get_credentials_for_garmin()
        else:
            # No session tokens; ask for credentials
            logger.info("No existing session. Please log in.")
            get_credentials_for_garmin()
    except GarthException as e:
        logger.info(f"Authentication error: {e}")
        sys.exit(1)


# Cleanup the FIT file and save it as a new file with "<timestamp>" suffix
def cleanup_fit_file(fit_file_path: Path, new_file_path: Path) -> None:
    builder = FitFileBuilder()
    fit_file = FitFile.from_file(str(fit_file_path))
    cadence_values = []
    power_values = []
    heart_rate_values = []

    # Process the records
    for record in fit_file.records:
        message = record.message
        # Skip invalid records based on type and remove unnecessary fields
        if isinstance(message, (FileCreatorMessage, LapMessage)):
            continue
        if isinstance(message, RecordMessage):
            message.remove_field(RecordTemperatureField.ID)  # Remove temperature field
            cadence_values.append(message.cadence if message.cadence else 0)
            power_values.append(message.power if message.power else 0)
            heart_rate_values.append(message.heart_rate if message.heart_rate else 0)
        if isinstance(message, SessionMessage):
            # Add average values if missing
            if not message.avg_cadence:
                message.avg_cadence = (
                    sum(cadence_values) / len(cadence_values)
                    if cadence_values
                    else 0
                )
            if not message.avg_power:
                message.avg_power = (
                    sum(power_values) / len(power_values)
                    if power_values
                    else 0
                )
            if not message.avg_heart_rate:
                message.avg_heart_rate = (
                    sum(heart_rate_values) / len(heart_rate_values)
                    if heart_rate_values
                    else 0
                )
            if not message.avg_power:
                message.avg_power = (
                    sum(power_values) / len(power_values)
                    if power_values
                    else 0
                )
            cadence_values = []
            power_values = []
            heart_rate_values = []
        builder.add(message)

    # Output the cleaned-up .fit file to the new file path (with timestamp suffix)
    out_file = builder.build()
    out_file.to_file(str(new_file_path))
    logger.info(f"Cleaned-up file saved as {new_file_path.name}")


# Cleanup the .fit file and save it with timestamp suffix
def cleanup_and_save_fit_file(fitfile_location: Path) -> Path:
    if fitfile_location.is_dir():
        logger.debug(f"Checking for .fit files in directory: {fitfile_location}")
        # Find all .fit files in the directory
        fit_files = list(fitfile_location.glob("*.fit"))
        if fit_files:
            logger.debug("Found the following .fit files:")
            # Get the most recent file. MyWhoosh creates a .fit file for every version they publish
            fit_file = max(fit_files, key=lambda f: f.stat().st_mtime)
            timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            # Generate the new filename with timestamp suffix
            new_filename = f"{fit_file.stem}_{timestamp}.fit"
            if not BACKUP_FOLDER.exists():
                BACKUP_FOLDER.mkdir()
            new_file_path = BACKUP_FOLDER / new_filename
            logger.info(f"Cleaning up {new_file_path}")
            try:
                cleanup_fit_file(fit_file, new_file_path)  # Clean and save with new filename
                logger.info(f"Successfully cleaned {fit_file.name} and saved the file as {new_file_path.name}.")
                return new_file_path
            except Exception as e:
                logger.error(f"Failed to process {fit_file.name}: {e}")
        else:
            logger.info("No .fit files found.")
            return Path()
    else:
        logger.info(f"The specified path is not a directory: {fitfile_location}")
        return Path()


def upload_fit_file_to_garmin(new_file_path: Path):
    try:
        if new_file_path and new_file_path.exists():
            with open(new_file_path, "rb") as f:
                uploaded = garth.client.upload(f)
                logger.debug(uploaded)
        else:
            logger.info(f"Invalid file path: {new_file_path}")
    except GarthHTTPError:
        logger.info("Duplicate activity found.")

def main():
    # Make sure packages are installed
    ensure_packages()
    authenticate_to_garmin()
    new_file_path = cleanup_and_save_fit_file(FITFILE_LOCATION)
    if new_file_path:
        upload_fit_file_to_garmin(new_file_path)

if __name__ == "__main__":
    main()