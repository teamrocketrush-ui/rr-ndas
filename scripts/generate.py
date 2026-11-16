#!/usr/bin/env python3
"""RocketRush NDA generator.

Fills template.html with a client's details, writes ndas/{key}.html and registers
the NDA in ndas.json. Standard library only.

Example:
  python3 scripts/generate.py \
      --company "Cautilya Wealth and Education Pvt Ltd." \
      --address "Flat No.: 331, Shastri Nagar, Bengaluru, Karnataka 560070" \
      --gst 29AAMCC5686K1ZT --signatory "Authorised Signatory" \
      --purpose "LinkedIn Personal Branding" --date "22nd May 2026" --place Noida
"""
import argparse, html, json, re, secrets, sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Rocket Rush Partners (always the Receiving Party). Single source of truth for every NDA.
RR_ADDRESS = "A-23, NAVADA, PRAGATI KUNJ, ANAND VAN PHASE 2, Aduki, PO, DIST: Mathura, Uttar Pradesh - 281006"
RR_GST = "09ABLFR1598J1ZG"
RR_PAN = "ABLFR1598J"
DEFAULT_PLACE = "Mathura"  # default place of execution for every new NDA
BASE_URL = "https://teamrocketrush-ui.github.io/rr-ndas/ndas/"
LEGAL_SUFFIXES = {"pvt", "private", "ltd", "limited", "llp", "inc", "incorporated", "llc",
                  "corp", "corporation", "co", "company", "opc", "fze", "plc"}


def ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        return f"{n}th"
    return f"{n}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th') }"


def today_text() -> str:
    d = datetime.now()
    return f"{ordinal(d.day)} {d.strftime('%B %Y')}"


def make_key(company: str) -> str:
    """'Alphastar Technologies Private Limited' -> 'alphastar-technologies'."""
    words = re.sub(r"[^a-z0-9\s-]", " ", company.lower()).split()
    while words and words[-1] in LEGAL_SUFFIXES:
        words.pop()
    key = "-".join(words).strip("-")
    key = re.sub(r"-{2,}", "-", key)
    if not key:
        raise SystemExit("Could not derive a link key from the company name.")
    return key


def unique_key(key: str, existing: set) -> str:
    if key not in existing:
        return key
    n = 2
    while f"{key}-{n}" in existing:
        n += 1
    return f"{key}-{n}"


def js(value: str) -> str:
    """A safe JavaScript string literal (also safe inside an HTML <script> block)."""
    return (json.dumps(value, ensure_ascii=False)
            .replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
            .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))


def clean(value: str, field: str, required=True) -> str:
    value = re.sub(r"\s+", " ", (value or "")).strip()
    if required and not value:
        raise SystemExit(f"--{field} is required.")
    return value


DEFAULT_CONFIDENTIALITY_PERIOD = "5 years from termination of the Agreement / discussions"


def load_custom(root: Path, key: str) -> dict:
    """Per-NDA changes live in custom/{key}.json (see SYSTEM.md, 'Custom clauses')."""
    path = root / "custom" / f"{key}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _clause_block(template: str, n: int):
    m = re.search(r'(<details class="acc"[^>]*><summary class="acc-trigger"><span class="acc-num">%02d</span>.*?)(</details>)' % n,
                  template, flags=re.S)
    if not m:
        raise SystemExit(f"Clause {n} not found in template.")
    return m


