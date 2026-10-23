"""The stable screener wire, independent of routing, storage and engine imports."""
from __future__ import annotations

from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, SkipValidation, field_validator, model_validator


class ScanIdentity(BaseModel):
    """Provenance for feedback bound to a scan and its engine version.

    Absent on old artifacts; when present it must be complete and closed.
    """
    model_config = ConfigDict(extra="forbid")
    scan_date: str | None
    universe_type: str
    engine_config_version: str


# The health board describes market context. Its closed contract refuses
# score/tier/trigger/setup fields rather than turning context into trade ideas.
# Existing drift tests pin these states to the pipeline's health-board vocabulary.
HealthStateName = Literal[
    "near_resistance", "post_breakout_markup", "near_support", "consolidating",
    "trending", "deep_correction", "no_structure",
]


class HealthMember(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ticker: str
    name: str | None = None
    state: HealthStateName
    box_pos: float | None = None
    breakout_extension: float | None = None
    distance_to_high_pct: float | None = None
    R: float | None = None
    S: float | None = None
    base_len: int
    candles: list[Any]
    volumes: list[Any]


class HealthBoard(BaseModel):
    model_config = ConfigDict(extra="forbid")
    members: list[HealthMember]
    unreadable: list[dict[str, Any]]
    member_count: int


class ScreenerChart(BaseModel):
    """Core fields every drawable chart carries; additive facts stay allowed.

    Bar arrays remain opaque: parsing every bar again on each GET would make
    validation proportional to the full price history. Existing candle and
    reader wire tests own their detailed contract.
    """
    model_config = ConfigDict(extra="allow", strict=True)
    candles: SkipValidation[list[dict[str, Any]]]
    R: FiniteFloat
    S: FiniteFloat
    score: FiniteFloat
    tier: Literal["S", "A", "B", "C", "D"]
    setup: str
    price: FiniteFloat | None
    trigger: FiniteFloat | None
    # Older scans did not carry these fields; missing means unmeasured.
    base_len: Annotated[int, Field(ge=0)] | None = None
    ta_grade: Annotated[FiniteFloat, Field(ge=0, le=100)] | None = None

    @field_validator("candles", mode="before")
    @classmethod
    def candle_array(cls, value: Any) -> Any:
        if not isinstance(value, list):
            raise ValueError("candles must be an array")
        return value


class ScreenerPayload(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)
    ordered_tickers: list[str]
    chart_data: dict[str, ScreenerChart]
    scan_identity: ScanIdentity | None = None
    health_board: HealthBoard | None = None

    @model_validator(mode="after")
    def chart_membership(self) -> Self:
        tickers = set(self.ordered_tickers)
        if len(tickers) != len(self.ordered_tickers):
            raise ValueError("ordered_tickers must not contain duplicates")
        if not set(self.chart_data).issubset(tickers):
            raise ValueError("a chart must belong to ordered_tickers")
        # An ungraded fire may deliberately have no drawable chart.
        return self


class ScreenerResponse(ScreenerPayload):
    universe: str
    status: Literal["ready", "never_scanned"]
    scanned_at: str | None
    stale_after: str | None
