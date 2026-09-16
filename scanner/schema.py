"""Bounded, strict extraction contract. Model output is untrusted input."""
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field

Text = Annotated[str, Field(max_length=12000)]
ShortText = Annotated[str, Field(max_length=500)]
class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

class Ingredient(StrictModel):
    original: Annotated[str, Field(min_length=1, max_length=300)]
    english: Annotated[str, Field(min_length=1, max_length=300)]

class LabelExtraction(StrictModel):
    product_name: ShortText
    language: Literal['nl', 'en', 'mixed', 'other', 'unknown']
    ingredients_present: bool
    ingredients_complete: bool
    ingredients_text: Text
    ingredients: Annotated[list[Ingredient], Field(max_length=100)]
    original_text: Text
    translated_text: Text
    contains: Annotated[list[ShortText], Field(max_length=30)]
    may_contain: Annotated[list[ShortText], Field(max_length=30)]
    visible_claims: Annotated[list[ShortText], Field(max_length=20)]
    unreadable_sections: Annotated[list[ShortText], Field(max_length=20)]
