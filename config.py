from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# T10: 定义了应用需要的设置
# 但是敏感值比如密钥，都是从环境变量或者env文件中获取而不是代码
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    database_url: str
    # 当创建env文件时，里面会有个环境变量叫做SECRET KEY，并将匹配这里的设置
    # 如果key不在环境变量里设置，将使用env文件中的值
    # 如果环境变量和env都没有，将从这里config的默认值获取  
    secret_key: SecretStr
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # S3 Configuration
    s3_bucket_name: str
    s3_region: str = "us-east-1"
    s3_access_key_id: SecretStr | None = None
    s3_secret_access_key: SecretStr | None = None
    s3_endpoint_url: str | None = None

    # 设置最大的文件大小,可以保护服务器免于大文件上传
    max_upload_size_bytes: int = 5 * 1024 * 1024

    posts_per_page: int = 10

    reset_token_expire_minutes: int = 60

    mail_server: str = "localhost"
    mail_port: int = 587
    mail_username: str = ""
    mail_password: SecretStr = SecretStr("")
    mail_from: str = "noreply@example.com"
    mail_use_tls: bool = True

    frontend_url: str = "http://localhost:8000"

# 从env文件中加载，因为Settings类有：
# model_config = SettingsConfigDict(
#         env_file=".env",
#         env_file_encoding="utf-8",
#     )
settings = Settings()  # type: ignore[call-arg] # Loaded from .env file
