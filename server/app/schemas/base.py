from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class StrictModel(BaseModel):
    """Base for every agent input/output and API schema.

    - extra="forbid": unknown fields are a validation error (and JSON schema gets additionalProperties: false,
      which structured-output APIs require).
    - camelCase aliases: JSON matches the frontend's TypeScript types; Python code keeps snake_case.
    """

    model_config = ConfigDict(
        extra="forbid",
        alias_generator=to_camel,
        populate_by_name=True,
        # No str_strip_whitespace: it would corrupt file contents (indentation, trailing newlines).
    )

    def to_json_dict(self) -> dict:
        return self.model_dump(mode="json", by_alias=True)
