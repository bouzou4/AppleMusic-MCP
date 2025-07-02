from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Apple Music API
    apple_team_id: str
    apple_key_id: str  
    apple_private_key_path: str = "/keys/AuthKey.p8"
    
    # Server Configuration
    server_host: str = "0.0.0.0"
    server_port: int = 8080
    debug: bool = False
    
    # Rate Limiting
    rate_limit_requests: int = 100
    rate_limit_window: int = 3600  # 1 hour
    
    class Config:
        env_file = ".env"

settings = Settings()