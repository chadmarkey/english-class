#!/usr/bin/env python3
"""English Class Prompt Council: roll, floor, objections, pick. Standard library, Python 3.9+.

Usage: council.py init "RAW ARGUMENT"   # flags, idea, run directory, roll, run pointer
       council.py pointer               # run pointer for this physical working directory
       council.py roll [--seed N] [--seats "A,B,C"] [--wild NAME] [--no-wild] [--fast]
       council.py floor DRAFT --roll ROLL.json [--idea idea.md]
       council.py objections PATH --roll ROLL.json
       council.py pick VERDICT DRAFTS_DIR --out WINNER.md [--roll ROLL.json] [--draft F] [--idea F]
Every subcommand prints one JSON object. Exit 0 = pass, 2 = fail, 3 = could not run.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import random
import re
import sys
import time
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEATS = HERE / "seats.tsv"
# The prompt the council writes is written for one model, and the frame is that model's.
# A new model means a new frame file and a new pair of constants, not an edited frame.
MODEL = "Claude Fable 5.1"
FRAME = "frame-fable-5.1.md"
N_REGULARS = 3
FAST_REGULARS = 2  # --fast: two rolled lenses plus the wild chair, drafted in one call
COUNCIL = Path.home() / ".council"


# ---------- helpers ----------


def slug(name):
    """A filename-safe key for a seat. Accents fold away, so Junot Díaz has one file."""
    folded = unicodedata.normalize("NFKD", name)
    folded = "".join(c for c in folded if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", folded.lower()).strip("-")


def read_seats(path=SEATS):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE))


def block(text, tag):
    """Inner text of the first <tag>...</tag> block, or '' if absent."""
    m = re.search(r"<%s>(.*?)</%s>" % (re.escape(tag), re.escape(tag)), text, re.S)
    return m.group(1) if m else ""


def emit(obj, code=0):
    print(json.dumps(obj, indent=2, sort_keys=True))
    return code


# ---------- init ----------

# Shapes, not entropy tests: enough to catch a key pasted into an idea by accident. The
# model-side check in SKILL.md stays as the backstop for everything this misses.
SECRET_PATTERNS = (
    ("an API key", r"\bsk-[A-Za-z0-9_-]{16,}"),
    ("a GitHub token", r"\bgh[pousr]_[A-Za-z0-9]{16,}"),
    ("an AWS access key id", r"\bAKIA[0-9A-Z]{16}\b"),
    ("a private key", r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    (
        "a named secret",
        r"(?i)\b(password|passwd|token|secret|api[_-]?key)\b\s*[:=]\s*\S{10,}",
    ),
)


def find_secret(text):
    """(what it looks like, a masked sample) for the first secret in TEXT, or None."""
    for what, pat in SECRET_PATTERNS:
        m = re.search(pat, text)
        if m:
            v = m.group(0)
            return what, "%s… (%d characters, not shown)" % (v[:3], len(v))
    return None


def run_slug(idea, n=5):
    """At most five lowercase words from the idea, joined by hyphens."""
    return "-".join(re.findall(r"[a-z0-9]+", idea.lower())[:n]) or "council-run"


# The idea is never tokenized. shlex.split raises "No closing quotation" on the apostrophe
# in "a doctor's note", and silently strips the quotes out of an idea that survives it, and
# SKILL.md promises the idea reaches the drafters verbatim. So the known flags are lifted off
# the front of the argument and everything after them is the idea, character for character.
FLAG_RE = re.compile(r"^--(seed|seats|wild|no-wild|revise|fast)(?=\s|=|$)")
VALUE_RE = re.compile(r"""^("[^"]*"|'[^']*'|(?!["'])\S+)(?=\s|$)""")
BARE_FLAGS = {"no-wild": "no_wild", "revise": "revise", "fast": "fast"}


