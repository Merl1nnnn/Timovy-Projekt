"""Refresh the local analytics snapshot from ECB reference rates."""

import json
import math
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

SOURCE = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
DESTINATION = Path(__file__).resolve().parents[1] / "frontend/data/exchange-rates.json"


def parse_rates(xml):
    root = ET.fromstring(xml)
    day = next(node for node in root.iter() if "time" in node.attrib)
    snapshot_date = date.fromisoformat(day.attrib["time"]).isoformat()
    rates = {"EUR": 1.0}
    for node in day:
        currency = node.attrib.get("currency", "")
        rate = float(node.attrib.get("rate", "nan"))
        if not re.fullmatch(r"[A-Z]{3}", currency) or not math.isfinite(rate) or rate <= 0:
            raise ValueError("Invalid ECB currency rate")
        rates[currency] = rate
    if len(rates) < 2:
        raise ValueError("Empty ECB reference rates")
    return {"date": snapshot_date, "base": "EUR", "source": SOURCE, "rates": rates}


def main():
    with urllib.request.urlopen(SOURCE, timeout=30) as response:
        snapshot = parse_rates(response.read())
    temporary = DESTINATION.with_suffix(".tmp")
    temporary.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    temporary.replace(DESTINATION)
    print(f"ECB {snapshot['date']}: {len(snapshot['rates'])} currencies → {DESTINATION}")


if __name__ == "__main__":
    main()