def apply_custom(template: str, custom: dict):
    """Apply a custom file to the template HTML. Returns (template, number_of_clauses)."""
    esc = lambda s: html.escape(s, quote=False)
    for e in custom.get("edits", []):
        m = _clause_block(template, e["clause"])
        block = m.group(1)
        if block.count(esc(e["find"])) != 1:
            raise SystemExit(f"Custom edit for clause {e['clause']} must match exactly once: {e['find'][:70]!r}")
        template = template.replace(m.group(0), block.replace(esc(e["find"]), esc(e["replace"])) + m.group(2), 1)
    for ap in custom.get("append", []):
        m = _clause_block(template, ap["clause"])
        block = m.group(1)
        if not block.endswith("</div>"):
            raise SystemExit(f"Cannot append to clause {ap['clause']}.")
        extra = "".join(f'<p class="">{esc(p)}</p>' for p in ap["paragraphs"])
        template = template.replace(m.group(0), block[:-len("</div>")] + extra + "</div>" + m.group(2), 1)
    count = 25
    new = custom.get("new_clauses", [])
    if new:
        last = _clause_block(template, 25).group(0)
        html_new = ""
        for i, c in enumerate(new, 26):
            body = "".join(f'<p class="">{esc(p)}</p>' for p in c["paragraphs"])
            html_new += (f'\n<details class="acc"><summary class="acc-trigger"><span class="acc-num">{i:02d}</span>'
                         f'<span class="acc-title">{esc(c["title"])}</span><span class="acc-chev">+</span></summary>'
                         f'<div class="acc-body">{body}</div></details>')
        template = template.replace(last, last + html_new, 1)
        count += len(new)
    return template, count


def pick_blocks(template: str, kind: str) -> str:
    """Keep <!--IF:kind-->…<!--/IF--> blocks that match, drop the others."""
    def repl(m):
        return m.group(2) if m.group(1) == kind else ""
    return re.sub(r"<!--IF:(\w+)-->(.*?)<!--/IF-->", repl, template, flags=re.S)


def card_meta(v: dict, has_gst: bool) -> str:
    """Small text under the client's name in the party card."""
    parts = []
    if v["address"]:
        parts.append(html.escape(v["address"]))
    elif v["type"] == "individual":
        parts.append("Individual")
    if has_gst:
        parts.append(f"<b>GST</b> {html.escape(v['gst'])}")
    return "<br>".join(parts)


