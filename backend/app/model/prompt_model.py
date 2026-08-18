"""Structured image-description output used for semantic retrieval."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

NonBlankText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
]


class ImageDescription(BaseModel):
    """Observable image details converted into text for embedding."""

    model_config = ConfigDict(frozen=True)

    summary: NonBlankText = Field(
        description="Concise factual overview of the complete visible image."
    )
    subjects: tuple[NonBlankText, ...] = Field(
        description=(
            "Visible people, animals, products, objects, and other primary entities."
        )
    )
    attributes: tuple[NonBlankText, ...] = Field(
        description=(
            "Observable appearance, clothing, materials, shapes, condition, "
            "expressions, and poses."
        )
    )
    actions: tuple[NonBlankText, ...] = Field(
        description="Visible activities, interactions, and movement."
    )
    setting: tuple[NonBlankText, ...] = Field(
        description=(
            "Environment, location type, weather, lighting, foreground, and background."
        )
    )
    colors: tuple[NonBlankText, ...] = Field(
        description="Dominant and retrieval-relevant colors tied to visible content."
    )
    style: tuple[NonBlankText, ...] = Field(
        description=(
            "Medium, photographic or illustrative style, composition, framing, "
            "and viewpoint."
        )
    )
    visible_text: tuple[NonBlankText, ...] = Field(
        description=(
            "Exactly readable visible text; omit obscured content instead of guessing."
        )
    )
    search_keywords: tuple[NonBlankText, ...] = Field(
        description="Concise terms and phrases useful for semantic retrieval."
    )

    def to_embedding_text(self) -> str:
        """Return deterministic formatted description text for embedding."""
        sections: tuple[tuple[str, tuple[str, ...]], ...] = (
            ("Subjects", self.subjects),
            ("Attributes", self.attributes),
            ("Actions", self.actions),
            ("Setting", self.setting),
            ("Colors", self.colors),
            ("Style", self.style),
            ("Visible text", self.visible_text),
            ("Search keywords", self.search_keywords),
        )
        lines = (f"Summary: {self.summary}",) + tuple(
            f"{label}: {', '.join(values)}" for label, values in sections if values
        )
        return "\n".join(lines)