def split_argument(raw):
    """({flags}, idea) from the one argument string /english-class was given."""
    flags = {"seed": None, "seats": None, "wild": None, "no_wild": False, "revise": False,
             "fast": False}
    rest = raw.strip()
    while True:
        if rest == "--" or (rest.startswith("--") and rest[2:3].isspace()):
            rest = rest[2:].lstrip()
            break
        m = FLAG_RE.match(rest)
        if not m:
            break
        name = m.group(1)
        rest = rest[m.end():].lstrip()
        if name in BARE_FLAGS:
            if rest.startswith("="):
                raise ValueError("--%s does not take a value" % name)
            flags[BARE_FLAGS[name]] = True
            continue
        if rest.startswith("="):
            rest = rest[1:]
            if not rest or rest[0].isspace():
                raise ValueError("--%s needs a value" % name)
        elif FLAG_RE.match(rest) or rest == "--" or (
            rest.startswith("--") and rest[2:3].isspace()
        ):
            raise ValueError("--%s needs a value" % name)
        v = VALUE_RE.match(rest)
        if not v:
            if rest.startswith(("\"", "'")):
                raise ValueError("--%s quoted value does not close cleanly" % name)
            raise ValueError("--%s needs a value" % name)
        value, rest = v.group(1), rest[v.end():].lstrip()
        if value[:1] in "\"'" and value[-1:] == value[:1]:
            value = value[1:-1]
        if not value.strip():
            raise ValueError("--%s needs a value" % name)
        if name == "seed":
            try:
                value = int(value)
            except ValueError:
                raise ValueError("--seed takes a number, not %r" % value)
        elif name == "seats":
            seat_list(value)
        flags[name] = value
    return flags, rest.strip()


def seat_list(value):
    """Normalize an explicit seat override without treating an empty one as a random roll."""
    if value is None:
        return None
    seats = [s for s in value.split(",") if s.strip()]
    if not seats:
        raise ValueError("--seats needs exactly %d names" % N_REGULARS)
    return seats


def run_pointer(home, cwd=None):
    """One pointer per working directory, so two councils never read each other's run."""
    here = Path.cwd() if cwd is None else Path(cwd)
    physical = here.resolve(strict=False)
    identity = hashlib.sha256(os.fsencode(physical)).hexdigest()
    return Path(home) / ("current_run." + identity)


def init(raw, home=COUNCIL, stamp=None, cwd=None):
    """Parse the whole argument string, make the run, roll it, and point at it."""
    # Clear the pointer first. A refused init must not leave the previous run bookmarked:
    # the next block reads $RUNPTR, and a stale one would draft over a finished run.
    ptr = run_pointer(home, cwd)
    if ptr.exists():
        ptr.unlink()
    flags, idea = split_argument(raw)
    if flags["fast"] and flags["revise"]:
        # A revision answers objections; a fast run files none, so there is nothing to answer.
        raise ValueError("--revise needs the objections a fast run skips; drop one of the two")
    if not idea:
        raise ValueError("no idea given; run /english-class <idea, rough prompt, or a file>")
    if len(idea.split()) == 1 or idea.startswith(("~", "/", "./")):
        src = Path(idea.strip("\"'")).expanduser()
        try:
            named_file = src.is_file()
        except OSError:
            named_file = False
        if named_file:
            idea = src.read_text(encoding="utf-8").strip()
            if not idea:
                raise ValueError("%s is empty" % src)
    found = find_secret(idea)
    if found:
        raise ValueError("the idea holds %s: %s; nothing was written" % found)
    seats = seat_list(flags["seats"])
    r = roll(flags["seed"], seats=seats, wild=flags["wild"], no_wild=flags["no_wild"],
             fast=flags["fast"])
    base = Path(home) / "runs" / ("%s-%s" % (run_slug(idea), stamp or time.strftime("%Y%m%d-%H%M%S")))
    run, n = base, 2
    while run.exists():  # same idea, same directory, same second: never share a run
        run, n = Path("%s-%d" % (base, n)), n + 1
    for d in ("drafts", "lint", "objections"):
        (run / d).mkdir(parents=True)
    (run / "idea.md").write_text(idea + "\n", encoding="utf-8")
    (run / "roll.json").write_text(json.dumps(r, indent=2, sort_keys=True), encoding="utf-8")
    ptr.parent.mkdir(parents=True, exist_ok=True)
    ptr.write_text(str(run) + "\n", encoding="utf-8")
    return {
        "run": str(run),
        "seed": r["seed"],
        "seats": [{"name": x["name"], "slug": x["slug"], "kind": x["kind"]} for x in r["seats"]],
        "revise": flags["revise"],
        "fast": flags["fast"],
        "pointer": str(ptr),
    }