def render(template: str, v: dict) -> str:
    template = pick_blocks(template, v["type"])
    custom = v.get("custom") or {}
    template, clause_count = apply_custom(template, custom)
    gst = v["gst"]
    has_gst = bool(gst) and gst.upper() not in {"N/A", "NA", "NONE", "-"}
    values = {
        "CLAUSE_COUNT": str(clause_count),
        "CONFIDENTIALITY_PERIOD": html.escape(custom.get("confidentiality_period", DEFAULT_CONFIDENTIALITY_PERIOD)),
        "RR_ADDRESS": html.escape(RR_ADDRESS),
        "RR_GST": html.escape(RR_GST),
        "RR_PAN": html.escape(RR_PAN),
        "CLIENT_COMPANY": html.escape(v["company"]),
        "CLIENT_ADDRESS": html.escape(v["address"]),
        "CLIENT_SIGNATORY": html.escape(v["signatory"]),
        "PURPOSE": html.escape(v["purpose"]),
        "EXEC_DATE": html.escape(v["date"]),
        "EXEC_PLACE": html.escape(v["place"]),
        "CLIENT_GST_ROW_HTML": f"<br><b>GST</b> {html.escape(gst)}" if has_gst else "",
        "CLIENT_RESIDING_SENTENCE": f", residing at {html.escape(v['address'])}" if v["address"] else "",
        "CLIENT_CARD_META_HTML": card_meta(v, has_gst),
        "CLIENT_GST_SENTENCE": f", GST No. {html.escape(gst)}" if has_gst else "",
        "NDA_KEY_JS": js(v["key"]),
        "CLIENT_COMPANY_JS": js(v["company"]),
        "CLIENT_SIGNATORY_JS": js(v["signatory"]),
        "PURPOSE_JS": js(v["purpose"]),
    }
    out = re.sub(r"\{\{([A-Z_]+)\}\}", lambda m: values[m.group(1)], template)
    left = re.findall(r"\{\{[A-Z_]+\}\}", out)
    if left:
        raise SystemExit(f"Unfilled template variables: {sorted(set(left))}")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--type", choices=["company", "individual"], default="company",
                    help="Is the client a company (default) or an individual signing in their own name?")
    ap.add_argument("--regenerate", metavar="ID", default=None,
                    help="Rebuild the page of an existing NDA from ndas.json using the current template "
                         "(no new entry). Use after a template or Rocket Rush detail change.")
    ap.add_argument("--company", default=None,
                    help="Client company full legal name (for --type individual: the person's full name)")
    ap.add_argument("--address", default="",
                    help="Client registered office (required for a company) or residential address "
                         "(optional for an individual; omitted from the agreement when empty)")
    ap.add_argument("--gst", default="N/A", help="Client GST number, or N/A")
    ap.add_argument("--signatory", default="Authorised Signatory", help="Client signatory name")
    ap.add_argument("--purpose", default=None, help='e.g. "LinkedIn Personal Branding"')
    ap.add_argument("--date", default=None, help='Execution date text, default today e.g. "12th November 2026"')
    ap.add_argument("--place", default=DEFAULT_PLACE, help=f"Execution place (default {DEFAULT_PLACE})")
    ap.add_argument("--private-suffix", action="store_true",
                    help="Append a random 4-char suffix to the link so it cannot be guessed from the company name")
    ap.add_argument("--root", default=str(ROOT), help="Repo root (default: this repo)")
    a = ap.parse_args(argv)

    root = Path(a.root)
    registry_path = root / "ndas.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8")) if registry_path.exists() else []

    if a.regenerate:
        entry = next((e for e in registry if e["id"] == a.regenerate), None)
        if entry is None:
            raise SystemExit(f"No NDA with id {a.regenerate!r} in ndas.json.")
        v = {"type": entry.get("type", "company"), "company": entry["client_name"], "address": entry.get("address", ""),
             "gst": entry.get("gst", "N/A"), "signatory": entry["signatory"], "purpose": entry["purpose"],
             "date": entry["exec_date"], "place": entry["exec_place"], "key": entry["id"]}
        v["custom"] = load_custom(root, v["key"])
        page = render((root / "template.html").read_text(encoding="utf-8"), v)
        (root / "ndas").mkdir(exist_ok=True)
        (root / "ndas" / f"{v['key']}.html").write_text(page, encoding="utf-8")
        print(json.dumps(entry, indent=2, ensure_ascii=False))
        return entry
    if not a.company or not a.purpose:
        raise SystemExit("--company and --purpose are required.")

    v = {
        "type": a.type,
        "company": clean(a.company, "company"),
        "address": clean(a.address, "address", required=(a.type == "company")),
        "gst": clean(a.gst, "gst", required=False) or "N/A",
        "signatory": clean(a.company if a.type == "individual" else a.signatory, "signatory"), "purpose": clean(a.purpose, "purpose"),
        "date": clean(a.date or today_text(), "date"), "place": clean(a.place, "place"),
    }
    base = make_key(v["company"])
    if a.private_suffix:
        base = f"{base}-{secrets.token_hex(2)}"
    v["key"] = unique_key(base, {e["id"] for e in registry})
    v["custom"] = load_custom(root, v["key"])

    page = render((root / "template.html").read_text(encoding="utf-8"), v)
    (root / "ndas").mkdir(exist_ok=True)
    (root / "ndas" / f"{v['key']}.html").write_text(page, encoding="utf-8")

    entry = {
        "id": v["key"], "type": v["type"], "client_name": v["company"], "signatory": v["signatory"], "gst": v["gst"],
        "address": v["address"], "purpose": v["purpose"], "exec_date": v["date"], "exec_place": v["place"],
        "created_date": f"{datetime.now().day} {datetime.now().strftime('%B %Y')}",
        "url": f"{BASE_URL}{v['key']}.html",
    }
    registry.append(entry)
    registry_path.write_text(json.dumps(registry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(entry, indent=2, ensure_ascii=False))
    return entry


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
