from app.services.normalizer import CodeComponent


class TitleBuilderService:
    def build_title(self, components: list[CodeComponent]) -> str:
        # Business rule:
        # - each stem starts a new title segment, joined by " / "
        # - each extension remains attached to its stem and is rendered as
        #   a bracketed qualifier immediately after that stem title
        # This mirrors the normalized code shape:
        #   stem1/stem2
        #   stem1&ext1/stem2
        #   stem1&ext1/stem2&ext2
        # into:
        #   Stem 1 / Stem 2
        #   Stem 1 [Ext 1] / Stem 2
        #   Stem 1 [Ext 1] / Stem 2 [Ext 2]
        if not components:
            return ""

        parts: list[str] = []
        for component in components:
            if component.is_stem:
                if parts:
                    parts.append(" / ")
                parts.append(self._title_for_component(component))
                continue

            parts.append(f" [{self._title_for_component(component)}]")
        return "".join(parts)

    @staticmethod
    def _title_for_component(component: CodeComponent) -> str:
        return component.title or f"Unknown code {component.code}"
