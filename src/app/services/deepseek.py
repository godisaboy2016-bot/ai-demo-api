import httpx

from app.core.config import Settings, get_settings
from app.core.exceptions import DeepSeekError


class DeepSeekService:
    """Client for the DeepSeek chat completions API."""

    def __init__(self, settings: Settings) -> None:
        self._api_key = settings.deepseek_api_key
        self._base_url = settings.deepseek_base_url.rstrip("/")
        self._model = settings.deepseek_model
        self._timeout = settings.deepseek_timeout_seconds

    @property
    def default_model(self) -> str:
        """Default model used when no override is provided."""
        return self._model

    async def chat(self, message: str, model: str | None = None) -> str:
        """Send a user message and return the AI reply."""
        if not self._api_key:
            raise DeepSeekError("DeepSeek API key is not configured.", status_code=503)

        payload = {
            "model": model or self._model,
            "messages": [{"role": "user", "content": message}],
            "stream": False,
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                )
        except httpx.TimeoutException as exc:
            raise DeepSeekError("DeepSeek API request timed out.", status_code=504) from exc
        except httpx.HTTPError as exc:
            raise DeepSeekError("Failed to reach DeepSeek API.") from exc

        if response.status_code != 200:
            raise DeepSeekError(
                f"DeepSeek API returned HTTP {response.status_code}: {response.text}"
            )

        try:
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError) as exc:
            raise DeepSeekError("Unexpected response from DeepSeek API.") from exc


def get_deepseek_service() -> DeepSeekService:
    """Dependency factory for DeepSeekService."""
    return DeepSeekService(get_settings())
