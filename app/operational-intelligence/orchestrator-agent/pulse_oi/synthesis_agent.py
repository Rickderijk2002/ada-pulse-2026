from __future__ import annotations

from google.adk.agents.llm_agent import LlmAgent
from google.genai import types

# No MCP tools — synthesis agent reasons only on the outputs
# of the financial and sales agents, which ADK passes via
# output_key substitution in the instruction template.

synthesis_agent = LlmAgent(
    name="InsightSynthesisAgent",
    model="gemini-2.5-flash",
    description="Combines financial and sales insights into a cross-domain insight payload.",
    instruction="""
You are a cross-domain business analyst for an SME called Pulse.

You have received the results of two specialist analysts:

Financial insights:
{financial_insights}

Sales/CRM insights:
{sales_crm_insights}

Your task:
1. Read both sets of insights carefully.
2. Detect compound cross-domain risks where a signal from the financial domain and a signal
   from the sales/CRM domain reinforce each other.
3. Determine the final_severity: the highest severity level found across ALL insights
   (both domain-level and cross-domain).

Apply these cross-domain compound rules:
- revenue_growth negative AND churn_rate increasing
    → risk_type: compound_revenue_pressure → severity: high
- cash_flow negative AND deal_velocity decreasing
    → risk_type: cash_flow_pipeline_risk → severity: high
- burn_rate increasing AND conversion_rate decreasing
    → risk_type: cost_pressure_weak_pipeline → severity: high
- outstanding_invoices increasing AND incoming_leads decreasing
    → risk_type: receivables_pipeline_risk → severity: medium

If none of the compound rules are triggered, return an empty synthesized_insights list.

Return ONLY a valid JSON object — no explanation text, no markdown, no code fences.
Use exactly this structure:

{
  "agent": "insight_synthesis_agent",
  "status": "success",
  "synthesized_insights": [
    {
      "domain": "cross_domain",
      "severity": "<low|medium|high>",
      "risk_type": "<snake_case label from the rules above>",
      "insight": "<one sentence describing the compound risk>",
      "recommendation": "<one concrete action>",
      "related_metrics": ["<metric1>", "<metric2>"]
    }
  ],
  "final_severity": "<low|medium|high>"
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
    output_key="synthesized_insights",
)
