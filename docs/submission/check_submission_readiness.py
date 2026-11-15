#!/usr/bin/env python3
"""Submission readiness audit for THE THIRD EYE (P5 Lane C).

Checks the judge-facing documents under docs/submission/ and the official
challenge capture under challenge/ against the team's submission rules:

  1. required files exist
  2. markdown links resolve (relative files, heading anchors, https syntax)
  3. no raw placeholders; only the registered [PENDING ...] markers are allowed
  4. numeric claims carry [PENDING MEASURED RUN] or an artifact ID + SHA256
  5. recorded SHA256 values match the git blob at the pinned commit
  6. no contract-fixture sample values leak into submission text
  7. team choices are never described as NASA or Space Apps mandates
  8. ONE_PAGE_RESULTS follows plan Section 9A
  9. DEMO_SCRIPT has the five-beat first-20-seconds opening, the four views in
     order, ends by 00:30 and keeps narration free of internal schema terms
 10. PORTAL_CHECKLIST and CHALLENGE_CAPTURE contain their required items
 11. no credentials

Usage:
    python docs/submission/check_submission_readiness.py [--online] [--strict-pending]

--online          also issue HTTPS HEAD requests for external links
--strict-pending  fail while any [PENDING ...] marker remains (use at final freeze)

Exit status is 0 only when every check passes. Standard library only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SUBMISSION_DIR = ROOT / "docs" / "submission"
CAPTURE = ROOT / "challenge" / "CHALLENGE_CAPTURE.md"
ONE_PAGE = SUBMISSION_DIR / "ONE_PAGE_RESULTS.md"
DEMO = SUBMISSION_DIR / "DEMO_SCRIPT.md"
CHECKLIST = SUBMISSION_DIR / "PORTAL_CHECKLIST.md"
FIXTURES_DIR = ROOT / "contracts" / "fixtures"
# Fixture values of the CURRENT contract are read from this git ref (P4-B review checkpoint), in
# addition to any older contracts/fixtures on this branch. Override with
# $env:SUBMISSION_CONTRACT_REF. If the ref is unreadable the leak check FAILS.
CONTRACT_REF = os.environ.get("SUBMISSION_CONTRACT_REF", "edf9d65255377320b0a544e69f64db897e2960bd")

REQUIRED_FILES = [CAPTURE, ONE_PAGE, DEMO, CHECKLIST, Path(__file__).resolve()]

# Registered annotation markers. Numbers use MEASURED RUN; names/URLs use TEAM
# INPUT; unconfirmed rules or shipped views use VERIFICATION. An optional
# ": detail" suffix names what is pending.
PENDING_ALLOWED = re.compile(
    r"\[PENDING (?:MEASURED RUN|TEAM INPUT|VERIFICATION)(?:: [^\]\n]+)?\]"
)
PENDING_ANY = re.compile(r"\[PENDING[^\]\n]*\]", re.IGNORECASE)
PENDING_MEASURED = "[PENDING MEASURED RUN]"

RAW_PLACEHOLDERS = [
    (re.compile(r"\b(?:TODO|TBD|TBA|FIXME|XXX+|TKTK)\b"), "raw TODO/TBD-style marker"),
    (re.compile(r"lorem ipsum", re.IGNORECASE), "lorem ipsum"),
    (re.compile(r"\?\?\?"), "'???' marker"),
    (re.compile(r"\[\s*(?:INSERT|FILL|ADD)\b", re.IGNORECASE), "[INSERT ...]-style marker"),
    (re.compile(r"<\s*(?:insert|fill|placeholder|your)[^>]*>", re.IGNORECASE), "<insert ...>-style marker"),
    (re.compile(r"\bPLACEHOLDER\b"), "PLACEHOLDER"),
    (re.compile(r"\{\{[^}]*\}\}"), "{{template}} marker"),
    (re.compile(r"\b[XYZWNRTB] of [XYZWNRTB]\b"), "unfilled letter template (e.g. 'X of N')"),
]

CLAIM_UNITS = (
    r"cases?|blocks?|regions?|test[- ]years?|fires?|hotspots?|detections?|alerts?|"
    r"users?|cell-days?|errors?|abstentions?|failures?|percent(?:age points?)?"
)
NUMERIC_CLAIMS = [
    re.compile(r"\d+(?:[.,]\d+)?\s*%"),
    re.compile(r"\b\d+(?:\.\d+)?\s+(?:of|out of)\s+\d+\b"),
    re.compile(r"\b\d[\d,]*(?:\.\d+)?\s+(?:" + CLAIM_UNITS + r")\b", re.IGNORECASE),
    re.compile(r"\b\d+(?:\.\d+)?\s*[x\u00d7]\s+(?:faster|better|fewer|more|less)\b", re.IGNORECASE),
]

MANDATE_LANGUAGE = re.compile(
    r"\b(?:NASA|Space Apps)[- ](?:mandat\w*|requires?|required|demands?)\b"
    r"|\b(?:mandated|required|demanded) by (?:NASA|Space Apps)\b"
    r"|\bNASA[- ]mandat\w*",
    re.IGNORECASE,
)

SHA256_HEX = re.compile(r"(?<![0-9a-fA-F])[0-9a-f]{64}(?![0-9a-fA-F])")
COMMIT_HEX = re.compile(r"`([0-9a-f]{40})`")
PINNED_COMMIT = re.compile(r"Pinned commit:\s*`([0-9a-f]{40})`")
BACKTICK = re.compile(r"`([^`\n]+)`")
EMPTY_INPUT_SHA256 = hashlib.sha256(b"").hexdigest()

SECRETS = [
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)\b(?:password|passwd|api[_-]?key|secret|token)\s*[:=]\s*\S{6,}"),
]

# Internal schema / method terms that must not reach narration or on-screen text.
DEMO_JARGON = [
    re.compile(r"\b[a-z]+(?:_[a-z0-9]+)+\b"),  # any snake_case identifier
    re.compile(r"\ba_[HC]\b"),
    re.compile(r"\bStage [AB]\b", re.IGNORECASE),
    re.compile(r"\bleave-one-year-out\b|\bLOYO\b", re.IGNORECASE),
    re.compile(r"\b(?:own|common)[- ]support\b", re.IGNORECASE),
    re.compile(r"\breference-relative\b", re.IGNORECASE),
    re.compile(r"\binference status\b|\bapplicability\b", re.IGNORECASE),
    re.compile(r"\bgeometry ID\b|\bartifact version\b|\bpolicy ID\b", re.IGNORECASE),
    re.compile(r"\bD\s*/\s*O\b"),
    re.compile(r"\btau\b|\u03c4"),
]
DEMO_ANIMATION_WORDS = re.compile(
    r"\b(?:animat\w*|morph\w*|fly[- ]?(?:in|through|over)\w*|glow\w*|puls\w*|"
    r"particle\w*|sparkl\w*|swoosh\w*|spin\w*|bounc\w*|fade\w*|shimmer\w*)\b",
    re.IGNORECASE,
)
DEMO_BEATS = ["Region", "Seam", "Headline Metric", "Finding", "Limitation"]
DEMO_VIEWS = ["Landing", "Story chapters", "Research Lab", "Evidence Export"]
DEMO_LIMIT_SECONDS = 30
DEMO_OPENING_SECONDS = 20

ONE_PAGE_MAX_WORDS = 900  # about one printed page including tables
EVIDENCE_RELATIONSHIPS = {"direct_reproduction", "related_indicator_analysis", "outside_scope"}

LINK = re.compile(r"(?<!!)\[([^\]\n]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
AUTOLINK = re.compile(r"<(https?://[^>\s]+)>")


@dataclass
class Report:
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    passed: list[str] = field(default_factory=list)

    def check(self, name: str, problems: list[str]) -> None:
        if problems:
            self.failures.extend(f"[{name}] {p}" for p in problems)
        else:
            self.passed.append(name)


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def documents() -> list[Path]:
    docs = sorted(SUBMISSION_DIR.glob("*.md"))
    if CAPTURE.exists():
        docs.insert(0, CAPTURE)
    return docs


def strip_code(text: str) -> str:
    """Blank out fenced blocks and inline code, keeping line numbers."""
    out, in_fence = [], False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            out.append("")
            continue
        out.append("" if in_fence else re.sub(r"`[^`\n]*`", "``", line))
    return "\n".join(out)


def github_slug(heading: str) -> str:
    text = re.sub(r"[`*_\[\]()]", "", heading.strip().lower())
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


def anchors_of(path: Path) -> set[str]:
    slugs: dict[str, int] = {}
    result = set()
    for line in strip_code(path.read_text(encoding="utf-8")).splitlines():
        m = re.match(r"^#{1,6}\s+(.*?)\s*#*\s*$", line)
        if not m:
            continue
        base = github_slug(m.group(1))
        n = slugs.get(base, 0)
        slugs[base] = n + 1
        result.add(base if n == 0 else f"{base}-{n}")
    return result


def git_blob_sha256(commit: str, path: str) -> str | None:
    try:
        blob = subprocess.run(
            ["git", "-C", str(ROOT), "cat-file", "blob", f"{commit}:{path}"],
            capture_output=True, check=True, timeout=30,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    return hashlib.sha256(blob).hexdigest()


def git_has_path(commit: str, path: str) -> bool:
    try:
        r = subprocess.run(
            ["git", "-C", str(ROOT), "cat-file", "-e", f"{commit}:{path}"],
            capture_output=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0


# ---------------------------------------------------------------- checks


def check_required_files() -> list[str]:
    return [f"missing required file: {rel(p)}" for p in REQUIRED_FILES if not p.is_file()]


def check_links(docs: list[Path], online: bool, report: Report) -> list[str]:
    problems: list[str] = []
    external: set[str] = set()
    for doc in docs:
        text = strip_code(doc.read_text(encoding="utf-8"))
        for lineno, line in enumerate(text.splitlines(), 1):
            targets = [m.group(2) for m in LINK.finditer(line)]
            targets += [m.group(1) for m in AUTOLINK.finditer(line)]
            for target in targets:
                where = f"{rel(doc)}:{lineno}"
                if target.startswith(("http://", "https://")):
                    parsed = urllib.parse.urlparse(target)
                    if parsed.scheme != "https":
                        problems.append(f"{where}: link is not https: {target}")
                    elif not parsed.netloc or "." not in parsed.netloc:
                        problems.append(f"{where}: malformed URL: {target}")
                    else:
                        external.add(target)
                    continue
                if target.startswith("mailto:"):
                    continue
                file_part, _, anchor = target.partition("#")
                dest = doc if not file_part else (doc.parent / urllib.parse.unquote(file_part)).resolve()
                if not dest.exists():
                    problems.append(f"{where}: broken relative link: {target}")
                    continue
                if anchor and dest.suffix == ".md" and anchor not in anchors_of(dest):
                    problems.append(f"{where}: missing anchor '#{anchor}' in {rel(dest)}")
    if online:
        for url in sorted(external):
            req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "third-eye-readiness/1"})
            try:
                with urllib.request.urlopen(req, timeout=20) as resp:
                    if resp.status >= 400:
                        problems.append(f"online: {url} returned HTTP {resp.status}")
            except urllib.error.HTTPError as exc:
                if exc.code in (403, 405):  # some hosts refuse HEAD; not proof of a broken link
                    report.warnings.append(f"online: {url} refused HEAD (HTTP {exc.code}); open it manually")
                else:
                    problems.append(f"online: {url} returned HTTP {exc.code}")
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                problems.append(f"online: {url} unreachable: {exc}")
    return problems


def check_placeholders(docs: list[Path], strict_pending: bool) -> list[str]:
    problems = []
    for doc in docs:
        for lineno, line in enumerate(doc.read_text(encoding="utf-8").splitlines(), 1):
            where = f"{rel(doc)}:{lineno}"
            for m in PENDING_ANY.finditer(line):
                if not PENDING_ALLOWED.fullmatch(m.group(0)):
                    problems.append(f"{where}: unregistered pending marker {m.group(0)!r}")
                elif strict_pending:
                    problems.append(f"{where}: pending marker remains at freeze: {m.group(0)}")
            scrubbed = PENDING_ALLOWED.sub("", line)
            for pattern, label in RAW_PLACEHOLDERS:
                if pattern.search(scrubbed):
                    problems.append(f"{where}: {label}: {line.strip()[:100]}")
    return problems


def check_numeric_claims(docs: list[Path]) -> list[str]:
    problems = []
    for doc in docs:
        for lineno, line in enumerate(doc.read_text(encoding="utf-8").splitlines(), 1):
            if PENDING_MEASURED in line:
                continue
            if SHA256_HEX.search(line) and re.search(r"artifact", line, re.IGNORECASE):
                continue
            probe = re.sub(r"`[^`\n]*`", "", line)
            probe = re.sub(r"\]\([^)]*\)|<https?://[^>]*>", "]", probe)  # ignore URLs
            for pattern in NUMERIC_CLAIMS:
                m = pattern.search(probe)
                if m:
                    problems.append(
                        f"{rel(doc)}:{lineno}: numeric claim '{m.group(0)}' has no artifact_id+SHA256 "
                        f"and no {PENDING_MEASURED}"
                    )
                    break
    return problems


def check_hashes(docs: list[Path], report: Report) -> list[str]:
    problems = []
    for doc in docs:
        text = doc.read_text(encoding="utf-8")
        pinned = PINNED_COMMIT.search(text)
        for lineno, line in enumerate(text.splitlines(), 1):
            hashes = SHA256_HEX.findall(line)
            if not hashes:
                continue
            where = f"{rel(doc)}:{lineno}"
            if EMPTY_INPUT_SHA256 in hashes:
                problems.append(f"{where}: SHA256 of empty input cannot identify an artifact")
                continue
            commits = [c for c in COMMIT_HEX.findall(line) if c not in hashes]
            commit = commits[0] if commits else (pinned.group(1) if pinned else None)
            paths = [t for t in BACKTICK.findall(line) if not SHA256_HEX.fullmatch(t) and ("/" in t or "." in t)]
            if commit:
                paths = [p for p in paths if git_has_path(commit, p)]
            if not paths:
                if not re.search(r"artifact|^\s*\|\s*[\w.-]+\s*\|", line, re.IGNORECASE):
                    problems.append(f"{where}: SHA256 has neither a verifiable path nor an artifact_id")
                else:
                    report.warnings.append(f"{where}: SHA256 for a non-repository artifact; not verified locally")
                continue
            if not commit:
                problems.append(f"{where}: SHA256 for `{paths[0]}` has no pinned commit to verify against")
                continue
            actual = git_blob_sha256(commit, paths[0])
            if actual is None:
                problems.append(f"{where}: cannot read `{paths[0]}` at commit {commit[:12]} (git unavailable?)")
            elif actual not in hashes:
                problems.append(
                    f"{where}: SHA256 mismatch for `{paths[0]}` at {commit[:12]}: recorded {hashes[0][:16]}..., "
                    f"actual {actual[:16]}..."
                )
    return problems


# Calendar structure (day counts, week and month numbers) is not a sample finding; contract
# 1.3.0+ fixtures carry such small integers (7, 27, 30, 31) on every period record.
STRUCTURAL_KEYS = {
    "coordinates", "days_in_period", "days_with_file", "included_day_count", "week_number", "month",
    "year", "iso_year", "target_year", "minimum_year_count", "reference_start_year",
    "reference_end_year", "normal_season_start_month", "normal_season_end_month", "peak_median_month",
    "eligible_prior_years",
}

# Structural duration numbers representing official competition limits (30-second video limit,
# 20-second first-screen rule, 60-90 second Quick Mission) are not sample finding leaks.
EVENT_DURATION_CONSTANTS = {"20", "30", "90"}


def _fixture_values(obj, sink: set[str], key: str = "") -> None:
    if key in STRUCTURAL_KEYS:
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            _fixture_values(v, sink, k)
    elif isinstance(obj, list):
        for v in obj:
            _fixture_values(v, sink, key)
    elif isinstance(obj, bool):
        return
    elif isinstance(obj, float) and not obj.is_integer():
        sink.add(repr(abs(obj)))
    elif isinstance(obj, (int, float)) and abs(obj) >= 20 and not 1990 <= abs(obj) <= 2100:
        val_str = str(int(abs(obj)))
        if val_str not in EVENT_DURATION_CONSTANTS:
            sink.add(val_str)
    elif isinstance(obj, str):
        for h in SHA256_HEX.findall(obj):
            sink.add(h)
        for num in re.findall(r"(?<![\w.])\d+\.\d+(?![\w.])", obj):
            sink.add(num)
        for num in re.findall(r"(?<![\w.:-])\d{2,}(?![\w.:-])", obj):
            if int(num) >= 20 and not 1990 <= int(num) <= 2100 and str(int(num)) not in EVENT_DURATION_CONSTANTS:
                sink.add(str(int(num)))
        if key in {"statement", "plain_language_summary", "headline_metric_description"} and len(obj) > 30:
            sink.add(obj)


def _fixture_texts() -> tuple[list[str], str]:
    """Fixture JSON texts from local contracts/ (may be an older version on this branch) AND the
    current contract ref. The ref must be readable; otherwise nothing is returned."""
    local = [p.read_text(encoding="utf-8") for p in sorted(FIXTURES_DIR.glob("*.json"))]
    try:
        names = subprocess.run(
            ["git", "-C", str(ROOT), "ls-tree", "--name-only", f"{CONTRACT_REF}:contracts/fixtures"],
            capture_output=True, text=True, check=True, timeout=30,
        ).stdout.split()
        texts = [subprocess.run(
            ["git", "-C", str(ROOT), "show", f"{CONTRACT_REF}:contracts/fixtures/{n}"],
            capture_output=True, text=True, encoding="utf-8", check=True, timeout=30,
        ).stdout for n in names if n.endswith(".json")]
    except (OSError, subprocess.SubprocessError):
        return [], f"git ref {CONTRACT_REF[:12]} (unreadable)"
    if not texts:
        return [], f"git ref {CONTRACT_REF[:12]} (no fixtures)"
    return local + texts, f"contracts/fixtures + git ref {CONTRACT_REF[:12]}"


def check_fixture_leaks(docs: list[Path]) -> list[str]:
    values: set[str] = set()
    texts, source = _fixture_texts()
    if not texts:
        return [f"no contract fixtures readable from {source}; fetch P4-B or set SUBMISSION_CONTRACT_REF"]
    for text in texts:
        try:
            _fixture_values(json.loads(text), values)
        except json.JSONDecodeError:
            continue
    problems = []
    for doc in docs:
        text = doc.read_text(encoding="utf-8")
        for value in sorted(values):
            if len(value) > 64:
                found = value in text
            else:
                found = re.search(r"(?<![\w.])" + re.escape(value) + r"(?![\w]|\.\d)", text) is not None
            if found:
                problems.append(f"{rel(doc)}: contains contract-fixture sample value {value[:60]!r}")
    return problems


def check_mandate_language(docs: list[Path]) -> list[str]:
    problems = []
    for doc in docs:
        for lineno, line in enumerate(doc.read_text(encoding="utf-8").splitlines(), 1):
            m = MANDATE_LANGUAGE.search(line)
            if m:
                problems.append(f"{rel(doc)}:{lineno}: '{m.group(0)}': label the source as VERIFIED SPACE APPS RULE, LOCAL EVENT RULE or TEAM CHOICE")
    return problems


def check_secrets(docs: list[Path]) -> list[str]:
    problems = []
    for doc in docs + [Path(__file__).resolve()]:
        text = doc.read_text(encoding="utf-8")
        if doc == Path(__file__).resolve():
            continue  # the pattern table itself would match
        for lineno, line in enumerate(text.splitlines(), 1):
            for pattern in SECRETS:
                if pattern.search(line):
                    problems.append(f"{rel(doc)}:{lineno}: possible credential")
    return problems


def section(text: str, heading_pattern: str) -> str | None:
    lines = text.splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m and re.search(heading_pattern, m.group(2), re.IGNORECASE):
            level = len(m.group(1))
            body = []
            for nxt in lines[i + 1:]:
                n = re.match(r"^(#{1,6})\s", nxt)
                if n and len(n.group(1)) <= level:
                    break
                body.append(nxt)
            return "\n".join(body)
    return None


def check_one_page() -> list[str]:
    if not ONE_PAGE.is_file():
        return ["ONE_PAGE_RESULTS.md missing"]
    text = ONE_PAGE.read_text(encoding="utf-8")
    problems = []
    header = section(text, r"\bHeader\b")
    if header is None:
        problems.append("missing 'Header' section")
    else:
        for item in ["Project Identity", "Challenge Category", "Team Members", "Artifact Hashes"]:
            if f"**{item}**" not in header:
                problems.append(f"Header lacks bold field '{item}'")
        if not SHA256_HEX.search(header):
            problems.append("Header lists no SHA256 artifact hash")
    denom = section(text, r"Denominator Statement")
    if denom is None:
        problems.append("missing 'Denominator Statement' section")
    else:
        for unit in ["blocks", "regions", "test years"]:
            if not re.search(rf"\b{unit}\b", denom):
                problems.append(f"Denominator Statement lacks independent unit '{unit}'")
        if "not independent" not in denom:
            problems.append("Denominator Statement must say cases/blocks are not independent tests")
    table = section(text, r"Primary Finding Table")
    if table is None:
        problems.append("missing 'Primary Finding Table' section")
    else:
        rows = [ln for ln in table.splitlines() if ln.lstrip().startswith("|")]
        if len(rows) < 3:
            problems.append("Primary Finding Table has no markdown table")
        for needle in ["Raw handover", "Stage A", "Uncertainty-aware", "Reference"]:
            if not any(needle.lower() in r.lower() for r in rows):
                problems.append(f"Primary Finding Table lacks row '{needle}'")
    limits = section(text, r"Limitations")
    if limits is None:
        problems.append("missing 'Limitations & Abstentions' section")
    else:
        low = limits.lower()
        if not ("2020" in low and "aqua" in low and "outage" in low):
            problems.append("Limitations must account for the 2020 Aqua outage")
        if "boundar" not in low or "calibrat" not in low:
            problems.append("Limitations must account for uncalibrated boundaries")
        if "abstention" not in low:
            problems.append("Limitations must account for abstentions")
    words = len(re.findall(r"\S+", text))
    if words > ONE_PAGE_MAX_WORDS:
        problems.append(f"one-page summary has {words} words (limit {ONE_PAGE_MAX_WORDS})")
    return problems


def _seconds(stamp: str) -> int:
    mm, ss = stamp.split(":")
    return int(mm) * 60 + int(ss)


def check_demo() -> list[str]:
    if not DEMO.is_file():
        return ["DEMO_SCRIPT.md missing"]
    text = DEMO.read_text(encoding="utf-8")
    problems = []
    opening = section(text, r"First 20 Seconds Showcase")
    if opening is None:
        return ["missing 'First 20 Seconds Showcase' section"]
    beats = re.findall(r"^###\s+(\d\d:\d\d)-(\d\d:\d\d)\s*\|\s*Beat\s+(\d):\s*(.+?)\s*$", opening, re.MULTILINE)
    if [b[3] for b in beats] != DEMO_BEATS:
        problems.append(f"opening beats must be {DEMO_BEATS} in order; found {[b[3] for b in beats]}")
    expected_start = 0
    for start, end, num, name in beats:
        s, e = _seconds(start), _seconds(end)
        if s != expected_start or e <= s:
            problems.append(f"beat {num} ({name}) {start}-{end} is not contiguous with the previous beat")
        expected_start = e
    if beats and expected_start != DEMO_OPENING_SECONDS:
        problems.append(f"opening must end at 00:20; ends at {expected_start}s")
    for start, end, num, name in beats:
        body = section(opening, rf"Beat\s+{num}:")
        if body is None or "**Narration:**" not in body or "**On-screen text:**" not in body or "**Screen action**" not in body:
            problems.append(f"beat {num} ({name}) needs Screen action, Narration and On-screen text")
    steps = re.findall(r"^###\s+(\d\d:\d\d)-(\d\d:\d\d)\s*\|\s*Step\s+(\d):\s*(.+?)\s*$", text, re.MULTILINE)
    if [s[3] for s in steps] != DEMO_VIEWS:
        problems.append(f"walkthrough views must be {DEMO_VIEWS} in order; found {[s[3] for s in steps]}")
    for start, end, num, name in steps:
        if _seconds(end) > DEMO_LIMIT_SECONDS:
            problems.append(f"step {num} ({name}) ends at {end}, past the 00:{DEMO_LIMIT_SECONDS} video limit")
        body = section(text, rf"Step\s+{num}:")
        if body is None or "**Shipped**" not in body or "**Route**" not in body:
            problems.append(f"step {num} ({name}) needs Route and Shipped lines")
    for lineno, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith(">"):
            spoken = PENDING_ALLOWED.sub("", re.sub(r"\*\*(?:Narration|On-screen text):\*\*", "", stripped))
            for pattern in DEMO_JARGON:
                m = pattern.search(spoken)
                if m:
                    problems.append(f"DEMO_SCRIPT.md:{lineno}: internal term '{m.group(0)}' in narration/on-screen text")
                    break
        if stripped.startswith("- **Screen action**"):
            m = DEMO_ANIMATION_WORDS.search(stripped)
            if m:
                problems.append(f"DEMO_SCRIPT.md:{lineno}: screen action describes an effect ('{m.group(0)}'); record only real UI behavior")
    return problems


def check_checklist() -> list[str]:
    if not CHECKLIST.is_file():
        return ["PORTAL_CHECKLIST.md missing"]
    text = CHECKLIST.read_text(encoding="utf-8")
    problems = []
    for needle, label in [
        ("22:00", "Sunday 22:00 internal freeze"),
        ("11:59 PM", "official 11:59 PM cutoff"),
        ("incognito", "incognito video playback test"),
        ("DOI", "dataset DOIs"),
        ("license", "license disclosures"),
        ("AI-assistance", "AI-assistance disclosure"),
        ("Sign-off", "sign-off table"),
    ]:
        if needle.lower() not in text.lower():
            problems.append(f"missing {label} ('{needle}')")
    if len(re.findall(r"^\s*- \[[ xX]\]", text, re.MULTILINE)) < 10:
        problems.append("fewer than 10 checklist items")
    if not re.search(r"10\.5067/", text):
        problems.append("no NASA dataset DOI listed")
    return problems


def check_capture() -> list[str]:
    if not CAPTURE.is_file():
        return ["challenge/CHALLENGE_CAPTURE.md missing"]
    text = CAPTURE.read_text(encoding="utf-8")
    problems = []
    for needle in ["11:59 PM", "UTC", "under 18", "VERIFIED SPACE APPS RULE", "TEAM CHOICE"]:
        if needle not in text:
            problems.append(f"missing '{needle}'")
    for crit in ["Impact", "Creativity", "Validity", "Relevance", "Presentation"]:
        if not re.search(rf"^\|\s*{crit}\s*\|", text, re.MULTILINE):
            problems.append(f"judging criteria table lacks '{crit}'")
    if not re.search(r"\d{4}-\d\d-\d\dT\d\d:\d\dZ", text):
        problems.append("no ISO-8601 UTC retrieval timestamp")
    if section(text, r"analyst question") is None:
        problems.append("missing analyst question section")
    labels = set(re.findall(r"evidence_relationship\s*\|\s*`([a-z_]+)`", text))
    if not labels:
        problems.append("flagship claim has no evidence_relationship label")
    elif not labels <= EVIDENCE_RELATIONSHIPS:
        problems.append(f"unknown evidence_relationship label(s): {sorted(labels - EVIDENCE_RELATIONSHIPS)}")
    if "source_id" not in text or not re.search(r"https://\S+", section(text, r"Published claim") or ""):
        problems.append("flagship claim needs a source_id and a source URL")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--online", action="store_true", help="HEAD-check external links")
    parser.add_argument("--strict-pending", action="store_true", help="fail on any remaining [PENDING ...] marker")
    args = parser.parse_args(argv)

    report = Report()
    report.check("required files exist", check_required_files())
    docs = [d for d in documents() if d.is_file()]
    report.check("markdown links valid", check_links(docs, args.online, report))
    report.check("no raw placeholders", check_placeholders(docs, args.strict_pending))
    report.check("numeric claims traceable", check_numeric_claims(docs))
    report.check("artifact hashes verified", check_hashes(docs, report))
    report.check("no contract-fixture values", check_fixture_leaks(docs))
    report.check("no mandate language", check_mandate_language(docs))
    report.check("no credentials", check_secrets(docs))
    report.check("ONE_PAGE_RESULTS follows Section 9A", check_one_page())
    report.check("DEMO_SCRIPT structure", check_demo())
    report.check("PORTAL_CHECKLIST complete", check_checklist())
    report.check("CHALLENGE_CAPTURE complete", check_capture())

    pending = sum(len(PENDING_ALLOWED.findall(d.read_text(encoding="utf-8"))) for d in docs)
    for name in report.passed:
        print(f"PASS  {name}")
    for failure in report.failures:
        print(f"FAIL  {failure}")
    for warning in report.warnings:
        print(f"WARN  {warning}")
    print(f"\nDocuments scanned: {', '.join(rel(d) for d in docs)}")
    print(f"Registered [PENDING ...] markers remaining: {pending}")
    total = len(report.passed) + len({f.split(']')[0] for f in report.failures})
    print(f"Result: {len(report.passed)}/{total} checks passed, {len(report.failures)} failure(s)")
    return 0 if not report.failures else 1


if __name__ == "__main__":
    sys.exit(main())