# ---------- roll ----------


def _find(rows, key):
    k = key.strip()
    for r in rows:
        if r["name"].lower() == k.lower() or slug(r["name"]) == slug(k):
            return r
    raise ValueError(
        "unknown seat %r; seats.tsv has: %s" % (key, ", ".join(r["name"] for r in rows))
    )


def _wild_seat(rows, wild):
    """The wild-card row: seats.tsv's wild seat, or whoever --wild names, kind forced to wild."""
    if not wild:
        wilds = [r for r in rows if r["kind"] == "wild"]
        if not wilds:
            raise ValueError("seats.tsv has no wild seat")
        return dict(wilds[0])
    try:
        w = dict(_find(rows, wild))
    except ValueError:
        # A name outside the roster: the skill writes the creed at run time.
        w = {"name": wild.strip(), "creed": "", "catch": "", "residue": ""}
    w["kind"] = "wild"
    return w


def roll(seed=None, seats=None, wild=None, no_wild=False, rows=None, fast=False):
    rows = read_seats() if rows is None else rows
    n = FAST_REGULARS if fast else N_REGULARS
    regulars = sorted([r for r in rows if r["kind"] == "regular"], key=lambda r: r["name"])
    if seed is None:
        seed = random.SystemRandom().randrange(1, 10**6)
    if seats is not None:
        if len(seats) != n:
            raise ValueError("--seats needs exactly %d names" % n)
        selectable = sorted(
            [r for r in rows if r["kind"] in ("regular", "bench")], key=lambda r: r["name"]
        )
        picked = [_find(selectable, s) for s in seats]
        if len({r["name"] for r in picked}) != n:
            raise ValueError("--seats names the same seat twice")
    else:
        picked = random.Random(seed).sample(regulars, n)
    chosen = [dict(r, kind="regular", slug=slug(r["name"])) for r in picked]
    if not no_wild:
        w = _wild_seat(rows, wild)
        if any(s["name"] == w["name"] for s in chosen):
            # Two drafters would write the same drafts/<slug>.md; the second would overwrite.
            raise ValueError("wild card %r is already seated; pick another" % w["name"])
        w["slug"] = slug(w["name"])
        chosen.append(w)
    for s in chosen:
        if not s["slug"]:
            # The council writes one file per seat and globs them back; a seat with no
            # filename would be drafted and then silently dropped from the run.
            raise ValueError(
                "%r has no filename-safe form; seat that writer under a Latin-letter name"
                % s["name"]
            )
    residue = "|".join(x for s in chosen for x in s["residue"].split("|") if x)
    # critics + graft.residue is the shape the lint's residue check (L6) reads.
    return {
        "seed": seed,
        "fast": bool(fast),
        "seats": chosen,
        "critics": [{"name": s["name"]} for s in chosen],
        "graft": {"residue": residue},
        "target_model": MODEL,
        "frame": FRAME,
    }


# ---------- floor ----------

