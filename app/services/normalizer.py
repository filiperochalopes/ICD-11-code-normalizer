from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import SimpleTabulationCode


TOKEN_SPLIT_PATTERN = re.compile(r"([/&])")


class NormalizationError(ValueError):
    pass


@dataclass(slots=True)
class CodeComponent:
    code: str
    separator: str | None
    original_position: int
    is_extension: bool = False
    sort_key: int | None = None
    title: str | None = None


@dataclass(slots=True)
class NormalizationResult:
    input_code: str
    normalized_code: str
    components: list[CodeComponent]


class NormalizerService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def normalize(self, raw_expression: str) -> NormalizationResult:
        components = self._tokenize(raw_expression)
        self._hydrate_components(components)

        anchor = components[0]
        trailing = sorted(components[1:], key=self._sort_key_for_component)
        ordered_components = [anchor, *trailing]
        normalized_code = self._build_expression(ordered_components)

        return NormalizationResult(
            input_code=raw_expression,
            normalized_code=normalized_code,
            components=ordered_components,
        )

    def _tokenize(self, raw_expression: str) -> list[CodeComponent]:
        cleaned_expression = raw_expression.strip().upper()
        if not cleaned_expression:
            raise NormalizationError("ICD-11 expression is empty.")

        parts = [
            part.strip()
            for part in TOKEN_SPLIT_PATTERN.split(cleaned_expression)
            if part and part.strip()
        ]
        if not parts:
            raise NormalizationError("ICD-11 expression is empty after tokenization.")
        if parts[0] in {"/", "&"}:
            raise NormalizationError("Expression cannot start with a separator.")

        components = [CodeComponent(code=parts[0], separator=None, original_position=0)]
        index = 1
        position = 1

        while index < len(parts):
            separator = parts[index]
            if separator not in {"/", "&"}:
                raise NormalizationError(f"Unexpected token {separator!r} in expression.")
            if index + 1 >= len(parts):
                raise NormalizationError("Expression cannot end with a separator.")

            code = parts[index + 1].strip()
            if code in {"/", "&"}:
                raise NormalizationError("Expression contains consecutive separators.")

            components.append(
                CodeComponent(
                    code=code,
                    separator=separator,
                    original_position=position,
                )
            )
            index += 2
            position += 1

        return components

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
                component.title = None
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
    def _build_expression(components: list[CodeComponent]) -> str:
        if not components:
            return ""

        expression_parts = [components[0].code]
        for component in components[1:]:
            expression_parts.append(f"{component.separator}{component.code}")
        return "".join(expression_parts)

