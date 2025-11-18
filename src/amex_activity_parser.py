import re
import csv
import sys
from pathlib import Path
from typing import List, Dict


DATE_INLINE_RE = re.compile(r"^(\d{1,2}\s+[A-Za-z]{3})\b(.*)$")
DATE_DASH_RE = re.compile(r"^(\d{1,2}-[A-Za-z]{3}-)(\d{4})?\s*$")


def _is_date_line(line: str) -> bool:
    """Return True if the line looks like a date row from Amex activity.

    Handles patterns like:
    - "18 Nov"
    - "18 Nov PAYU SWIGGY"
    - "31-Dec-" (followed by a year on next line)
    - "31-Dec-2024"
    """
    s = line.strip()
    if not s:
        return False

    if DATE_INLINE_RE.match(s):
        return True
    if DATE_DASH_RE.match(s):
        return True

    return False


def _split_into_blocks(lines: List[str]) -> List[List[str]]:
    """Group raw lines into logical transaction blocks based on date lines."""
    blocks: List[List[str]] = []
    current: List[str] = []

    for raw in lines:
        line = raw.rstrip("\n")
        s = line.strip()
        if not s:
            continue

        # Skip global headers/footers that are not part of transactions
        lower = s.lower()
        if s.startswith("Card Activity from"):
            continue
        if s.startswith("Transactions ") and "Transactions" in s:
            continue
        if s.startswith("DATE DESCRIPTION AMOUNT"):
            continue
        if s.startswith("ACCOUNT ENDING -"):
            continue
        if s.startswith("American Express"):
            continue
        if s.startswith("Summary"):
            continue
        if s.startswith("Payments & Credits"):
            continue
        if s.startswith("New Charges") or s.startswith("Total "):
            continue
        if s.endswith("activity/search?from=2024-10-01&to=2025-11-19"):
            # Page footer with URL
            continue

        if _is_date_line(s):
            # start of a new block
            if current:
                blocks.append(current)
            current = [s]
        else:
            if current:
                current.append(s)
            # else lines before the first date are ignored

    if current:
        blocks.append(current)

    return blocks


def _parse_amount_line(line: str) -> float:
    """Extract signed amount from a line containing a rupee amount."""
    m = re.search(r"(-?)₹\s*([\d,]+(?:\.\d+)?)", line)
    if not m:
        raise ValueError(f"No amount found in line: {line!r}")
    sign = -1.0 if m.group(1) == '-' else 1.0
    value = float(m.group(2).replace(',', ''))
    return sign * value


def _parse_block(block: List[str]) -> Dict:
    """Parse a single transaction block into a structured dict.

    Returns dict with keys: date, name, description, amount.
    Returns None-like (raises) if block cannot be parsed.
    """
    if not block:
        raise ValueError("Empty block")

    # Handle date + optional inline name on the first line
    first = block[0].strip()

    # Special case: date split like "31-Dec-" and next line is year
    m_dash = DATE_DASH_RE.match(first)
    if m_dash:
        base = m_dash.group(1)  # e.g. "31-Dec-"
        # try to read year from next line if it is 4 digits
        if len(block) > 1 and block[1].strip().isdigit() and len(block[1].strip()) == 4:
            year = block[1].strip()
            date_str = f"{base}{year}"
            idx = 2
        else:
            date_str = base.rstrip('-')
            idx = 1

        # Next line may be "Credit"; skip it for the name
        if idx < len(block) and block[idx].strip().lower() == "credit":
            idx += 1

        name_line = block[idx].strip() if idx < len(block) else ""
        content_start = idx + 1
    else:
        m = DATE_INLINE_RE.match(first)
        if not m:
            raise ValueError(f"First line does not look like a date: {first!r}")
        date_part, rest = m.group(1), m.group(2).strip()
        date_str = date_part

        if rest:
            name_line = rest
            content_start = 1
        else:
            # Name is on the next line, possibly after a "Credit" marker
            idx = 1
            if idx < len(block) and block[idx].strip().lower() == "credit":
                idx += 1
            name_line = block[idx].strip() if idx < len(block) else ""
            content_start = idx + 1

    # Find description: last line before "Will appear on your"
    description = name_line
    for idx in range(content_start, len(block)):
        if "Will appear on your" in block[idx]:
            if idx - 1 >= content_start:
                description = block[idx - 1].strip()
            break

    upper_name = name_line.upper()
    upper_desc = description.upper()

    # Drop pure card-payment rows
    if "PAYMENT RECEIVED" in upper_name or "PAYMENT RECEIVED" in upper_desc:
        raise ValueError("Payment received row; skip")

    # Find amount line: last line containing the rupee symbol
    amount_line = None
    for ln in reversed(block):
        if "₹" in ln:
            amount_line = ln
            break
    if not amount_line:
        raise ValueError("No amount line in block")

    amount = _parse_amount_line(amount_line)

    return {
        "date": date_str.strip(),
        "name": name_line.strip(),
        "description": description.strip(),
        "amount": amount,
    }


