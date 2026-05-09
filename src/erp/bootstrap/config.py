"""
ERP 应用配置模块

基于 Pydantic Settings 的分层配置管理，支持环境变量与 .env 文件覆盖。

配置分组:
  - DatabaseSettings: PostgreSQL 异步连接池配置 (ERP_DB_ 前缀)
  - RedisSettings: Redis 缓存配置 (ERP_REDIS_ 前缀)
  - RabbitMQSettings: RabbitMQ 消息队列配置 (ERP_RABBITMQ_ 前缀)
  - KeycloakSettings: Keycloak SSO 认证配置 (ERP_KEYCLOAK_ 前缀)
  - ObjectStorageSettings: MinIO/S3 对象存储配置 (ERP_OSS_ 前缀)
  - OpenSearchSettings: OpenSearch 全文检索配置 (ERP_OPENSEARCH_ 前缀)
  - AppSettings: 应用全局配置 (ERP_ 前缀)，聚合上述所有子配置

环境变量命名规则: {前缀}_{字段名}，如 ERP_DB_URL、ERP_REDIS_URL
生产环境务必修改: secret_key、jwt_secret、数据库密码、OSS密钥等敏感配置
"""
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """数据库配置 - PostgreSQL异步连接池，环境变量前缀: ERP_DB_"""
    model_config = SettingsConfigDict(env_prefix="ERP_DB_", env_file=".env", env_file_encoding="utf-8", extra="ignore")

    url: PostgresDsn = Field(
        default="postgresql+asyncpg://erp:erp_secret@localhost:5432/erp_db",
        description="异步PostgreSQL连接URL，格式: postgresql+asyncpg://user:pass@host:port/db",
    )
    pool_size: int = Field(default=20, description="连接池大小，建议生产环境20-50")
    max_overflow: int = Field(default=10, description="最大溢出连接数，pool_size + max_overflow = 最大连接数")
    pool_recycle: int = Field(default=3600, description="连接回收时间(秒)，防止数据库主动断开连接")
    echo: bool = Field(default=False, description="是否打印SQL语句，生产环境务必设为False")


class RedisSettings(BaseSettings):
    """Redis配置 - 缓存/会话/分布式锁，环境变量前缀: ERP_REDIS_"""
    model_config = SettingsConfigDict(env_prefix="ERP_REDIS_", env_file=".env", env_file_encoding="utf-8", extra="ignore")

    url: RedisDsn = Field(default="redis://localhost:6379/0", description="Redis连接URL，格式: redis://host:port/db")
    key_prefix: str = Field(default="erp:", description="Redis键前缀，多租户/多应用隔离")


class RabbitMQSettings(BaseSettings):
    """RabbitMQ配置 - 异步消息队列，环境变量前缀: ERP_RABBITMQ_"""
    model_config = SettingsConfigDict(env_prefix="ERP_RABBITMQ_", env_file=".env", env_file_encoding="utf-8", extra="ignore")

    url: str = Field(default="amqp://erp:erp_secret@localhost:5672/erp_vhost", description="RabbitMQ AMQP连接URL")


class KeycloakSettings(BaseSettings):
    """Keycloak配置 - SSO单点登录/OAuth2认证，环境变量前缀: ERP_KEYCLOAK_"""
    model_config = SettingsConfigDict(env_prefix="ERP_KEYCLOAK_", env_file=".env", env_file_encoding="utf-8", extra="ignore")

    server_url: str = Field(default="http://localhost:8080", description="Keycloak服务器地址")
    realm: str = Field(default="erp", description="Keycloak Realm名称")
    client_id: str = Field(default="erp-api", description="OAuth2客户端ID")
    client_secret: str = Field(default="", description="OAuth2客户端密钥，生产环境必填")


class KafkaSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ERP_KAFKA_", env_file=".env", env_file_encoding="utf-8", extra="ignore")
    bootstrap_servers: str = Field(default="localhost:9092")
    security_protocol: str = Field(default="PLAINTEXT")


class CelerySettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ERP_CELERY_", env_file=".env", env_file_encoding="utf-8", extra="ignore")
    broker_url: str = Field(default="redis://localhost:6379/0")
    result_backend: str = Field(default="redis://localhost:6379/0")


class ObjectStorageSettings(BaseSettings):
    """对象存储配置 - MinIO/S3兼容，环境变量前缀: ERP_OSS_"""
    model_config = SettingsConfigDict(env_prefix="ERP_OSS_", env_file=".env", env_file_encoding="utf-8", extra="ignore")

    endpoint: str = Field(default="http://localhost:9000", description="S3兼容端点地址")
    access_key: str = Field(default="minioadmin", description="访问密钥Access Key")
    secret_key: str = Field(default="minioadmin", description="访问密钥Secret Key，生产环境务必修改")
    bucket: str = Field(default="erp-assets", description="默认存储桶名称")
    region: str = Field(default="us-east-1", description="存储区域")


class OpenSearchSettings(BaseSettings):
    """OpenSearch配置 - 全文检索/日志分析，环境变量前缀: ERP_OPENSEARCH_"""
    model_config = SettingsConfigDict(env_prefix="ERP_OPENSEARCH_", env_file=".env", env_file_encoding="utf-8", extra="ignore")

    hosts: str = Field(default="http://localhost:9200", description="OpenSearch节点地址，多节点逗号分隔")
    username: str = Field(default="admin", description="认证用户名")
    password: str = Field(default="admin", description="认证密码，生产环境务必修改")


class AppSettings(BaseSettings):
    """应用全局配置 - 聚合所有子配置，环境变量前缀: ERP_"""
    model_config = SettingsConfigDict(env_prefix="ERP_", env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = Field(default="Cross-Border ERP", description="应用名称")
    environment: Literal["development", "staging", "production"] = Field(default="development", description="运行环境: development/staging/production")
    debug: bool = Field(default=True, description="调试模式，生产环境务必设为False")
    api_prefix: str = Field(default="/api", description="API基础路径前缀")
    admin_prefix: str = Field(default="/api/admin/v1", description="管理端API路径前缀")
    open_prefix: str = Field(default="/api/open/v1", description="开放API路径前缀(第三方调用)")
    webhook_prefix: str = Field(default="/api/webhooks", description="Webhook回调路径前缀")
    secret_key: str = Field(default="change-me-in-production-32chars!!", description="应用密钥，生产环境务必修改为随机32+字符")
    jwt_secret: str = Field(default="change-me-jwt-secret-key-32chars!", description="JWT签名密钥，生产环境务必修改")
    jwt_algorithm: str = Field(default="HS256", description="JWT签名算法")
    access_token_expire_minutes: int = Field(default=30, description="访问令牌过期时间(分钟)")
    refresh_token_expire_days: int = Field(default=7, description="刷新令牌过期时间(天)")
    cors_origins: list[str] = Field(default=["*"], description="CORS允许的源列表，生产环境限制为具体域名")

    db: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    kafka: KafkaSettings = Field(default_factory=KafkaSettings)
    celery: CelerySettings = Field(default_factory=CelerySettings)
    rabbitmq: RabbitMQSettings = Field(default_factory=RabbitMQSettings)
    keycloak: KeycloakSettings = Field(default_factory=KeycloakSettings)
    oss: ObjectStorageSettings = Field(default_factory=ObjectStorageSettings)
    opensearch: OpenSearchSettings = Field(default_factory=OpenSearchSettings)


    @property
    def redis_url(self) -> str:
        return str(self.redis.url)


def get_settings() -> AppSettings:
    return AppSettings()
