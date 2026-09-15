import os
import secrets
import sys
import warnings

from pydantic_settings import BaseSettings, SettingsConfigDict


# 已写入仓库的占位 SECRET_KEY 字符串集合 — 一旦命中即视为未配置
_KNOWN_INSECURE_SECRETS = {
    "foodtime-dev-insecure-please-override-via-env",
    "foodtime-dev-insecure-change-me-please-2026",
    "PUT_A_NEW_RANDOM_HEX_HERE_32BYTES",
    "",
}


def _ensure_secret_key(raw: str) -> str:
    """
    P0-1 防护：
    1) 生产环境禁止使用已知的弱/占位密钥；
    2) 开发环境如未配置，自动生成 ephemeral 密钥（仅本次进程内有效，重启会让 JWT 失效），
       同时打印一条警告，提示用户把随机密钥写入 .env.local 以获得长期稳定。
    """
    if raw not in _KNOWN_INSECURE_SECRETS and len(raw) >= 16:
        return raw
    generated = secrets.token_hex(32)
    if os.environ.get("APP_ENV") == "production" or raw == "":
        warnings.warn(
            "[SECURITY] SECRET_KEY 使用了占位默认值，已自动生成一次性密钥。"
            " 请立即在 .env.local 中配置 SECRET_KEY 以避免重启后登录态失效。"
        )
    else:
        warnings.warn(
            "[SECURITY] SECRET_KEY 使用了仓库内置占位值，存在泄露风险。"
            " 请重新生成并通过 .env.local 注入。本次运行已临时生成随机密钥（重启失效）。"
        )
    return generated


class Settings(BaseSettings):
    # 注意：Pydantic v2 的 env_file 通过 SettingsConfigDict.env_file 声明；
    # 但 Windows + pydantic-settings 2.5.2 对多 env_file 的解析偶发异常，这里通过
    # 自定义 dotenv 加载器先 merge 两个 .env，再把结果作为 env_file 交给 pydantic。
    # 优先级：.env.local > .env
    @staticmethod
    def _merged_env_file() -> str:
        target = ".env.local"
        fallback = ".env"
        import os as _os
        for p in (target, fallback):
            if _os.path.exists(p):
                return p
        return fallback

    model_config = SettingsConfigDict(
        env_file=(
            # ⚠️ pydantic-settings v2: 在 env_file 列表中，**后者覆盖前者**。
            # 为保证".env.local（本机私密）> .env（模板）"，必须把优先级高的放后面。
            ".env",
            ".env.local",
        ),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_ENV: str = "test"
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = ""
    DB_NAME: str = "Gourmet_House_test"
    DB_TYPE: str = "sqlite"

    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-chat"

    DASHSCOPE_API_KEY: str = ""
    QWEN_MODEL: str = "qwen-plus"

    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    DEBUG: bool = True
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # ---- P0 安全 ----
    SECRET_KEY: str = "foodtime-dev-insecure-please-override-via-env"
    # 限流 / LLM 配额（每用户每天）
    RATE_LIMIT_PER_MIN: int = 60
    LLM_RECIPES_QUOTA: int = 30
    LLM_FORTUNE_QUOTA: int = 2
    LLM_CHAT_QUOTA: int = 10

    # ---- 日志 ----
    LOG_LEVEL: str = "INFO"         # DEBUG/INFO/WARNING/ERROR
    LOG_DIR: str = "./logs"

    @property
    def is_test(self) -> bool:
        return self.APP_ENV == "test"

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def db_url(self) -> str:
        if self.DB_TYPE == "sqlite":
            return f"sqlite:///./{self.DB_NAME}.db"
        return (
            f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
            "?charset=utf8mb4"
        )

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()

# 防御性地把 SECRET_KEY 规范化 — 防止把占位符当作真实密钥
settings.SECRET_KEY = _ensure_secret_key(settings.SECRET_KEY)

if settings.is_production and settings.DEBUG:
    warnings.warn("PRODUCTION 环境不应开启 DEBUG，已自动关闭")
    settings.DEBUG = False

if settings.is_test:
    print(f"[ENV] 当前运行环境: TEST (数据库: {settings.DB_NAME})")
elif settings.is_production:
    print(f"[ENV] 当前运行环境: PRODUCTION (数据库: {settings.DB_NAME})")
