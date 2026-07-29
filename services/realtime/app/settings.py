from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration via RT_-prefixed environment variables."""

    model_config = SettingsConfigDict(env_prefix="RT_")

    database_url: str = "postgresql://orders:dev-only-password@localhost:5432/orders"
    order_channel: str = "order_events"
    stock_channel: str = "stock_events"
    # Idle sockets get a heartbeat so intermediaries don't reap them.
    heartbeat_seconds: float = 25.0
    # Bounded per-client buffer: a slow consumer loses oldest events rather
    # than ballooning server memory (see ConnectionManager).
    client_queue_size: int = 100
    reconnect_max_backoff_seconds: float = 30.0
    log_level: str = "info"
