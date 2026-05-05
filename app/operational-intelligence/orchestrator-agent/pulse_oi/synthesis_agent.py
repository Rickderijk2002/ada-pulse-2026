from __future__ import annotations

from google.adk.agents.llm_agent import LlmAgent
from google.genai import types

# No MCP tools — synthesis agent reasons only on the outputs
# of the financial and sales agents passed via session state.

synthesis_agent = LlmAgent(
    name="InsightSynthesisAgent",
    model="gemini-2.5-flash",
    description="Combines financial and sales insights into a single consolidated intelligence report.",
    instruction="""
You are a cross-domain business analyst for an SME called Pulse.

You have received results from two specialist analysts:

Financial insights:
{financial_insights}

Sales/CRM insights:
{sales_crm_insights}

Your task is to produce ONE complete consolidated intelligence report.

Step 1 — Parse both inputs.
The inputs may be wrapped in ```json code fences — strip them and parse the JSON.
Extract the "insights" arrays from both payloads.

Step 2 — Collect all domain-level insights.
Take every insight from financial_insights["insights"] and every insight from
sales_crm_insights["insights"] as-is. Include them all in the final report.

Step 3 — Check for cross-domain compound risks.
Look at ALL insights collected from both domains and apply these compound rules:
- revenue_growth flagged AND churn_rate flagged
    → risk_type: compound_revenue_pressure, severity: high
- cash_flow flagged AND deal_velocity flagged
    → risk_type: cash_flow_pipeline_risk, severity: high
- burn_rate flagged AND conversion_rate flagged
    → risk_type: cost_pressure_weak_pipeline, severity: high
- outstanding_invoices flagged AND incoming_leads flagged
    → risk_type: receivables_pipeline_risk, severity: medium

A metric is "flagged" if it appears in either domain's insights list.
Only add compound insights that are actually triggered.

Step 4 — Determine final_severity.
final_severity is the highest severity level found across ALL insights
(domain-level and cross-domain combined).
If there are no insights at all, final_severity is "low".

Step 5 — Write a one-sentence executive summary describing the overall situation.

CRITICAL: Return ONLY raw JSON. Do NOT wrap in ```json or ``` code fences.
Do NOT add any explanation before or after the JSON.
The very first character of your response must be { and the very last must be }.

Use exactly this structure:

{
  "agent": "insight_synthesis_agent",
  "status": "success",
  "tenant_id": "pulse-demo",
  "final_severity": "<low|medium|high>",
  "summary": "<one sentence describing the overall business situation>",
  "domain_insights": {
    "financial": [
      {
        "metric_name": "<metric_name>",
        "severity": "<low|medium|high>",
        "trend": "<increasing|decreasing|stable|volatile>",
        "insight": "<insight text>",
        "recommendation": "<recommendation text>"
      }
    ],
    "sales_crm": [
      {
        "metric_name": "<metric_name>",
        "severity": "<low|medium|high>",
        "trend": "<increasing|decreasing|stable|volatile>",
        "insight": "<insight text>",
        "recommendation": "<recommendation text>"
      }
    ]
  },
  "cross_domain_insights": [
    {
      "risk_type": "<snake_case risk label>",
      "severity": "<low|medium|high>",
      "insight": "<one sentence describing the compound risk>",
      "recommendation": "<one concrete action>",
      "related_metrics": ["<metric1>", "<metric2>"]
    }
  ]
}

If a domain has no insights, its array must be [] (empty, not omitted).
If no compound rules trigger, cross_domain_insights must be [] (empty, not omitted).
""",
    generate_content_config=types.GenerateContentConfig(
        temperature=0.1,
        max_output_tokens=6000,
        response_mime_type="application/json",
        http_options=types.HttpOptions(
            retry_options=types.HttpRetryOptions(
                initial_delay=1.0,
                attempts=5,
                http_status_codes=[408, 429, 500, 502, 503, 504],
            ),
            timeout=120 * 1000,
        ),
    ),
    output_key="synthesized_insights",
)
