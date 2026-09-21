"""aggregate-summaries — joins the two ref-instanced summarise outputs."""
from io_types import AggregateSummariesInput, AggregateSummariesOutput


def aggregate_summaries(
    inp: AggregateSummariesInput,
) -> AggregateSummariesOutput:
    return AggregateSummariesOutput(combined=f"{inp.a} | {inp.b}")