# Asking the target model to reproduce its reasoning can trip a refusal; the docs list it as
# an audit item, so it fails the floor rather than warning.
REASON_RE = re.compile(
    r"(?i)(\bshow (me )?your (thinking|reasoning|work|steps)\b"
    r"|\bexplain your (thinking|reasoning) (first|before)\b"
    r"|\bwalk me through your (thinking|reasoning)\b"
    r"|\bthink (out loud|aloud)\b"
    # C1 owns step-by-step reasoning-reproduction detection so the instruction has one rule owner.
    r"|\b(think|reason|work)\b[^.\n]{0,20}\bstep[- ]by[- ]step\b"
    r"|\blet\'?s think\b"
    r"|<thinking>|<scratchpad>)"
)
# Written for models that over-narrated or over-formatted. The target model does neither, so
# these lines only silence it.
FOSSIL_RE = re.compile(
    r"(?i)(\bhold (all |your )*(findings|results)\b"
    r"|\bdo not narrate\b|\bdon'?t narrate\b"
    r"|\bno interim (updates?|reports?)\b"
    r"|\b(never|do not|don'?t|avoid) (use |using )?(bullets?|bullet points|headers?|headings?|bold)\b"
    r"|\bno (bullets?|bullet points|headers?|headings?|bold)\b)"
)


EXTRA_CHECKS = (
    ("C1", REASON_RE, "reasoning reproduction: %r; can trip a refusal on " + MODEL),
    ("C2", FOSSIL_RE, "fossil for an older model: %r; " + MODEL + " narrates and formats less"),
)

# The council uses a 1200-word warning and a 1500-word hard limit because a complete draft
# includes substantial frame material.
SOFT_WORDS = 1200
HARD_WORDS = 1500


def extra_checks(prompt):
    findings = []
    for rule, rx, detail in EXTRA_CHECKS:
        m = rx.search(prompt)
        if m:
            findings.append({"rule": rule, "severity": "fail", "detail": detail % m.group(0)})
    n = len(re.findall(r"\S+", prompt))
    if n == 0:
        # Every other rule is vacuously satisfied by an empty prompt, so without this the
        # floor passes a truncated draft and pick ships an empty winner.md.
        findings.append({"rule": "C3", "severity": "fail", "detail": "the prompt is empty"})
    elif n > HARD_WORDS:
        findings.append(
            {"rule": "C3", "severity": "fail",
             "detail": "the prompt is %d words; hard cap %d" % (n, HARD_WORDS)}
        )
    elif n > SOFT_WORDS:
        findings.append(
            {"rule": "C3", "severity": "warn",
             "detail": "the prompt is %d words; soft cap %d" % (n, SOFT_WORDS)}
        )
    return findings


# L1 and L3 through L7 are the council's deterministic lint checks. C1 owns
# reasoning-reproduction wording, and C3 owns empty-input and word-limit enforcement.
# Harness-description and wrapper-only checks do not apply to the council's output contract.
TELLS = (
    "a wide range of",
    "as an AI",
    "best practices",
    "comprehensive",
    "cutting-edge",
    "delve",
    "elevate",
    "ensure that",
    "facilitate",
    "game-changer",
    "holistic",
    "in today's fast-paced",
    "it is important to note",
    "it's important to note",
    "leverage",
    "navigate the landscape",
    "robust",
    "seamless",
    "seamlessly",
    "step-by-step",
    "streamline",
    "synergy",
    "tapestry",
    "utilize",
)
L4_PATTERNS = (
    r"\bif in doubt\b",
    r"\balways use\b",
    r"\bbe as thorough as possible\b",
    r"\bdefault to using\b",
    r"\bwhenever possible,? (use|run|call)\b",
)


def _sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def has_term(text, term):
    """True when TERM appears in TEXT as a whole word or phrase, case-insensitively."""
    return re.search(r"(?i)(?<![\w-])%s(?![\w-])" % re.escape(term), text) is not None


