import threading
from utils.config import get_config_value

_SUPPORTED_PROVIDERS = {"azure", "aws"}
_provider_lock = threading.RLock()
_active_provider = str(get_config_value("CLOUD_PROVIDER", "azure")).strip().lower()


def normalize_cloud_provider(provider: str) -> str:
    normalized = str(provider or "azure").strip().lower()
    if normalized not in _SUPPORTED_PROVIDERS:
        raise ValueError(
            f"Unsupported cloud provider: {normalized}. Supported providers: {', '.join(sorted(_SUPPORTED_PROVIDERS))}"
        )
    return normalized


def set_active_cloud_provider(provider: str) -> str:
    global _active_provider
    normalized = normalize_cloud_provider(provider)
    with _provider_lock:
        _active_provider = normalized
    return normalized


def get_active_cloud_provider() -> str:
    with _provider_lock:
        return _active_provider


def get_supported_cloud_providers() -> tuple:
    return tuple(sorted(_SUPPORTED_PROVIDERS))
