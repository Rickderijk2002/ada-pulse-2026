from __future__ import annotations

import os

from dotenv import load_dotenv
from google.adk.agents.llm_agent import LlmAgent
from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams
from google.genai import types

load_dotenv()

KPI_MCP_URL = os.getenv("KPI_MCP_URL", "http://localhost:8080/mcp")

_tools = McpToolset(
    connection_params=StreamableHTTPConnectionParams(
        url=KPI_MCP_URL,
        timeout=120.0,
    ),
    tool_filter=["get_latest_kpis", "get_kpi_history"],
)

financial_agent = LlmAgent(
    name="FinancialIntelligenceAgent",
    model="gemini-2.5-flash-lite",
    max_steps=10,
    description="Retrieves and analyses financial KPIs for a tenant and returns structured insights.",
    instruction="""
You are a financial intelligence analyst for an SME called Pulse.

Your job is to retrieve financial KPI data and analyse it for signals and risks.

Step 1 — Retrieve latest values:
Call get_latest_kpis with:
  tenant_id = "pulse-demo"
  domain    = "financial"

Step 2 — Retrieve 6-week history for key metrics:
Call get_kpi_history five times in one batch, all with tenant_id="pulse-demo", domain="financial", limit=6:
  call 1: metric_name = "burn_rate"
  call 2: metric_name = "cash_flow"
  call 3: metric_name = "revenue_growth"
  call 4: metric_name = "outstanding_invoices"
  call 5: metric_name = "weekly_profit"

Step 3 — Apply severity rules and return insights.

TREND rules (look at the 6-week history):
- burn_rate increasing for 3 or more consecutive periods    → severity: medium
- cash_flow was negative in any of the last 3 periods       → severity: medium
- revenue_growth negative in latest period                  → severity: medium
- outstanding_invoices increasing for 2 or more periods     → severity: medium
- cash_flow negative latest AND outstanding_invoices rising → severity: high (compound)

ABSOLUTE VALUE rules (apply to latest value regardless of trend):
- cash_flow latest value < 0                                → severity: high
- weekly_profit latest value < 0                            → severity: medium
- revenue_growth latest value < -0.20 (worse than -20%)    → severity: high

Only include a metric if a rule triggers. If everything looks healthy return an empty insights list.

After completing Steps 1, 2, and 3, output your final JSON and STOP.
Do NOT call any tools again after producing the JSON output.

CRITICAL: Return ONLY raw JSON. Do NOT wrap in ```json or ``` code fences.
Do NOT add any explanation before or after the JSON.
The very first character of your response must be { and the very last must be }.

Use exactly this structure:

{
  "agent": "financial_intelligence_agent",
  "domain": "financial",
  "status": "success",
  "insights": [
    {
      "metric_name": "<metric_name>",
      "severity": "<low|medium|high>",
      "trend": "<increasing|decreasing|stable|volatile>",
      "insight": "<one sentence describing what is happening>",
      "recommendation": "<one concrete action>",
      "evidence": {
        "latest_value": <number>,
        "previous_value": <number>,
        "periods_observed": <number>
      }
    }
  ]
}
""",
    generate_content_config=types.GenerateContentConfig(
        temperature=0.1,
        max_output_tokens=4000,
        http_options=types.HttpOptions(
            retry_options=types.HttpRetryOptions(
                initial_delay=1.0,
                attempts=5,
                http_status_codes=[408, 429, 500, 502, 503, 504],
            ),
            timeout=120 * 1000,
        ),
    ),
    tools=[_tools],
    output_key="financial_insights",
)
