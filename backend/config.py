from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    app_env: str = 'dev'
    postgres_host: str = 'localhost'
    postgres_port: int = 5432
    postgres_db: str = 'backend'
    postgres_user: str = 'backend'
    postgres_password: str = 'backend'

    azurite_blob_host: str = '127.0.0.1'
    azurite_blob_port: int = 10000
    azure_account_name: str = 'devstoreaccount1'
    azure_account_key: str = (
        'Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw=='
    )
    azure_raw_container: str = 'raw'
    app_host: str = '0.0.0.0'
    app_port: int = 8000

    llm_provider: str = 'gemini'
    google_api_key: str | None = None
    gemini_model: str = 'gemini-2.0-flash'
    llm_prompt_version: str = 'v1'
    auto_post_confidence_threshold: float = 0.9

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def azurite_connection_string(self) -> str:
        return (
            'DefaultEndpointsProtocol=http;'
            f'AccountName={self.azure_account_name};'
            f'AccountKey={self.azure_account_key};'
            f'BlobEndpoint=http://{self.azurite_blob_host}:{self.azurite_blob_port}/{self.azure_account_name};'
        )


settings = Settings()
