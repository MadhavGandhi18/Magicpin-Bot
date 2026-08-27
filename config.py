import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

class Settings(BaseSettings):
    gemini_api_key: str
    openrouter_api_key: str
    team_name: str = "Prodigy"
    contact_email: str = "madhavgandhi99@gmail.com"
    model_name: str = "gemini-flash-latest"
    
    model_config = SettingsConfigDict(
        env_file=os.path.join(Path(__file__).parent.parent, ".env"), 
        env_file_encoding='utf-8', 
        extra='ignore'
    )

settings = Settings()
