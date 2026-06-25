#!/usr/bin/env python3
"""Step 3: Card Approval Data Extraction.

Extracts transaction data from card approval file.
Handles both .xlsx (openpyxl) and .xls (xlrd) formats.
"""

import json
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
RESEARCH_DIR = PROJECT_DIR / "research"


def extract_xlsx(filepath):
    """Extract from .xlsx using openpyxl."""
    import openpyxl
    wb = openpyxl.load_workbook(filepath, data_only=True, read_only=True)
    ws = wb.active

    records = []
    header_row = None

    for row in ws.iter_rows(values_only=False):
        values = [c.value for c in row]
        # Find header row
        if header_row is None:
            for i, v in enumerate(values):
                if v and isinstance(v, str):
                    v_nfc = unicodedata.normalize("NFC", v)
                    if "승인일자" in v_nfc or "승인날짜" in v_nfc or "거래일자" in v_nfc or "이용일" in v_nfc:
                        header_row = {unicodedata.normalize("NFC", str(cell.value).strip()): idx
                                     for idx, cell in enumerate(row) if cell.value}
                        break
            continue

        if not any(values):
            continue

        # Extract fields based on header mapping
        record = {}
        for key, idx in header_row.items():
            if idx < len(values):
                record[key] = values[idx]

        # Normalize to standard fields
        normalized = normalize_record(record)
        if normalized:
            records.append(normalized)

    wb.close()
    return records


def extract_xls(filepath):
    """Extract from .xls using xlrd."""
    import xlrd
    wb = xlrd.open_workbook(filepath)
    ws = wb.sheet_by_index(0)

    records = []
    header_row = None

    for rx in range(ws.nrows):
        values = [ws.cell_value(rx, cx) for cx in range(ws.ncols)]

        if header_row is None:
            for i, v in enumerate(values):
                if v and isinstance(v, str):
                    v_nfc = unicodedata.normalize("NFC", v)
                    if "승인일자" in v_nfc or "승인날짜" in v_nfc or "거래일자" in v_nfc or "이용일" in v_nfc:
                        header_row = {}
                        for cx in range(ws.ncols):
                            cv = ws.cell_value(rx, cx)
                            if cv:
                                header_row[unicodedata.normalize("NFC", str(cv).strip())] = cx
                        break
            continue

        if not any(values):
            continue

        record = {}
        for key, idx in header_row.items():
            if idx < len(values):
                record[key] = values[idx]

        normalized = normalize_record(record)
        if normalized:
            records.append(normalized)

    return records


def normalize_record(record):
    """Normalize record to standard format: date, time, amount."""
    date_val = None
    time_val = None
    amount_val = None

    # Date fields
    for key in ["승인일자", "승인날짜", "거래일자", "이용일", "이용일자"]:
        if key in record and record[key]:
            date_val = parse_date(record[key])
            break

    # Time fields
    for key in ["승인시간", "거래시간", "이용시간"]:
        if key in record and record[key]:
            time_val = parse_time(record[key])
            break

    # Amount fields
    for key in ["거래금액", "이용금액", "승인금액", "승인금액(원화)", "이용금액(원)"]:
        if key in record and record[key]:
            amount_val = parse_amount(record[key])
            break

    if date_val and amount_val:
        return {
            "date": date_val,
            "time": time_val or "00:00:00",
            "amount": amount_val,
            "raw": {k: str(v) for k, v in record.items() if v}
        }
    return None


def parse_date(val):
    """Parse date to YYYY-MM-DD format."""
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d")
    s = str(val).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y%m%d"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return s


def parse_time(val):
    """Parse time to HH:MM:SS format."""
    if isinstance(val, datetime):
        return val.strftime("%H:%M:%S")
    s = str(val).strip()
    # Handle HHMM or HH:MM or HH:MM:SS
    s = s.replace(":", "")
    if len(s) == 4:
        return f"{s[:2]}:{s[2:4]}:00"
    elif len(s) == 6:
        return f"{s[:2]}:{s[2:4]}:{s[4:6]}"
    return s


def parse_amount(val):
    """Parse amount to integer."""
    if isinstance(val, (int, float)):
        return int(val)
    s = str(val).strip().replace(",", "").replace("원", "").replace("₩", "")
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return None


def main():
    # Load manifest
    manifest_file = RESEARCH_DIR / "input-manifest.json"
    with open(manifest_file, 'r', encoding='utf-8') as f:
        manifest = json.load(f)

    card_file = manifest.get("card_approval_file")
    card_format = manifest.get("card_format")

    if not card_file:
        print("WARNING: No card approval file found. Creating empty data.", file=sys.stderr)
        output = {"records": [], "source": None}
    else:
        card_path = Path(card_file)
        print(f"Processing: {card_path.name} (format: {card_format})")

        if card_format == ".xlsx":
            records = extract_xlsx(card_path)
        elif card_format == ".xls":
            records = extract_xls(card_path)
        else:
            print(f"ERROR: Unknown format {card_format}", file=sys.stderr)
            sys.exit(1)

        output = {
            "records": records,
            "source": str(card_path),
            "count": len(records),
        }
        print(f"Extracted {len(records)} records")

    # Save output
    output_file = RESEARCH_DIR / "card-approval-data.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Output: {output_file}")
    print("Step 3 complete.")


if __name__ == "__main__":
    main()
