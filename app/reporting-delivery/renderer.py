from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from jinja2 import Environment

HERE = Path(__file__).parent

_SEVERITY_COLOR = {"high": "#dc2626", "medium": "#d97706", "low": "#16a34a"}
_TREND_ARROW = {"increasing": "↑", "decreasing": "↓", "stable": "→", "volatile": "~"}

TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Pulse Operational Intelligence Report</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    background: #f0f4f8;
    color: #1e293b;
    font-size: 15px;
    line-height: 1.6;
  }
  /* ── Header ── */
  .header {
    background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 100%);
    color: #fff;
    padding: 36px 48px 32px;
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 24px;
  }
  .header-brand { display: flex; align-items: center; gap: 14px; }
  .header-logo {
    width: 44px; height: 44px; border-radius: 10px;
    background: #3b82f6;
    display: flex; align-items: center; justify-content: center;
    font-weight: 800; font-size: 20px; color: #fff; flex-shrink: 0;
  }
  .header-title { font-size: 22px; font-weight: 700; letter-spacing: -0.3px; }
  .header-sub { font-size: 13px; color: #93c5fd; margin-top: 2px; }
  .header-meta { text-align: right; }
  .header-meta .tenant { font-size: 14px; color: #cbd5e1; }
  .header-meta .run-date { font-size: 13px; color: #64748b; margin-top: 4px; }
  /* ── Severity badge ── */
  .badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: #fff;
  }
  .badge-high   { background: #dc2626; }
  .badge-medium { background: #d97706; }
  .badge-low    { background: #16a34a; }
  .header-severity { margin-top: 10px; display: flex; align-items: center; gap: 8px; }
  .header-severity span { font-size: 13px; color: #94a3b8; }
  .badge-large { font-size: 14px; padding: 5px 16px; }
  /* ── Layout ── */
  .container { max-width: 960px; margin: 0 auto; padding: 40px 24px 60px; }
  /* ── Summary ── */
  .summary-card {
    background: #fff;
    border-left: 5px solid #3b82f6;
    border-radius: 8px;
    padding: 20px 24px;
    margin-bottom: 36px;
    box-shadow: 0 1px 4px rgba(0,0,0,.07);
  }
  .summary-card h2 { font-size: 13px; text-transform: uppercase; letter-spacing: 0.7px; color: #64748b; margin-bottom: 8px; }
  .summary-card p { font-size: 15px; color: #1e293b; }
  /* ── Section ── */
  .section { margin-bottom: 40px; }
  .section-title {
    font-size: 16px; font-weight: 700; color: #0f172a;
    border-bottom: 2px solid #e2e8f0;
    padding-bottom: 10px; margin-bottom: 18px;
    display: flex; align-items: center; gap: 8px;
  }
  .section-title .dot {
    width: 10px; height: 10px; border-radius: 50%; background: #3b82f6; flex-shrink: 0;
  }
  /* ── Insight cards ── */
  .cards { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
  @media (max-width: 640px) { .cards { grid-template-columns: 1fr; } }
  .card {
    background: #fff;
    border-radius: 10px;
    padding: 18px 20px;
    box-shadow: 0 1px 4px rgba(0,0,0,.08);
    border-top: 4px solid #e2e8f0;
  }
  .card-high   { border-top-color: #dc2626; }
  .card-medium { border-top-color: #d97706; }
  .card-low    { border-top-color: #16a34a; }
  .card-header {
    display: flex; align-items: center; justify-content: space-between;
    margin-bottom: 10px; gap: 8px;
  }
  .card-metric {
    font-weight: 700; font-size: 14px; color: #0f172a;
    text-transform: replace; letter-spacing: 0;
  }
  .card-right { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
  .trend-arrow { font-size: 18px; font-weight: 700; line-height: 1; }
  .trend-increasing { color: #dc2626; }
  .trend-decreasing { color: #16a34a; }
  .trend-stable     { color: #64748b; }
  .trend-volatile   { color: #d97706; }
  .card-insight { font-size: 13.5px; color: #334155; margin-bottom: 10px; }
  .card-rec-label { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.6px; color: #64748b; margin-bottom: 3px; }
  .card-rec { font-size: 13px; color: #475569; }
  /* ── Cross-domain risk cards ── */
  .risk-card {
    background: #fffbeb;
    border: 1px solid #fcd34d;
    border-left: 5px solid #d97706;
    border-radius: 10px;
    padding: 18px 22px;
    margin-bottom: 14px;
    box-shadow: 0 1px 4px rgba(0,0,0,.05);
  }
  .risk-card-high { border-left-color: #dc2626; background: #fff5f5; border-color: #fca5a5; }
  .risk-card-header { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
  .risk-type { font-weight: 700; font-size: 14px; color: #0f172a; }
  .risk-insight { font-size: 13.5px; color: #334155; margin-bottom: 10px; }
  .risk-rec-label { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.6px; color: #64748b; margin-bottom: 3px; }
  .risk-rec { font-size: 13px; color: #475569; margin-bottom: 10px; }
  .risk-metrics { display: flex; gap: 8px; flex-wrap: wrap; }
  .metric-pill {
    background: #e2e8f0; color: #334155;
    font-size: 11px; font-weight: 600;
    padding: 2px 9px; border-radius: 999px;
    font-family: monospace;
  }
  /* ── Empty state ── */
  .empty { font-size: 13px; color: #94a3b8; font-style: italic; padding: 12px 0; }
  /* ── Footer ── */
  .footer {
    margin-top: 48px; text-align: center;
    font-size: 12px; color: #94a3b8;
  }
</style>
</head>
<body>

<header class="header">
  <div>
    <div class="header-brand">
      <div class="header-logo">P</div>
      <div>
        <div class="header-title">Pulse Operational Intelligence</div>
        <div class="header-sub">Automated KPI Analysis Report</div>
      </div>
    </div>
    <div class="header-severity">
      <span>Overall severity:</span>
      <span class="badge badge-large badge-{{ final_severity }}">{{ final_severity }}</span>
    </div>
  </div>
  <div class="header-meta">
    <div class="tenant">Tenant: <strong>{{ tenant_id }}</strong></div>
    <div class="run-date">Generated: {{ report_date }}</div>
    {% if run_id %}<div class="run-date">Run ID: {{ run_id }}</div>{% endif %}
  </div>
</header>

<div class="container">

  <div class="summary-card">
    <h2>Executive Summary</h2>
    <p>{{ summary }}</p>
  </div>

  <!-- Financial insights -->
  <div class="section">
    <div class="section-title"><span class="dot"></span>Financial Insights</div>
    {% if financial %}
    <div class="cards">
      {% for item in financial %}
      <div class="card card-{{ item.severity }}">
        <div class="card-header">
          <span class="card-metric">{{ item.metric_name | replace("_", " ") | title }}</span>
          <div class="card-right">
            <span class="trend-arrow trend-{{ item.trend }}">{{ item.trend | trend_arrow }}</span>
            <span class="badge badge-{{ item.severity }}">{{ item.severity }}</span>
          </div>
        </div>
        <p class="card-insight">{{ item.insight }}</p>
        <div class="card-rec-label">Recommendation</div>
        <p class="card-rec">{{ item.recommendation }}</p>
      </div>
      {% endfor %}
    </div>
    {% else %}
    <p class="empty">No financial risks detected.</p>
    {% endif %}
  </div>

  <!-- Sales & CRM insights -->
  <div class="section">
    <div class="section-title"><span class="dot" style="background:#8b5cf6;"></span>Sales &amp; CRM Insights</div>
    {% if sales_crm %}
    <div class="cards">
      {% for item in sales_crm %}
      <div class="card card-{{ item.severity }}">
        <div class="card-header">
          <span class="card-metric">{{ item.metric_name | replace("_", " ") | title }}</span>
          <div class="card-right">
            <span class="trend-arrow trend-{{ item.trend }}">{{ item.trend | trend_arrow }}</span>
            <span class="badge badge-{{ item.severity }}">{{ item.severity }}</span>
          </div>
        </div>
        <p class="card-insight">{{ item.insight }}</p>
        <div class="card-rec-label">Recommendation</div>
        <p class="card-rec">{{ item.recommendation }}</p>
      </div>
      {% endfor %}
    </div>
    {% else %}
    <p class="empty">No sales/CRM risks detected.</p>
    {% endif %}
  </div>

  <!-- Cross-domain risks -->
  <div class="section">
    <div class="section-title"><span class="dot" style="background:#ef4444;"></span>Cross-Domain Risks</div>
    {% if cross_domain %}
    {% for risk in cross_domain %}
    <div class="risk-card risk-card-{{ risk.severity }}">
      <div class="risk-card-header">
        <span class="risk-type">{{ risk.risk_type | replace("_", " ") | title }}</span>
        <span class="badge badge-{{ risk.severity }}">{{ risk.severity }}</span>
      </div>
      <p class="risk-insight">{{ risk.insight }}</p>
      <div class="risk-rec-label">Recommendation</div>
      <p class="risk-rec">{{ risk.recommendation }}</p>
      <div class="risk-metrics">
        {% for m in risk.related_metrics %}
        <span class="metric-pill">{{ m }}</span>
        {% endfor %}
      </div>
    </div>
    {% endfor %}
    {% else %}
    <p class="empty">No cross-domain compound risks detected.</p>
    {% endif %}
  </div>

</div>

<footer class="footer">
  <p>Pulse &mdash; Operational Intelligence &mdash; {{ report_date }}</p>
</footer>

</body>
</html>"""


def _trend_arrow(trend: str) -> str:
    return _TREND_ARROW.get(trend, "")


def render(insights_path: Path, output_path: Path) -> None:
    data = json.loads(insights_path.read_text(encoding="utf-8"))

    # Support both flat and nested structures from the pipeline
    insights = data.get("insights", data)

    env = Environment(autoescape=True)
    env.filters["trend_arrow"] = _trend_arrow

    tmpl = env.from_string(TEMPLATE)
    html = tmpl.render(
        run_id=data.get("run_id", ""),
        tenant_id=insights.get("tenant_id", data.get("tenant_id", "")),
        final_severity=insights.get("final_severity", "low"),
        summary=insights.get("summary", ""),
        financial=insights.get("domain_insights", {}).get("financial", []),
        sales_crm=insights.get("domain_insights", {}).get("sales_crm", []),
        cross_domain=insights.get("cross_domain_insights", []),
        report_date=date.today().isoformat(),
    )
    output_path.write_text(html, encoding="utf-8")
    print(f"Report written to {output_path}")


if __name__ == "__main__":
    render(HERE / "sample_insights.json", HERE / "report.html")
