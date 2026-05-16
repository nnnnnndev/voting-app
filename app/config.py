import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # All Azure/SharePoint fields are optional so the app can boot in dev mode
    # (MIE_DEV_AUTH=1) before an Entra app registration exists.
    azure_tenant_id: str = ""
    azure_client_id: str = ""
    azure_client_secret: str = ""
    azure_redirect_uri: str = "http://localhost:8000/auth/callback"

    sharepoint_hostname: str = ""
    sharepoint_site_path: str = ""

    session_secret: str = "dev-secret-change-me"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    @property
    def authority(self) -> str:
        return f"https://login.microsoftonline.com/{self.azure_tenant_id}"


settings = Settings()


def dev_mode() -> bool:
    return os.environ.get("MIE_DEV_AUTH") == "1"
