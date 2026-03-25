from app.services.normalizer import CodeComponent


class TitleBuilderService:
    def build_title(self, components: list[CodeComponent]) -> str:
        if not components:
            return ""

        parts = [self._title_for_component(components[0])]
        for component in components[1:]:
            joiner = " / " if component.separator == "/" else " + "
            parts.append(f"{joiner}{self._title_for_component(component)}")
        return "".join(parts)

    @staticmethod
    def _title_for_component(component: CodeComponent) -> str:
        return component.title or f"Unknown code {component.code}"

