import logging
from dataclasses import dataclass

from app.core.config import get_settings
from app.services.normalizer import CodeComponent


logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = """You are a clinical terminology assistant.

Your task is to rewrite an ICD-11 post-coordinated expression into a clinically precise, natural-sounding title in English.

Rules:
- Preserve the exact clinical meaning.
- Do not omit severity, temporality, anatomy, laterality, etiology, or extension meaning.
- Do not add information that is not present.
- Prefer formal clinical phrasing.
- Return only one final phrase.

Normalized code: {normalized_code}
Ordered components:
{components}

Basic concatenated title:
{basic_title}
"""


@dataclass(slots=True)
class AIPhraseResult:
    text: str
    requested_model_name: str
    resolved_model_name: str


class AIPhraseService:
    def __init__(self) -> None:
        settings = get_settings()
        self._settings = settings
        self.model_name = settings.openrouter_model
        self.prompt_version = settings.prompt_version

    def generate_ai_phrase(
        self,
        normalized_code: str,
        components: list[CodeComponent],
        basic_title: str,
    ) -> AIPhraseResult | None:
        if not self._settings.openrouter_api_key.strip():
            logger.info("Skipping AI phrase generation because OPENROUTER_API_KEY is not configured")
            return None

        try:
            from langchain_core.prompts import ChatPromptTemplate
            from langchain_openai import ChatOpenAI
        except ImportError:
            logger.exception("LangChain/OpenAI dependencies are not available")
            return None

        try:
            prompt = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
            model = ChatOpenAI(
                model=self._settings.openrouter_model,
                api_key=self._settings.openrouter_api_key,
                base_url=self._settings.openrouter_base_url,
                timeout=self._settings.llm_timeout_seconds,
                temperature=0,
                max_retries=1,
            )
            response = (prompt | model).invoke(
                {
                    "normalized_code": normalized_code,
                    "components": self._render_components(components),
                    "basic_title": basic_title,
                }
            )
            text = self._extract_content(response.content)
            if not text:
                return None

            return AIPhraseResult(
                text=text,
                requested_model_name=self.model_name,
                resolved_model_name=self._extract_model_name(response),
            )
        except Exception:
            logger.exception("LLM error while generating AI phrase")
            return None

    @staticmethod
    def _render_components(components: list[CodeComponent]) -> str:
        rendered: list[str] = []
        stem_index = 0

        for component in components:
            label = component.title or f"Unknown code {component.code}"
            if component.is_stem:
                stem_index += 1
                rendered.append(f"- Stem {stem_index}: {component.code}: {label}")
                continue

            rendered.append(f"  - Extension for stem {stem_index}: {component.code}: {label}")

        return "\n".join(rendered)

    @staticmethod
    def _extract_content(content: str | list[dict] | list[str]) -> str | None:
        if isinstance(content, str):
            cleaned = content.strip()
            return cleaned or None

        if isinstance(content, list):
            text_chunks: list[str] = []
            for item in content:
                if isinstance(item, str):
                    text_chunks.append(item)
                elif isinstance(item, dict):
                    text_value = item.get("text")
                    if isinstance(text_value, str):
                        text_chunks.append(text_value)
            merged = " ".join(part.strip() for part in text_chunks if part.strip()).strip()
            return merged or None

        return None

    def _extract_model_name(self, response) -> str:
        response_metadata = getattr(response, "response_metadata", {}) or {}
        if not isinstance(response_metadata, dict):
            return self.model_name

        for key in ("model", "model_name"):
            value = response_metadata.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

        return self.model_name
