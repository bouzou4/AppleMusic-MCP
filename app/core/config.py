from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Apple Music API
    apple_team_id: str
    apple_key_id: str  
    apple_private_key_path: str = "/keys/AuthKey.p8"
    
    
    # Server Configuration
    server_host: str = "0.0.0.0"
    server_port: int = 3600
    debug: bool = False
    oauth_port: int = 443  # Port for OAuth URLs (443 for HTTPS, 80 for HTTP)
    @property
    def oauth_base_url(self) -> str:
        """Get OAuth base URL using the configured oauth port"""
        if self.oauth_port == 443:
            return f"https://{self.server_host}"
        elif self.oauth_port == 80:
            return f"http://{self.server_host}"
        else:
            return f"http://{self.server_host}:{self.oauth_port}"
    
    # Database
    database_url: str = "sqlite:///./data/apple_music.db"
    
    # OAuth Security
    jwt_secret_key: str
    token_encryption_key: str
    
    # Token Lifetimes
    access_token_lifetime: int = 3600  # 1 hour
    refresh_token_lifetime: int = 2592000  # 30 days
    authorization_code_lifetime: int = 600  # 10 minutes
    
    # Rate Limiting
    rate_limit_requests: int = 100
    rate_limit_window: int = 3600  # 1 hour
    
    class Config:
        env_file = ".env"

settings = Settings()