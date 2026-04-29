from __future__ import annotations

import csv
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


BASE_DIR = Path(__file__).resolve().parents[1]
INPUT_DIR = BASE_DIR / "data" / "mockaroo"
OUTPUT_DIR = BASE_DIR / "data" / "ingest"

INPUT_SALES = INPUT_DIR / "Sales & Marketing.csv"
INPUT_FINANCIAL = INPUT_DIR / "Financial_data.csv"

OUTPUT_SALES = OUTPUT_DIR / "sales_marketing_clean.csv"
OUTPUT_FINANCIAL = OUTPUT_DIR / "financial_clean.csv"

TENANT_ID = "pulse-demo"


@dataclass
class SalesRow:
    date: str
    tenant_id: str
    campaign_spend: Decimal
    website_visits: int
    leads: int
    qualified_leads: int
    new_deals: int
    pipeline_value: Decimal
    churn_rate: Decimal


@dataclass
class FinancialRow:
    date: str
    tenant_id: str
    revenue: Decimal
    expenses: Decimal
    cash_inflow: Decimal
    cash_outflow: Decimal
    outstanding_invoices: Decimal


def parse_date(value: str) -> str:
    return datetime.strptime(value.strip(), "%Y-%m-%d").date().isoformat()


def to_decimal(value: str) -> Decimal:
    return Decimal(value.strip())


def to_non_negative_decimal(value: str) -> Decimal:
    return max(Decimal("0"), to_decimal(value))


def to_non_negative_int(value: str) -> int:
    return max(0, int(Decimal(value.strip())))


def clamp_ratio(value: str) -> Decimal:
    try:
        parsed = Decimal(value.strip())
    except (InvalidOperation, AttributeError):
        return Decimal("0")
    if parsed < 0:
        return Decimal("0")
    if parsed > 1:
        return Decimal("1")
    return parsed