def parse_amex_activity(text: str, debug: bool = False) -> List[Dict]:
    """Parse raw Amex activity text into a list of transactions.

    The input should be the full copied text from the Amex activity page
    for a given date range.

    When debug=True, also report how many blocks were skipped and why.
    """
    lines = text.splitlines()
    blocks = _split_into_blocks(lines)

    transactions: List[Dict] = []
    skipped: List[Dict] = []

    for idx, block in enumerate(blocks):
        try:
            tx = _parse_block(block)
            transactions.append(tx)
        except ValueError as e:
            if debug:
                # Try to infer an amount even for skipped blocks
                amount_line = None
                for ln in reversed(block):
                    if "₹" in ln:
                        amount_line = ln
                        break
                inferred_amount = None
                if amount_line is not None:
                    try:
                        inferred_amount = _parse_amount_line(amount_line)
                    except Exception:
                        inferred_amount = None

                skipped.append({
                    "index": idx,
                    "reason": str(e),
                    "first_line": block[0].strip() if block else "",
                    "amount": inferred_amount,
                })
            continue

    if debug:
        total_blocks = len(blocks)
        print(f"DEBUG: total blocks detected: {total_blocks}")
        print(f"DEBUG: parsed transactions: {len(transactions)}")
        print(f"DEBUG: skipped blocks: {len(skipped)}")

        # Aggregate skipped amounts by reason
        by_reason = {}
        for s in skipped:
            amt = s["amount"] or 0.0
            by_reason.setdefault(s["reason"], 0.0)
            by_reason[s["reason"]] += amt

        if skipped:
            print("DEBUG: skipped summary by reason:")
            for reason, amt in by_reason.items():
                print(f"  - {reason}: {amt:.2f}")

            print("DEBUG: first few skipped blocks:")
            for s in skipped[:10]:
                print(f"  [#{s['index']}] {s['first_line']} | reason={s['reason']} | amount={s['amount']}")

    return transactions


def export_amex_to_csv(input_path: Path, output_path: Path) -> None:
    """Read raw Amex activity text and write a CSV suitable for Excel.

    CSV columns: Date, Name, Description, Amount
    """
    raw = input_path.read_text(encoding="utf-8")
    transactions = parse_amex_activity(raw, debug=True)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Date", "Name", "Description", "Amount"])
        for tx in transactions:
            writer.writerow([
                tx["date"],
                tx["name"],
                tx["description"],
                f"{tx['amount']:.2f}",
            ])

    total = sum(t["amount"] for t in transactions)
    debits = sum(t["amount"] for t in transactions if t["amount"] > 0)
    credits = sum(t["amount"] for t in transactions if t["amount"] < 0)

    print(f"Parsed {len(transactions)} transactions.")
    print(f"Total debits (spend): {debits:.2f}")
    print(f"Total credits (refunds/adjustments): {credits:.2f}")
    print(f"Net amount: {total:.2f}")
    print(f"CSV written to: {output_path}")


def main(argv: List[str]) -> None:
    if len(argv) >= 2:
        in_path = Path(argv[1])
    else:
        in_path = Path("data/amex_activity.txt")

    if len(argv) >= 3:
        out_path = Path(argv[2])
    else:
        out_path = Path("data/amex_activity_parsed.csv")

    if not in_path.exists():
        print(f"Input file not found: {in_path}")
        print("Create the file and paste your Amex activity text into it.")
        return

    export_amex_to_csv(in_path, out_path)


if __name__ == "__main__":
    main(sys.argv)
