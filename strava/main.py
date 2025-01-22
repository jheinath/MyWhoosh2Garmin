"""
Strava API client for downloading virtual ride activities with 'MyWhoosh' in their name.
Handles authentication, session management, and tracks downloaded activities in SQLite.
"""

import json
import os
import sqlite3
from datetime import datetime
from typing import List, Optional
from urllib.parse import parse_qs, urlparse

import requests
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from requests import Session


class StravaSettings(BaseSettings):
    """
    Application configuration settings loaded from environment variables and .env file.

    Attributes:
        client_id: Strava API client ID
        client_secret: Strava API client secret
        token_url: OAuth2 token endpoint URL
        auth_base_url: Authorization endpoint URL
        token_file: Path to store authentication tokens
        cookie_file: Path to browser cookies file
        activities_url: Strava API endpoint for athlete activities
        database_file: SQLite database file path
    """
    client_id: str = Field(..., validation_alias="CLIENT_ID")
    client_secret: str = Field(..., validation_alias="CLIENT_SECRET")
    token_url: str = "https://www.strava.com/oauth/token"
    auth_base_url: str = "https://www.strava.com/oauth/authorize"
    token_file: str = "strava_tokens.json"
    cookie_file: str = "cookie.json"
    activities_url: str = "https://www.strava.com/api/v3/athlete/activities"
    database_file: str = "strava.db"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class TokenData(BaseModel):
    """
    Represents OAuth2 token data with expiration handling.

    Attributes:
        access_token: Short-lived API access token
        refresh_token: Long-lived token for refreshing access
        expires_at: Token expiration timestamp
    """
    access_token: str
    refresh_token: str
    expires_at: datetime

    @classmethod
    def from_json(cls, data: dict) -> "TokenData":
        """Create TokenData instance from JSON response, converting timestamp."""
        if isinstance(data.get("expires_at"), int):
            data["expires_at"] = datetime.fromtimestamp(data["expires_at"])
        return cls(**data)


class ActivityDetails(BaseModel):
    """
    Represents essential activity details from Strava API.

    Attributes:
        id: Unique activity identifier
        name: Activity name
        start_date: Activity start time
        type: Activity type (e.g., VirtualRide)
    """
    id: int
    name: str
    start_date: datetime
    type: str