def lint_prompt(prompt, roll=None, idea=None):
    findings = []

    def add(rule, severity, detail):
        findings.append({"rule": rule, "severity": severity, "detail": detail})

    # L1 assistant prefill
    if re.search(r"(?im)^\s*(assistant|a):\s*\S", prompt) or re.search(
        r'"role"\s*:\s*"assistant"', prompt
    ):
        add(
            "L1",
            "fail",
            "assistant prefill present; prefill returns 400 on Claude 4.6+ and Claude 5",
        )
    # L3 example count
    n_ex = len(re.findall(r"<example>", prompt))
    if n_ex > 5:
        add("L3", "fail", "%d <example> blocks; docs say 3 to 5" % n_ex)
    # L4 over-trigger clauses
    for pat in L4_PATTERNS:
        m = re.search(pat, prompt, re.I)
        if m:
            add("L4", "fail", "over-trigger clause: %r" % m.group(0))
    # L5 negation-heavy instructions
    sents = _sentences(prompt)
    neg = [s for s in sents if re.match(r"(?i)^(do not|don'?t|never|avoid|no )", s)]
    if len(sents) >= 8 and len(neg) / len(sents) > 0.25:
        add(
            "L5",
            "fail",
            "%d of %d sentences are negations; state what to do instead"
            % (len(neg), len(sents)),
        )
    # L6 roll residue: the seated writers' names and the words of their world. A word the
    # user's own idea uses is the user's word, not the writer's, so it is waived and logged.
    if roll:
        terms = [c["name"] for c in roll.get("critics", [])]
        terms += [t for t in roll.get("graft", {}).get("residue", "").split("|") if t]
        for term in [t for t in terms if t]:
            if not has_term(prompt, term):
                continue
            if idea and has_term(idea, term):
                add("L6", "warn", "residue %r waived: the idea uses the word" % term)
            else:
                add("L6", "fail", "roll residue in prompt: %r" % term)
    else:
        add("L6", "warn", "no --roll given; residue check skipped")
    # L7 generic tells
    for tell in TELLS:
        if has_term(prompt, tell):
            add("L7", "fail", "generic tell: %r" % tell)
    return findings


def read_roll(roll_path):
    return json.loads(Path(roll_path).read_text(encoding="utf-8")) if roll_path else None


def prompt_of(text):
    """What the floor and the ship step read. A draft that opens a <prompt> tag is judged on
    what is between the tags even when that is nothing; only an untagged file is read whole,
    because otherwise an empty <prompt> block silently falls through to the <note>."""
    return block(text, "prompt").strip() if "<prompt>" in text else text.strip()


def _floor_prompt(prompt, draft_path, roll, idea):
    findings = lint_prompt(prompt, roll, idea) + extra_checks(prompt)
    fails = sum(1 for f in findings if f["severity"] == "fail")
    return {"file": str(draft_path), "findings": findings, "fail_count": fails, "ok": fails == 0}


def floor(draft_path, roll_path, idea_path=None):
    text = Path(draft_path).read_text(encoding="utf-8")
    prompt = prompt_of(text)
    idea = Path(idea_path).read_text(encoding="utf-8") if idea_path else None
    return _floor_prompt(prompt, draft_path, read_roll(roll_path), idea)


# ---------- objections ----------

# parse_objections and validate_objections implement the council's deterministic objection boundary.
OBJ_RE = re.compile(r"<objection\b([^>]*)>(.*?)</objection>", re.S)
ATTR_RE = re.compile(r'(\w+)="([^"]*)"')
OBJ_TAGS = ("claim", "falsifying_input", "expected_divergence", "proposed_change")
MIN_INPUT = 20


def parse_objections(text):
    objs = []
    for m in OBJ_RE.finditer(text):
        attrs = dict(ATTR_RE.findall(m.group(1)))
        o = {k: attrs.get(k, "") for k in ("axis", "critic", "candidate")}
        for tag in OBJ_TAGS:
            o[tag] = block(m.group(2), tag).strip()
        objs.append(o)
    return objs


