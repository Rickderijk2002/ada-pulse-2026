from __future__ import annotations

from google.adk.agents import ParallelAgent, SequentialAgent

from pulse_oi.financial_agent import financial_agent
from pulse_oi.sales_crm_agent import sales_crm_agent
from pulse_oi.synthesis_agent import synthesis_agent

# Step 1: Run Financial and Sales agents at the same time
# ParallelAgent fires both sub-agents concurrently.
# Each stores its result in session state via output_key:
#   financial_agent  → session["financial_insights"]
#   sales_crm_agent  → session["sales_crm_insights"]

parallel_analysis = ParallelAgent(
    name="ParallelKpiAnalysis",
    description="Runs financial and sales/CRM KPI analysis concurrently.",
    sub_agents=[financial_agent, sales_crm_agent],
)

# Step 2: Synthesise after both parallel agents complete
# synthesis_agent reads {financial_insights} and {sales_crm_insights}
# from session state (injected into its instruction template by ADK).
# It stores the result in session["synthesized_insights"].

# Full pipeline
# SequentialAgent runs parallel_analysis first, then synthesis_agent.
# ADK requires the top-level agent to be named root_agent.

root_agent = SequentialAgent(
    name="OperationalIntelligencePipeline",
    description=(
        "Pulse Operational Intelligence pipeline. "
        "Analyses financial and sales KPIs in parallel, "
        "then synthesises cross-domain insights."
    ),
    sub_agents=[parallel_analysis, synthesis_agent],
)
