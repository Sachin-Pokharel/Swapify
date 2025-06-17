from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    model_artifact_path: str

    class Config:
        env_file = ".env"

settings = Settings()
