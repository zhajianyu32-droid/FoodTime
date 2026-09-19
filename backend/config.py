import os
import re
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
    # 通配符 CORS（逗号分隔的正则片段），用于 *.vercel.app 这类每次部署都变的预览域名。
    # 例：https://.*\.vercel\.app   留空则不启用。
    CORS_ORIGIN_REGEX: str = ""

    # ---- 数据库连接池（云数据库免费层连接数有限，默认调小；本地可通过环境变量调大）----
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 5
    DB_POOL_RECYCLE: int = 1800

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

    def model_post_init(self, __context) -> None:
        """
        Railway 环境变量适配。

        Railway 注入的 MySQL 插件变量名是 MYSQLHOST / MYSQLPORT / MYSQLUSER /
        MYSQLPASSWORD / MYSQLDATABASE，与本项目使用的 DB_* 命名不一致。
        这里做一层映射，使后端无需手填数据库连接信息即可走 **内网** 访问
        （mysql.railway.internal，不经公网代理，更快且不暴露端口）。

        ⚠️ 前提：MySQL 插件与后端服务**必须在同一个 Railway 项目内**，
        Railway 才会把 MYSQL* 注入到后端容器。跨项目时不会注入。

        优先级：显式配置的 DB_* > Railway 注入的 MYSQL* > 类默认值。
        即：只有当 DB_HOST 仍是默认值 "localhost" 时才采用 MYSQLHOST，
        避免本地开发时被误覆盖。
        """
        import os as _os

        # 仅在 DB_HOST 未被显式配置（仍是默认 localhost）时启用映射
        if self.DB_HOST not in ("localhost", ""):
            self._db_source = "explicit(DB_*)"
            return

        host = _os.getenv("MYSQLHOST")
        if not host:
            # 云环境下未注入 MYSQLHOST，说明不在同一项目 / 未关联 MySQL 插件。
            # 此时 DB_HOST 会停留在 localhost 导致连接被拒，故显式告警（不改行为）。
            if _os.getenv("RAILWAY_ENVIRONMENT") or _os.getenv("RAILWAY_PROJECT_ID"):
                import warnings as _w
                _w.warn(
                    "[DB-CONFIG] 未检测到 MYSQLHOST，数据库连接将使用 localhost "
                    "（通常不可用）。原因通常是 MySQL 与后端不在同一 Railway 项目。"
                    "请在 Variables 中显式配置 DB_HOST/DB_PORT/DB_USER/"
                    "DB_PASSWORD/DB_NAME。",
                    stacklevel=2,
                )
            self._db_source = "default(localhost)"
            return

        self.DB_HOST = host
        self.DB_TYPE = "mysql"
        if _os.getenv("MYSQLPORT"):
            self.DB_PORT = int(_os.getenv("MYSQLPORT"))
        if _os.getenv("MYSQLUSER"):
            self.DB_USER = _os.getenv("MYSQLUSER")
        if _os.getenv("MYSQLPASSWORD"):
            self.DB_PASSWORD = _os.getenv("MYSQLPASSWORD")
        if _os.getenv("MYSQLDATABASE"):
            self.DB_NAME = _os.getenv("MYSQLDATABASE")
        self._db_source = f"railway-env({self.DB_HOST})"

    @property
    def db_source(self) -> str:
        """数据库配置来源，用于启动日志诊断。"""
        return getattr(self, "_db_source", "unknown")

    @property
    def is_test(self) -> bool:
        return self.APP_ENV == "test"

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def db_url(self) -> str:
        if self.DB_TYPE == "sqlite":
            # 内存库（测试用）必须走 sqlite:///:memory:，不能拼成文件路径
            if self.DB_NAME in (":memory:", "") or "memory" in self.DB_NAME:
                return "sqlite:///:memory:"
            return f"sqlite:///./{self.DB_NAME}.db"
        return (
            f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
            "?charset=utf8mb4"
        )

    @property
    def cors_list(self) -> list[str]:
        """
        精确来源白名单。自动忽略含通配符 '*' 的项 —— 它们交给 cors_regex 处理，
        因为 CORSMiddleware 的 allow_origins 不支持通配符匹配（只会做字面比较）。
        """
        return [
            o.strip()
            for o in self.CORS_ORIGINS.split(",")
            if o.strip() and "*" not in o
        ]

    @property
    def cors_regex(self) -> str | None:
        """
        生成 allow_origin_regex 用的正则。合并两处来源：
        1) CORS_ORIGINS 中带 '*' 的项，例如 https://*.vercel.app
        2) CORS_ORIGIN_REGEX 显式配置的正则片段
        返回 None 表示不启用正则匹配。
        """
        patterns: list[str] = []

        # 1) 从 CORS_ORIGINS 的 *. 写法转换 -> 正则
        for origin in self.CORS_ORIGINS.split(","):
            origin = origin.strip()
            if not origin or "*" not in origin:
                continue
            # 转义除 * 以外的所有正则元字符，再把 \* 还原成 [^.]* 之类的宽松匹配
            escaped = re.escape(origin).replace(r"\*", r"[^/]*")
            patterns.append(escaped)

        # 2) 显式配置的正则片段（原样使用，由使用者保证正确性）
        if self.CORS_ORIGIN_REGEX.strip():
            patterns.append(self.CORS_ORIGIN_REGEX.strip())

        if not patterns:
            return None
        return "|".join(f"(?:{p})" for p in patterns)


settings = Settings()

# 防御性地把 SECRET_KEY 规范化 — 防止把占位符当作真实密钥
settings.SECRET_KEY = _ensure_secret_key(settings.SECRET_KEY)

if settings.is_production and settings.DEBUG:
    warnings.warn("PRODUCTION 环境不应开启 DEBUG，已自动关闭")
    settings.DEBUG = False

if settings.is_test:
    print(
        f"[ENV] 当前运行环境: TEST (数据库: {settings.DB_NAME} @ {settings.DB_HOST}:{settings.DB_PORT}) "
        f"[来源: {settings.db_source}]"
    )
elif settings.is_production:
    print(
        f"[ENV] 当前运行环境: PRODUCTION (数据库: {settings.DB_NAME} @ {settings.DB_HOST}:{settings.DB_PORT}) "
        f"[来源: {settings.db_source}]"
    )
    # 云环境下若数据库仍指向 localhost，说明变量未注入 —— 显式提示排查方向
    if settings.DB_HOST in ("localhost", "127.0.0.1"):
        print(
            "[ENV] ⚠️  数据库指向 localhost，容器内通常不可用。\n"
            "[ENV] ⚠️  排查：MySQL 与后端需在【同一个 Railway 项目】内，"
            "MYSQL* 变量才会自动注入；否则请在 Variables 中显式配置 "
            "DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME。"
        )