def load_csv(path: Path) -> List[Dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as file_handle:
        return list(csv.DictReader(file_handle))


def clean_sales(rows: Iterable[Dict[str, str]]) -> List[SalesRow]:
    cleaned: List[SalesRow] = []
    for row in rows:
        try:
            event_date = parse_date(row["date"])
            leads = to_non_negative_int(row["leads"])
            qualified = min(to_non_negative_int(row["qualified_leads"]), leads)
            deals = min(to_non_negative_int(row["new_deals"]), qualified)
            cleaned.append(
                SalesRow(
                    date=event_date,
                    tenant_id=TENANT_ID,
                    campaign_spend=to_non_negative_decimal(row["campaign_spend"]),
                    website_visits=to_non_negative_int(row["website_visits"]),
                    leads=leads,
                    qualified_leads=qualified,
                    new_deals=deals,
                    pipeline_value=to_non_negative_decimal(row["pipeline_value"]),
                    churn_rate=clamp_ratio(row["churn_rate"]),
                )
            )
        except (KeyError, ValueError, InvalidOperation) as error:
            logger.warning("Skipping malformed sales row: %s", error)
    return cleaned


def clean_financial(rows: Iterable[Dict[str, str]]) -> List[FinancialRow]:
    cleaned: List[FinancialRow] = []
    for row in rows:
        try:
            cleaned.append(
                FinancialRow(
                    date=parse_date(row["date"]),
                    tenant_id=TENANT_ID,
                    revenue=to_non_negative_decimal(row["revenue"]),
                    expenses=to_non_negative_decimal(row["expenses"]),
                    cash_inflow=to_non_negative_decimal(row["cash_inflow"]),
                    cash_outflow=to_non_negative_decimal(row["cash_outflow"]),
                    outstanding_invoices=to_non_negative_decimal(
                        row["outstanding_invoices"]
                    ),
                )
            )
        except (KeyError, ValueError, InvalidOperation) as error:
            logger.warning("Skipping malformed financial row: %s", error)
    return cleaned


def aggregate_sales(rows: Iterable[SalesRow]) -> List[Dict[str, str]]:
    grouped: Dict[Tuple[str, str], Dict[str, Decimal]] = defaultdict(
        lambda: {
            "campaign_spend": Decimal("0"),
            "website_visits": Decimal("0"),
            "leads": Decimal("0"),
            "qualified_leads": Decimal("0"),
            "new_deals": Decimal("0"),
            "pipeline_value": Decimal("0"),
            "churn_weighted_sum": Decimal("0"),
        }
    )

    for row in rows:
        key = (row.date, row.tenant_id)
        target = grouped[key]
        target["campaign_spend"] += row.campaign_spend
        target["website_visits"] += Decimal(row.website_visits)
        target["leads"] += Decimal(row.leads)
        target["qualified_leads"] += Decimal(row.qualified_leads)
        target["new_deals"] += Decimal(row.new_deals)
        target["pipeline_value"] += row.pipeline_value
        target["churn_weighted_sum"] += row.churn_rate * Decimal(max(row.leads, 1))

    output: List[Dict[str, str]] = []
    for (event_date, tenant_id), agg in sorted(grouped.items()):
        leads = int(agg["leads"])
        deals = int(agg["new_deals"])
        churn_rate = (
            agg["churn_weighted_sum"] / Decimal(leads) if leads > 0 else Decimal("0")
        )
        conversion_rate = (
            (Decimal(deals) / Decimal(leads)) if leads > 0 else Decimal("0")
        )
        output.append(
            {
                "date": event_date,
                "tenant_id": tenant_id,
                "campaign_spend": f"{agg['campaign_spend']:.2f}",
                "website_visits": str(int(agg["website_visits"])),
                "leads": str(leads),
                "qualified_leads": str(int(agg["qualified_leads"])),
                "new_deals": str(deals),
                "pipeline_value": f"{agg['pipeline_value']:.2f}",
                "churn_rate": f"{churn_rate:.4f}",
                "conversion_rate": f"{conversion_rate:.4f}",
            }
        )
    return output


def aggregate_financial(rows: Iterable[FinancialRow]) -> List[Dict[str, str]]:
    grouped: Dict[Tuple[str, str], Dict[str, Decimal]] = defaultdict(
        lambda: {
            "revenue": Decimal("0"),
            "expenses": Decimal("0"),
            "cash_inflow": Decimal("0"),
            "cash_outflow": Decimal("0"),
            "outstanding_invoices": Decimal("0"),
        }
    )

    for row in rows:
        key = (row.date, row.tenant_id)
        target = grouped[key]
        target["revenue"] += row.revenue
        target["expenses"] += row.expenses
        target["cash_inflow"] += row.cash_inflow
        target["cash_outflow"] += row.cash_outflow
        target["outstanding_invoices"] += row.outstanding_invoices

    output: List[Dict[str, str]] = []
    for (event_date, tenant_id), agg in sorted(grouped.items()):
        profit = agg["revenue"] - agg["expenses"]
        output.append(
            {
                "date": event_date,
                "tenant_id": tenant_id,
                "revenue": f"{agg['revenue']:.2f}",
                "expenses": f"{agg['expenses']:.2f}",
                "cash_inflow": f"{agg['cash_inflow']:.2f}",
                "cash_outflow": f"{agg['cash_outflow']:.2f}",
                "outstanding_invoices": f"{agg['outstanding_invoices']:.2f}",
                "profit": f"{profit:.2f}",
            }
        )
    return output


def write_csv(path: Path, rows: List[Dict[str, str]]) -> None:
    if not rows:
        raise ValueError(f"No rows to write for {path}")
    with path.open("w", newline="", encoding="utf-8") as file_handle:
        writer = csv.DictWriter(file_handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    sales_raw = load_csv(INPUT_SALES)
    financial_raw = load_csv(INPUT_FINANCIAL)

    cleaned_sales = clean_sales(sales_raw)
    cleaned_financial = clean_financial(financial_raw)

    sales_aggregated = aggregate_sales(cleaned_sales)
    financial_aggregated = aggregate_financial(cleaned_financial)

    write_csv(OUTPUT_SALES, sales_aggregated)
    write_csv(OUTPUT_FINANCIAL, financial_aggregated)

    logger.info("Created %s rows -> %s", len(sales_aggregated), OUTPUT_SALES)
    logger.info("Created %s rows -> %s", len(financial_aggregated), OUTPUT_FINANCIAL)


if __name__ == "__main__":
    main()
