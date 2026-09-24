from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, model_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ResultIn(BaseModel):
    station: str = Field(min_length=1, examples=["ST-01"])
    lot: str = Field(min_length=1, examples=["LOT-A"])
    serial: str = Field(min_length=1, examples=["SN-0101"])
    result: Literal["pass", "fail"]

    fail_code: str | None = Field(default=None, examples=["V_OUT_LOW"])
    measurements: dict[str, float] = Field(
        default_factory=dict, examples=[{"v_out": 5.02, "temp_c": 41.3}]
    )
    ts: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def check_fail_code(self):
        if self.result == "fail" and not self.fail_code:
            raise ValueError("A fail result requires a fail_code")
        if self.result == "pass" and self.fail_code:
            raise ValueError("A pass result should have no fail_code")
        return self