class ActivityDatabase:
    """Manages SQLite database for tracking downloaded activities."""

    def __init__(self, db_file: str) -> None:
        """Initialize database connection and create table if needed."""
        self.conn = sqlite3.connect(db_file)
        self._create_table()

    def _create_table(self) -> None:
        """Create the downloads tracking table if it doesn't exist."""
        query = """
        CREATE TABLE IF NOT EXISTS downloaded_activities (
            activity_id INTEGER PRIMARY KEY,
            downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        self.conn.execute(query)
        self.conn.commit()

    def is_downloaded(self, activity_id: int) -> bool:
        """Check if an activity has already been downloaded."""
        cursor = self.conn.execute(
            "SELECT 1 FROM downloaded_activities WHERE activity_id = ?",
            (activity_id,)
        )
        return bool(cursor.fetchone())

    def mark_downloaded(self, activity_id: int) -> None:
        """Record a downloaded activity in the database."""
        self.conn.execute(
            "INSERT OR IGNORE INTO downloaded_activities (activity_id) VALUES (?)",
            (activity_id,)
        )
        self.conn.commit()

    def close(self) -> None:
        """Close the database connection."""
        self.conn.close()


class StravaAuth:
    """Handles OAuth2 authentication flow and token management."""

    def __init__(self, settings: StravaSettings) -> None:
        """Initialize with application settings."""
        self.settings = settings
        self.token_data: Optional[TokenData] = None

    def authenticate(self) -> None:
        """Perform full authentication flow, using existing tokens if available."""
        if not self._load_tokens():
            self._perform_oauth_flow()

    def _perform_oauth_flow(self) -> None:
        """Execute the OAuth2 authorization code flow."""
        auth_url = (
            f"{self.settings.auth_base_url}?"
            f"client_id={self.settings.client_id}&"
            "response_type=code&"
            "redirect_uri=http://localhost/exchange_token&"
            "scope=activity:read_all"
        )
        print(f"🔗 Authorize here: {auth_url}")
        redirect_url = input("🔄 Paste callback URL: ")
        self._fetch_token(redirect_url)

    def _fetch_token(self, redirect_url: str) -> None:
        """Exchange authorization code for access token."""
        code = parse_qs(urlparse(redirect_url).query).get("code")
        if not code:
            raise ValueError("Authorization code missing")

        response = requests.post(
            self.settings.token_url,
            data={
                "client_id": self.settings.client_id,
                "client_secret": self.settings.client_secret,
                "code": code[0],
                "grant_type": "authorization_code",
            },
        )
        response.raise_for_status()
        self._save_tokens(response.json())

    def _save_tokens(self, token_data: dict) -> None:
        """Persist tokens to file and update current token data."""
        with open(self.settings.token_file, "w") as f:
            json.dump(token_data, f)
        self.token_data = TokenData.from_json(token_data)

    def _load_tokens(self) -> bool:
        """Load tokens from file if available."""
        if os.path.exists(self.settings.token_file):
            with open(self.settings.token_file, "r") as f:
                raw_data = json.load(f)
            self.token_data = TokenData.from_json(raw_data)
            return True
        return False

    def refresh_token(self) -> None:
        """Refresh expired access token using refresh token."""
        if not self.token_data:
            raise ValueError("No token data available")

        response = requests.post(
            self.settings.token_url,
            data={
                "client_id": self.settings.client_id,
                "client_secret": self.settings.client_secret,
                "grant_type": "refresh_token",
                "refresh_token": self.token_data.refresh_token,
            },
        )
        response.raise_for_status()
        self._save_tokens(response.json())


class CookieManager:
    """Manages browser cookies for authenticated session."""

    def __init__(self, cookie_file: str) -> None:
        """Initialize with path to cookie file."""
        self.cookie_file = cookie_file
        self.session = Session()

    def load_cookies(self) -> None:
        """Load cookies from JSON file into session."""
        with open(self.cookie_file, "r") as f:
            cookies = json.load(f)
        for name, value in cookies.items():
            self.session.cookies.set(name, value)


class ActivityDownloader:
    """Handles activity file downloads and naming."""

    def __init__(self, session: Session, database: ActivityDatabase) -> None:
        """Initialize with authenticated session and database."""
        self.session = session
        self.db = database

    def _sanitize_filename(self, name: str) -> str:
        """
        Sanitize activity name for filesystem safety.

        Replaces non-alphanumeric characters with underscores and trims whitespace.
        """
        return "".join(
            c if c.isalnum() or c in (' ', '_') else '_' for c in name
        ).strip()

    def download_activity(self, activity: ActivityDetails) -> bool:
        """
        Download an activity file if not previously downloaded.

        Returns:
            True if file was downloaded, False if skipped
        """
        if self.db.is_downloaded(activity.id):
            return False

        url = f"https://www.strava.com/activities/{activity.id}/export_original"
        response = self.session.get(url, stream=True)
        response.raise_for_status()

        # Generate filename from timestamp and sanitized name
        timestamp = activity.start_date.strftime("%Y%m%d_%H%M%S")
        clean_name = self._sanitize_filename(activity.name).replace(' ', '_')
        filename = f"{timestamp}_{clean_name}.fit"

        with open(filename, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        self.db.mark_downloaded(activity.id)
        print(f"✅ Downloaded {filename}")
        return True


class StravaClient:
    """Main client class for interacting with Strava API."""

    def __init__(self, auth: StravaAuth, downloader: ActivityDownloader) -> None:
        """Initialize with authentication and download components."""
        self.auth = auth
        self.downloader = downloader

    def get_filtered_activities(self) -> List[ActivityDetails]:
        """Retrieve VirtualRide activities containing 'MyWhoosh' in their name."""
        headers = {"Authorization": f"Bearer {self.auth.token_data.access_token}"}
        params = {"per_page": 100}
        response = requests.get(
            self.auth.settings.activities_url,
            headers=headers,
            params=params
        )
        response.raise_for_status()

        return [
            ActivityDetails(**activity)
            for activity in response.json()
            if activity.get("type") == "VirtualRide"
               and "MyWhoosh" in activity.get("name", "")
        ]


class StravaClientBuilder:
    """Builder pattern implementation for constructing StravaClient instances."""

    def __init__(self) -> None:
        """Initialize all component dependencies."""
        self.settings = StravaSettings()
        self.auth = StravaAuth(self.settings)
        self.cookie_manager = CookieManager(self.settings.cookie_file)
        self.database = ActivityDatabase(self.settings.database_file)

    def with_auth(self) -> "StravaClientBuilder":
        """Perform authentication flow."""
        self.auth.authenticate()
        return self

    def with_cookies(self) -> "StravaClientBuilder":
        """Load browser cookies for session."""
        self.cookie_manager.load_cookies()
        return self

    def build(self) -> StravaClient:
        """Construct the final client instance."""
        downloader = ActivityDownloader(
            self.cookie_manager.session,
            self.database
        )
        return StravaClient(self.auth, downloader)

    def __del__(self):
        """Clean up resources on instance destruction."""
        self.database.close()


if __name__ == "__main__":
    client_builder = None
    try:
        # Build and configure client
        client_builder = StravaClientBuilder()
        client = client_builder.with_auth().with_cookies().build()

        # Retrieve and filter activities
        all_activities = client.get_filtered_activities()
        new_activities = [
            a for a in all_activities
            if not client.downloader.db.is_downloaded(a.id)
        ]

        if not new_activities:
            print("No new activities found")
            exit()

        # Display new activities
        print("\n🏆 New Virtual Rides with 'MyWhoosh' in name:")
        for activity in new_activities:
            date_str = activity.start_date.strftime("%Y-%m-%d %H:%M")
            print(f"📅 {date_str} - {activity.name} (ID: {activity.id})")

        # Download new activities
        new_downloads = 0
        for activity in new_activities:
            if client.downloader.download_activity(activity):
                new_downloads += 1

        # Print summary
        print("\nDownload summary:")
        print(f"• New activities downloaded: {new_downloads}")
        print(f"• Already existed: {len(all_activities) - len(new_activities)}")
        print(f"• Total processed: {len(all_activities)}")

    except Exception as e:
        print(f"❌ Error: {str(e)}")
    finally:
        if client_builder:
            client_builder.database.close()