def validate_objections(objs, min_len=MIN_INPUT, seated=None, source_errors=None):
    valid, dropped = [], []
    source_errors = {} if source_errors is None else source_errors
    for i, o in enumerate(objs):
        fi = o.get("falsifying_input", "")
        reason = source_errors.get(i)
        if reason:
            pass
        elif not fi:
            reason = "falsifying_input missing"
        elif len(fi) < min_len:
            reason = "falsifying_input under %d chars" % min_len
        elif not o.get("claim"):
            reason = "claim missing"
        elif not o.get("expected_divergence"):
            reason = "expected_divergence missing"
        elif seated is not None and o["candidate"] == o["axis"]:
            reason = "candidate %r is the objection's own seat" % o["candidate"]
        elif seated is not None and o["candidate"] not in seated:
            reason = "candidate %r was never seated" % o["candidate"]
        else:
            reason = None
        if reason:
            dropped.append({"index": i, "reason": reason})
            continue
        o = dict(o)
        o["id"] = "OBJ-%s-%s-%02d" % (o["candidate"] or "c", (o["axis"] or "axis")[:12], i)
        valid.append(o)
    return valid, dropped


def objections(path, roll_path=None):
    """Every <objection> in PATH, which may be one file or a directory of <slug>.md files.

    When a roll is supplied, the source filename is authoritative for axis and critic
    identity. Files not owned by seated writers are dropped, as are objections aimed at
    their own seat or a candidate that was not seated.
    """
    p = Path(path)
    directory = p.is_dir()
    if directory:
        files = sorted(p.glob("*.md"))
    elif p.exists():
        files = [p]
    else:
        raise FileNotFoundError("no objections at %s" % p)
    roll = read_roll(roll_path)
    seated_writers, seated = {}, None
    if roll is not None:
        for x in roll.get("seats", []):
            seated_writers[x.get("slug") or slug(x["name"])] = x["name"]
        seated = set(seated_writers) | {"plain"}
    objs = []
    source_errors = {}
    for f in files:
        for o in parse_objections(f.read_text(encoding="utf-8")):
            if seated is not None and f.stem not in seated_writers:
                source_errors[len(objs)] = (
                    "objection file %r does not belong to a seated writer" % f.name
                )
            elif f.stem in seated_writers:
                o["axis"], o["critic"] = f.stem, seated_writers[f.stem]
            objs.append(o)
    valid, dropped = validate_objections(objs, seated=seated, source_errors=source_errors)
    return {"received": len(objs), "valid": valid, "dropped": dropped}


# ---------- pick ----------

WINNER_RE = re.compile(r"WINNER:\s*\**\s*([^\n(*]+)")


def winner_slug(name, roll=None):
    """The seat slug the verdict names. slug() folds case and accents, so the judge may
    write the name, the slug, or the name without its accents."""
    key = slug(name)
    if roll is None:
        return key
    seated = {"plain": "plain"}
    for s in roll.get("seats", []):
        seated[slug(s["name"])] = s.get("slug") or slug(s["name"])
    if key not in seated:
        raise ValueError(
            "the verdict names %r, who was not seated; the roll seated: %s"
            % (name, ", ".join([s["name"] for s in roll.get("seats", [])] + ["plain"]))
        )
    return seated[key]


def pick(verdict_path, drafts_dir, out_path, roll_path=None, draft=None, idea_path=None):
    text = Path(verdict_path).read_text(encoding="utf-8")
    m = WINNER_RE.search(text)
    if not m:
        raise ValueError("no WINNER: line in %s" % verdict_path)
    name = m.group(1).strip().strip("\"\'`*")
    roll = read_roll(roll_path)
    key = winner_slug(name, roll)
    src = Path(draft) if draft else Path(drafts_dir) / (key + ".md")
    if not src.exists():
        raise FileNotFoundError("no draft for winner %r at %s" % (name, src))
    body = src.read_text(encoding="utf-8")
    prompt = prompt_of(body)
    idea = Path(idea_path).read_text(encoding="utf-8") if idea_path else None
    checked = _floor_prompt(prompt, src, roll, idea)
    if not checked["ok"]:
        return checked
    out = Path(out_path)
    try:
        with out.open("x", encoding="utf-8") as winner:
            winner.write(prompt)
    except FileExistsError:
        raise FileExistsError("%s exists; runs are append-only" % out)
    return {"winner": name, "slug": key, "source": str(src), "written": str(out)}


