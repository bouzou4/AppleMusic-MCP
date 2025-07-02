from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Apple Music API
    apple_team_id: str
    apple_key_id: str  
    apple_private_key_path: str = "/keys/AuthKey.p8"
    
    # Apple Music OAuth (for user tokens)
    apple_client_id: str
    apple_client_secret: str
    
    # Server Configuration
    server_host: str = "0.0.0.0"
    server_port: int = 8080
    debug: bool = False
    oauth_base_url: str = "http://localhost:8080"
    
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