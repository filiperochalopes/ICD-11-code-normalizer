from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.models import SimpleTabulationCode

logger = logging.getLogger(__name__)


TOKEN_SPLIT_PATTERN = re.compile(r"([/&])")


class NormalizationError(ValueError):
    pass


@dataclass(slots=True)
class CodeComponent:
    code: str
    separator: str | None
    original_position: int
    is_stem: bool
    is_extension: bool = False
    sort_key: int | None = None
    title: str | None = None


@dataclass(slots=True)
class CodeCluster:
    stem: CodeComponent
    extensions: list[CodeComponent]
    original_position: int


@dataclass(slots=True)
class NormalizationResult:
    input_code: str
    normalized_code: str
    components: list[CodeComponent]


class NormalizerService:
    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self.session = session
        self._settings = settings or get_settings()

    def normalize(self, raw_expression: str) -> NormalizationResult:
        # Business rule:
        # - "/" separates stem groups from one another.
        # - "&" attaches extension codes to the immediately preceding stem.
        # - stems are sorted among themselves.
        # - extensions are sorted only inside their own stem group.
        # This preserves stem -> extension linkage after normalization.
        clusters = self._tokenize_clusters(raw_expression)
        components = self._flatten_tokenized_clusters(clusters)
        self._hydrate_components(components)

        ordered_clusters = sorted(clusters, key=self._sort_key_for_cluster)
        for cluster in ordered_clusters:
            cluster.extensions.sort(key=self._sort_key_for_component)

        ordered_components = self._flatten_normalized_clusters(ordered_clusters)
        normalized_code = self._build_expression(ordered_components)

        return NormalizationResult(
            input_code=raw_expression,
            normalized_code=normalized_code,
            components=ordered_components,
        )

    def _tokenize_clusters(self, raw_expression: str) -> list[CodeCluster]:
        cleaned_expression = raw_expression.strip().upper()
        if not cleaned_expression:
            raise NormalizationError("ICD-11 expression is empty.")

        parts = [
            part.strip()
            for part in TOKEN_SPLIT_PATTERN.split(cleaned_expression)
            if part is not None
        ]
        if not parts or parts[0] in {"/", "&"}:
            raise NormalizationError("Expression cannot start with a separator.")
        if parts[-1] in {"/", "&"}:
            raise NormalizationError("Expression cannot end with a separator.")

        raw_clusters = [segment.strip() for segment in cleaned_expression.split("/")]
        if any(not segment for segment in raw_clusters):
            raise NormalizationError("Expression contains empty stem groups.")

        clusters: list[CodeCluster] = []
        position = 0

        for cluster_position, raw_cluster in enumerate(raw_clusters):
            raw_codes = [segment.strip() for segment in raw_cluster.split("&")]
            if any(not code for code in raw_codes):
                raise NormalizationError("Expression contains empty extension codes.")

            stem = CodeComponent(
                code=raw_codes[0],
                separator=None,
                original_position=position,
                is_stem=True,
            )
            position += 1

            extensions: list[CodeComponent] = []
            for code in raw_codes[1:]:
                extensions.append(
                    CodeComponent(
                        code=code,
                        separator="&",
                        original_position=position,
                        is_stem=False,
                    )
                )
                position += 1

            clusters.append(
                CodeCluster(
                    stem=stem,
                    extensions=extensions,
                    original_position=cluster_position,
                )
            )

        return clusters

    @staticmethod
    def _flatten_tokenized_clusters(clusters: list[CodeCluster]) -> list[CodeComponent]:
        flattened: list[CodeComponent] = []
        for cluster in clusters:
            flattened.append(cluster.stem)
            flattened.extend(cluster.extensions)
        return flattened

    def _fetch_title_from_icd_api(self, code: str) -> str | None:
        base = self._settings.who_icd_api_base_url
        release = self._settings.who_icd_release_id
        headers = {"API-Version": "v2", "Accept-Language": "en"}
        try:
            r1 = httpx.get(
                f"{base}/icd/release/11/{release}/mms/codeInfo/{code}",
                headers=headers,
                timeout=5.0,
            )
            if r1.status_code != 200:
                return None
            stem_id = r1.json().get("stemId", "")
            if not stem_id:
                return None
            entity_url = stem_id.replace("http://id.who.int", base)
            r2 = httpx.get(entity_url, headers=headers, timeout=5.0)
            if r2.status_code == 200:
                return r2.json().get("title", {}).get("@value")
        except Exception:
            logger.debug("ICD API fallback failed for code %s", code, exc_info=True)
        return None

    def _hydrate_components(self, components: list[CodeComponent]) -> None:
        codes = [component.code for component in components]
        rows = self.session.scalars(
            select(SimpleTabulationCode).where(SimpleTabulationCode.code.in_(codes))
        ).all()
        lookup = {row.code: row for row in rows}

        for component in components:
            row = lookup.get(component.code)
            if not row:
                component.is_extension = component.code.startswith("X")
                component.title = self._fetch_title_from_icd_api(component.code)
                component.sort_key = None
                continue

            component.is_extension = row.is_extension
            component.title = row.title
            component.sort_key = row.sort_key

    @staticmethod
    def _sort_key_for_component(component: CodeComponent) -> tuple[int, int, int]:
        return (
            1 if component.sort_key is None else 0,
            component.sort_key or 10**12,
            component.original_position,
        )

    @staticmethod
    def _sort_key_for_cluster(cluster: CodeCluster) -> tuple[int, int, int]:
        stem = cluster.stem
        return (
            1 if stem.sort_key is None else 0,
            stem.sort_key or 10**12,
            cluster.original_position,
        )

    @staticmethod
    def _flatten_normalized_clusters(clusters: list[CodeCluster]) -> list[CodeComponent]:
        flattened: list[CodeComponent] = []
        for cluster_index, cluster in enumerate(clusters):
            cluster.stem.separator = None if cluster_index == 0 else "/"
            flattened.append(cluster.stem)
            for extension in cluster.extensions:
                extension.separator = "&"
                flattened.append(extension)
        return flattened

    @staticmethod
    def _build_expression(components: list[CodeComponent]) -> str:
        if not components:
            return ""

        expression_parts = [components[0].code]
        for component in components[1:]:
            expression_parts.append(f"{component.separator}{component.code}")
        return "".join(expression_parts)
