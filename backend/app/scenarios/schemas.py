from pydantic import BaseModel, ConfigDict, Field


class ScenarioImportInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    scenario_id: str = Field(min_length=1, max_length=40)
    csv_text: str = Field(min_length=1, max_length=2_000_000)
