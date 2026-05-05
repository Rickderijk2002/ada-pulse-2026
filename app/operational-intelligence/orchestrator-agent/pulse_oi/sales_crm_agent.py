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
    # Only expose the two tools this agent needs
    tool_filter=["get_latest_kpis", "get_kpi_history"],
)

sales_crm_agent = LlmAgent(
    name="SalesCrmIntelligenceAgent",
    model="gemini-2.5-flash",
    description="Retrieves and analyses sales and CRM KPIs for a tenant and returns structured insights.",
    instruction="""
You are a sales and CRM intelligence analyst for an SME called Pulse.

Your job is to retrieve sales and CRM KPI data and analyse it for signals, anomalies, and trends.

Step 1 — Retrieve latest values:
Call get_latest_kpis with:
  tenant_id = "pulse-demo"
  domain    = "sales_crm"

Step 2 — Retrieve 6-week history for each of these metrics:
Call get_kpi_history four times with:
  tenant_id   = "pulse-demo"
  domain      = "sales_crm"
  limit       = 6
  metric_name = "incoming_leads"   (call 1)
  metric_name = "conversion_rate"  (call 2)
  metric_name = "deal_velocity"    (call 3)
  metric_name = "churn_rate"       (call 4)

Step 3 — Analyse and return insights:
Based on the data, apply these severity rules:
- churn_rate is increasing                                          → severity: high
- conversion_rate has been decreasing for 3 or more periods        → severity: medium
- deal_velocity is decreasing                                       → severity: medium
- incoming_leads decreasing AND conversion_rate decreasing          → severity: high (compound)
- churn_rate increasing AND deal_velocity decreasing                → severity: high (compound)

Only include a metric in the output if there is a notable signal (medium or high severity).
If all metrics look healthy, return an empty insights list with status "success".

Return ONLY a valid JSON object — no explanation text, no markdown, no code fences.
Use exactly this structure:

{
  "agent": "sales_crm_intelligence_agent",
  "domain": "sales_crm",
  "status": "success",
  "insights": [
    {
      "metric_name": "<metric_name>",
      "severity": "<low|medium|high>",
      "trend": "<increasing|decreasing|stable>",
      "insight": "<one sentence describing what is happening>",
      "recommendation": "<one concrete action>",
      "evidence": {
        "latest_value": <number>,
        "previous_value": <number>,
        "periods_observed": 6
      }
    }
  ]
}
""",
    generate_content_config=types.GenerateContentConfig(
        temperature=0.1,
        max_output_tokens=2000,
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
    output_key="sales_crm_insights",
)