# ---------- entry point ----------


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


def nonempty_argument(value):
    if not value.strip():
        raise ValueError("needs a nonempty value")
    return value


def cmd_pointer(rest):
    p = JsonArgumentParser(prog="council pointer", allow_abbrev=False)
    p.parse_args(rest)
    return emit({"pointer": str(run_pointer(COUNCIL))})


def cmd_init(rest):
    if len(rest) > 1:
        # Invalid invocation must clear the bookmark just like a refused raw argument.
        ptr = run_pointer(COUNCIL)
        if ptr.exists():
            ptr.unlink()
        raise ValueError('init takes one raw argument; quote the whole argument string')
    return emit(init(rest[0] if rest else ""))


def cmd_roll(rest):
    p = JsonArgumentParser(prog="council roll", allow_abbrev=False)
    p.add_argument("--seed", type=int, default=None)
    p.add_argument(
        "--seats", type=seat_list, default=None,
        help="three regular or bench writers, comma-separated"
    )
    p.add_argument("--wild", type=nonempty_argument, default=None,
                   help="seat this name in the wild-card chair")
    p.add_argument("--no-wild", action="store_true")
    p.add_argument("--fast", action="store_true",
                   help="seat %d regulars instead of %d" % (FAST_REGULARS, N_REGULARS))
    a = p.parse_args(rest)
    return emit(roll(a.seed, seats=a.seats, wild=a.wild, no_wild=a.no_wild, fast=a.fast))


def cmd_floor(rest):
    p = JsonArgumentParser(prog="council floor", allow_abbrev=False)
    p.add_argument("draft", type=nonempty_argument)
    p.add_argument("--roll", type=nonempty_argument, required=True)
    p.add_argument("--idea", type=nonempty_argument, default=None,
                   help="waive residue words the idea itself uses")
    a = p.parse_args(rest)
    r = floor(a.draft, a.roll, a.idea)
    return emit(r, 0 if r["ok"] else 2)


def cmd_objections(rest):
    p = JsonArgumentParser(prog="council objections", allow_abbrev=False)
    p.add_argument("path", type=nonempty_argument,
                   help="an objections file, or the directory holding them")
    p.add_argument("--roll", type=nonempty_argument, default=None)
    a = p.parse_args(rest)
    return emit(objections(a.path, a.roll))


def cmd_pick(rest):
    p = JsonArgumentParser(prog="council pick", allow_abbrev=False)
    p.add_argument("verdict", type=nonempty_argument)
    p.add_argument("drafts_dir", type=nonempty_argument)
    p.add_argument("--out", type=nonempty_argument, required=True)
    p.add_argument("--roll", type=nonempty_argument, default=None,
                   help="resolve the winner against this roll")
    p.add_argument("--draft", type=nonempty_argument, default=None,
                   help="ship this file instead of the seat's draft")
    p.add_argument("--idea", type=nonempty_argument, default=None,
                   help="waive residue words the idea itself uses")
    a = p.parse_args(rest)
    result = pick(a.verdict, a.drafts_dir, a.out, a.roll, a.draft, a.idea)
    return emit(result, 2 if result.get("ok") is False else 0)


SUBCOMMANDS = {
    "pointer": cmd_pointer,
    "init": cmd_init,
    "roll": cmd_roll,
    "floor": cmd_floor,
    "objections": cmd_objections,
    "pick": cmd_pick,
}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    fn = SUBCOMMANDS.get(argv[0])
    if fn is None:
        return emit(
            {"error": "unknown subcommand", "name": argv[0], "known": sorted(SUBCOMMANDS)}, 3
        )
    try:
        return fn(argv[1:])
    except (OSError, ValueError) as e:
        return emit({"error": str(e)}, 3)


if __name__ == "__main__":
    sys.exit(main())
