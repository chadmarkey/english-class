---
name: english-class
description: English Class Prompt Council. Turns an idea or a rough prompt into a finished prompt shaped for Claude Fable 5.1 by seating three named editorial lenses rolled from fifteen plus Werner Herzog, drafting five versions in one frame, dropping any that fail the lint floor, running one round of editorial cross-examination where every objection must name a literal failing input, and having Codex judge the survivors. Use on /english-class <idea, rough prompt, or file>, "run the council on this", "have the editorial lenses challenge this prompt". The number of model calls depends on how many drafts survive; `--revise` may add one. `--fast` cuts the run to one drafting call and one judge call: two lenses plus Werner Herzog, the same floor, no cross-examination.
disable-model-invocation: true
---

# English Class Prompt Council

One run, one prompt. Editorial lenses draft and object. The script holds the floor. Codex picks.

The council phases, deterministic floor, length limits, and judge rubric below are English Class
project policy, not vendor guidance.

## Data handling

The full run is not local-only. The idea and frame go to Claude for drafting; later Claude
calls can also receive generated drafts, objections, verdict, or revision material. An
installed and authenticated Codex CLI receives the surviving drafts and valid objections
when it acts as judge. If Codex is unavailable, exits nonzero, or leaves no usable verdict,
the same judge material goes to the Claude fallback. Provider-side storage, telemetry,
retention, and training follow the policies for the configured accounts and services.

Run artifacts remain under `~/.council/runs/` until a human deletes a specifically selected
run. Never prune or delete runs automatically; the README documents the guarded manual
procedure. Secret detection is heuristic and can miss credentials, so never submit secrets.
A recognized secret-like input creates no new run, although `init` can clear an obsolete
pointer before it refuses the input.

Shell variables do not survive between tool calls, so every Bash block below starts with these lines:

```bash
SKILL=~/.claude/skills/english-class
co() { python3 "$SKILL/council.py" "$@"; }   # a function, not a variable: zsh does not split "$CO" into words
pointer_from_json() { python3 -c 'import json,sys; print(json.load(sys.stdin)["pointer"])'; }
POINTER_JSON=$(co pointer) || exit $?
RUNPTR=$(printf '%s\n' "$POINTER_JSON" | pointer_from_json) || exit $?
RUN=$(cat "$RUNPTR" 2>/dev/null)
```

Every subagent prompt ends with the same line, because agent results are truncated in transit: `Write your complete output to {{OUT}} before you return, and return only the path.` Then read that file. Never parse the returned message.

## Refuse first

- No argument: say so in one line and stop.
- The input holds a secret longer than ten characters (a key, token, or password): mask it in every output and stop.

## Flags

`--seed N` replays a roll. `--seats "A,B,C"` fills the three regular chairs with regular or bench seats. `--wild "Name"` fills the wild chair instead of seating Herzog for one run. `--no-wild` leaves the chair empty. `--fast` seats two regulars instead of three, drafts them and the wild chair in one call with no plain seat, skips cross-examination, and judges on a faster model; with it, `--seats` takes two names and `--revise` is refused, because a revision answers objections and a fast run files none. A bare `--` ends the flags; everything after it is the idea, even when it starts with a known flag name. Bench seats are never rolled by default.

Put flags before the idea. Value-taking flags require a nonempty value; `--wild=`, quoted-empty values, and whitespace/comma-only `--seats` lists are refused. A following known flag or bare `--` cannot supply a missing value. Quote a literal flag-leading value inside the argument string (`--wild "--revise"`) or attach it with `=` (`--wild=--revise`); an attached value must begin immediately after `=`. `--no-wild`, `--revise` and `--fast` take no value. Unknown words, including `--wild-card`, start the idea and remain unchanged.

## 0. Init

```bash
INIT=$(co init "$ARGUMENTS")
INIT_STATUS=$?
if [ "$INIT_STATUS" -ne 0 ]; then
  printf '%s\n' "$INIT"
  exit "$INIT_STATUS"
fi
RUNPTR=$(printf '%s\n' "$INIT" | pointer_from_json) || exit $?
RUN=$(cat "$RUNPTR") || exit $?
printf '%s\nRUN=%s\n' "$INIT" "$RUN"
```

If that block printed an `error` instead of a `RUN=` line, print the error, say no new run was created, and stop. Do not run any later step: `init` clears the run pointer before it does anything else, so there is no run to fall back to, and a run from an earlier `/english-class` in this directory is not yours to write into.

Pass exactly one shell argument to `init`, as above; separately supplied words or flags are refused. Every CLI invocation error prints exactly one JSON object containing `error` to stdout and exits 3, with no usage text or error prose on stderr. This includes unknown direct-subcommand options, missing operands or values, and invalid or blank values. Direct subcommands require full option names; for a flag-leading option value use `--option=value`, and for a flag-leading positional path put `--` before it. Top-level and direct-subcommand `--help` remain successful help requests; inside `init`'s raw argument, `--help` is idea text.

`init` takes the whole argument, splits it, and lifts `--seed N`, `--seats "A,B,C"`, `--wild "Name"`, `--no-wild`, `--revise` and `--fast` out of it; whatever is left is the idea, or the file to read when it names one. It refuses an empty idea, an idea holding a key, a token, or a password, and a `--seed` that is not a number, and creates no new run in any of those cases. The parser trims surrounding whitespace from the inline idea or UTF-8 file contents, preserves the remaining punctuation, spaces, tabs, and newlines, and saves that text to `$RUN/idea.md` with a trailing newline. A word that is not a known flag stays part of the idea. Otherwise it makes the run directory with `drafts/`, `lint/` and `objections/` inside it, writes `$RUN/roll.json`, points `$RUNPTR` at the run, and prints one JSON object with `run`, `seed`, `seats`, `revise`, `fast`, and `pointer`. Phase 0 reads `RUNPTR` from that successful result; later blocks ask `council.py pointer` for the same Python-owned working-directory pointer.

Print the seed and the seated names: four in a full run, three in a fast one. Keep the `revise` and `fast` values; step 4b runs only when `revise` is true, and `fast` changes steps 1, 3 and 4 as each of them says. If a seat's `creed` and `catch` are empty (a `--wild` name not in `seats.tsv`), use this fixed neutral fallback creed: "Challenge the draft from a neutral outsider perspective. Expose unstated assumptions, high-stakes failure modes, and unclear success criteria." Use this fixed fallback catch: "A claim that depends on hidden context or a failure mode the prompt never makes testable." The custom name is only a seat label and supplies no beliefs, style, or quotations; do not research, imitate, quote, or infer beliefs from it.

## 1. Draft

Five subagents in one message, in parallel, all on opus: one **Drafter** per seat in `roll.json`, plus one plain seat. Fill `{{IDEA}}` from `idea.md`, `{{FRAME}}` with the full contents of `$SKILL/frame-fable-5.1.md`, and `{{NAME}}`, `{{CREED}}`, `{{CATCH}}` from the seat. The plain seat uses the **Plain drafter** variant. `{{OUT}}` is `$RUN/drafts/<slug>.md`, using the `slug` value `co init` printed for that seat, never a slug you work out from the name; the plain seat is `plain`.

In a fast run (`"fast": true`), spawn one **Fast drafter** subagent instead, on sonnet, and no plain seat. Fill `{{IDEA}}` and `{{FRAME}}` as above, and repeat the `<seat>` element once per entry in `roll.json`, each with that seat's `{{NAME}}`, `{{CREED}}`, `{{CATCH}}`, and its own `{{OUT}}` of `$RUN/drafts/<slug>.md`. One call writes every draft; the floor below runs on whatever files it finds, so nothing else changes.

## 2. Floor

```bash
for f in "$RUN"/drafts/*.md; do s=$(basename "$f" .md); co floor "$f" --roll "$RUN/roll.json" --idea "$RUN/idea.md" > "$RUN/lint/$s.json"; done
grep -l '"ok": false' "$RUN"/lint/*.json
```

A draft whose lint file says `"ok": false` is out. Print each dropped seat with its failing rules in one line: L1 and L3 through L7 by their detail text, C1 for a reasoning-reproduction instruction, C2 for a fossil written for an older model, C3 for a prompt over the hard word cap.

If every draft is out, print every seat's findings, write `$RUN/verdict.md` holding the two lines `NO WINNER` and `Every draft failed the floor; nothing shipped.`, and stop there. Do not run step 5. A council that cannot clear its own floor has no winner to hand over, and shipping the plain draft anyway would hide that.

## 3. Cross-examination

One **Examiner** subagent per surviving named seat (not the plain seat), in one message, in parallel, on opus. Fill `{{NAME}}`, `{{CREED}}`, `{{CATCH}}`, `{{SLUG}}`, `{{OWN}}` with that seat's `<prompt>` block, and `{{RIVALS}}` with every other surviving draft's `<prompt>` block, each wrapped as `<rival seat="slug">…</rival>`. `{{OUT}}` is `$RUN/objections/<slug>.md`. Then:

```bash
co objections "$RUN/objections" --roll "$RUN/roll.json" > "$RUN/objections.json"
python3 -c "import json;o=json.load(open('$RUN/objections.json'));print('received',o['received'],'kept',len(o['valid']),'dropped',len(o['dropped']))"
```

Print that tally. If no named seat survived the floor there are no examiners to spawn; run the block anyway, because an empty `objections/` directory returns `received 0` and the judge then reads the drafts alone. In a fast run (`"fast": true`) there are no examiners either: spawn none, run the block, and carry the `received 0` tally into the final report.

`co objections` accepts either one objection file or a directory of them. With `--roll`,
each source filename is authoritative: a seated entry's `axis` and `critic` are restamped
from the filename and roll, ignoring those attributes inside the file, while a source whose
filename does not belong to a seated entry is counted as received but dropped. Without
`--roll`, the attributes inside each objection are preserved and filename and candidate
seating checks are skipped; the ordinary claim, falsifying-input, and expected-divergence
checks still apply.

## 4. Judge

Write `$RUN/judge_prompt.md` from the **Judge** template. `{{DRAFTS}}` is every surviving draft as `<draft seat="slug" name="Seat Name">` holding its `<prompt>` and `<note>`. `{{OBJECTIONS}}` is the `valid` list from `objections.json`, each as one `<objection critic="…" candidate="…">` holding its claim, falsifying_input, and expected_divergence. Use the `critic` and `candidate` values from the script's validated output. The script restamps `axis` and `critic` from the source filename and roll, then validates `candidate` against the seated entries and plain baseline and rejects self-objections. Then:

```bash
if command -v codex >/dev/null 2>&1; then
  codex exec -s read-only -C "$RUN" --skip-git-repo-check --ephemeral -o "$RUN/verdict.md" - < "$RUN/judge_prompt.md" > /dev/null 2> "$RUN/judge.stderr" || echo "codex exited non-zero; see $RUN/judge.stderr"
fi
test -s "$RUN/verdict.md" && head -1 "$RUN/verdict.md" || echo "no verdict from codex"
```

If there is no verdict, spawn one subagent with the same judge prompt, on opus in a full run and on sonnet in a fast run, `{{OUT}}` set to `$RUN/verdict.md`, and this line added at the top of its instructions: `Begin your file with the line: JUDGE: claude-opus (codex unavailable)`.

## 4b. Revise, only when the run asked for it

Run this step only when step 0 printed `"revise": true`, and skip it when the winner is the plain seat: there is no named lens to hand the objections to.

Spawn one **Reviser** subagent for the winning seat. `{{OWN}}` is that seat's `<prompt>` block, `{{OBJECTIONS}}` is every valid objection in `objections.json` whose `candidate` is that seat's slug, `{{VERDICT}}` is the text of `$RUN/verdict.md`, and `{{OUT}}` is `$RUN/revision.md`. Then:

```bash
co floor "$RUN/revision.md" --roll "$RUN/roll.json" --idea "$RUN/idea.md" > "$RUN/lint/revision.json"
```

If the revision passes the floor, ship it: add `--draft "$RUN/revision.md"` to the `co pick` call in step 5, and say it was revised once against however many objections it answered. If it fails, ship the original draft and say which rule the revision broke. A revision that cannot clear the floor is worse than the draft that did.

## 5. Ship

```bash
co pick "$RUN/verdict.md" "$RUN/drafts" --roll "$RUN/roll.json" --idea "$RUN/idea.md" --out "$RUN/winner.md"
```

`pick` rechecks the selected source through the same floor immediately before shipping,
including a revision supplied with `--draft`. A floor failure prints its one JSON result,
exits 2, and creates no `winner.md`; an invocation, parsing, or I/O failure exits 3. A
passing prompt ships normally, and an existing `winner.md` is never altered.

Print, in this order: the seed and the seats; who was dropped at the floor and why; the objection tally, and in a fast run the line `Fast run: cross-examination skipped, so the judge read the drafts alone.`; the verdict in full; the winner from `winner.md` in a fenced block; then one line: `The whole fight is in $RUN.` Nothing under `~/.council/runs` is ever edited or deleted; the run pointer beside it is rewritten every run.

## Templates

Fill the double-brace slots and send nothing else.

### Drafter

```
Apply the {{NAME}} editorial lens using only the supplied lens text. The name labels the seat; do not imitate, quote, or infer beliefs from it. Work as an editor, not as a narrator. Editorial lens: {{CREED}} Look especially for: {{CATCH}}

The council has one job: turn the idea below into the prompt a human will paste to Claude Fable 5.1. Write that prompt in the frame that follows, and apply only the supplied editorial criteria to every sentence. Do not introduce biographical details, references to creative works, quotations, or stylistic imitation. The prompt is for the human's reader, not for the seat label.

<idea>
{{IDEA}}
</idea>

<frame>
{{FRAME}}
</frame>

Keep the prompt under 1500 words. A script drops longer drafts at the floor before anyone reads them, and it warns above 1200, so spend the budget on the context and the done-state.

Output exactly two tagged blocks and nothing outside them:
<prompt>the prompt, ready to paste</prompt>
<note>three sentences of direct editorial rationale explaining what you cut or refused to write, and why</note>

Write your complete output to {{OUT}} before you return, and return only the path.
```

### Plain drafter

```
Serve as the plain seat on the council: no creed and no named editorial lens. Turn the idea below into the prompt a human will paste to Claude Fable 5.1, written in one pass in the frame that follows.

<idea>
{{IDEA}}
</idea>

<frame>
{{FRAME}}
</frame>

Keep the prompt under 1500 words. A script drops longer drafts at the floor before anyone reads them, and it warns above 1200, so spend the budget on the context and the done-state.

Output exactly two tagged blocks and nothing outside them:
<prompt>the prompt, ready to paste</prompt>
<note>one sentence on the choice you were least sure of</note>

Write your complete output to {{OUT}} before you return, and return only the path.
```

### Fast drafter

```
Serve as every seat of the council in one pass. Apply each seat's editorial lens using only the supplied lens text. The name labels the seat; do not imitate, quote, or infer beliefs from it. Work as an editor, not as a narrator.

The council has one job: turn the idea below into the prompt a human will paste to Claude Fable 5.1. Write one prompt per seat in the frame that follows, and apply only that seat's editorial criteria to every sentence of its draft. Do not introduce biographical details, references to creative works, quotations, or stylistic imitation. The prompt is for the human's reader, not for the seat label.

<idea>
{{IDEA}}
</idea>

<frame>
{{FRAME}}
</frame>

<seats>
<seat name="{{NAME}}" out="{{OUT}}">Editorial lens: {{CREED}} Look especially for: {{CATCH}}</seat>
</seats>

Keep each prompt under 1500 words. A script drops longer drafts at the floor before anyone reads them, and it warns above 1200, so spend the budget on the context and the done-state.

For each seat, write the file named by its out attribute holding exactly two tagged blocks and nothing outside them:
<prompt>the prompt, ready to paste</prompt>
<note>two sentences of direct editorial rationale explaining what that lens cut or refused to write, and why</note>

Write every file completely before you return, and return only the paths, one per line.
```

### Examiner

```
Apply the {{NAME}} editorial lens using only the supplied lens text. The name labels the seat; do not imitate, quote, or infer beliefs from it. Work as an editor, not as a narrator. Editorial lens: {{CREED}} Look especially for: {{CATCH}}

Below is the prompt from your seat and the prompts from the rival seats for the same idea. File exactly one objection against each rival. An objection counts only if it names a literal input, at least twenty characters long, that could reach the reader of that prompt (a line in a file, words from the user, a state of the repo) and on which the rival's prompt and yours would make the reader behave differently. Say what each would do. Objections without such an input are discarded by a script, so write no general advice. Apply the supplied editorial lens to the claim; keep the input and divergence literal.

<own seat="{{SLUG}}">
{{OWN}}
</own>

<rivals>
{{RIVALS}}
</rivals>

Use exactly this format, one block per rival, nothing outside the blocks:
<objection axis="{{SLUG}}" critic="{{NAME}}" candidate="RIVAL_SLUG">
  <claim>one sentence</claim>
  <falsifying_input>the literal input</falsifying_input>
  <expected_divergence>rival does X; mine does Y</expected_divergence>
  <proposed_change>one sentence, or omit</proposed_change>
</objection>

Write your complete output to {{OUT}} before you return, and return only the path.
```

### Reviser

```
Apply the {{NAME}} editorial lens using only the supplied lens text. The name labels the seat; do not imitate, quote, or infer beliefs from it. Work as an editor, not as a narrator. Editorial lens: {{CREED}} Look especially for: {{CATCH}}

The draft from your seat won. Below is that prompt, the surviving objections filed against it, and the judge's verdict. Revise the prompt once against them, as an edit and not a rewrite: keep the frame and the shape. An objection that names an input the prompt would really get wrong is answered by changing the prompt. An objection that does not land is answered by leaving the prompt as it stands and saying why in the note.

<prompt>
{{OWN}}
</prompt>

<objections>
{{OBJECTIONS}}
</objections>

<verdict>
{{VERDICT}}
</verdict>

Keep the prompt under 1500 words. A script drops longer drafts at the floor before anyone reads them, and it warns above 1200, so spend the budget on the context and the done-state.

Output exactly two tagged blocks and nothing outside them:
<prompt>the revised prompt, ready to paste</prompt>
<note>one line per objection: what you changed, or why you left it</note>

Write your complete output to {{OUT}} before you return, and return only the path.
```

### Judge

```
You judge a council of editorial lenses that each produced a prompt for the same idea for Claude Fable 5.1. Judge every draft against the supplied frame, rewarding clear goals, constraints, evidence, and completion criteria without rewarding gratuitous method prescription.

Rubric, in order:
1. Goal and done-state before optional method. The prompt states the outcome, the relevant constraints with their reasons, the evidence it should use, and what done looks like. Penalize choreography the task does not require.
2. Every slot the prompt type needs is present, and none is empty or generic.
3. A new colleague with no context could follow it without confusion.
4. The objections: which land? An objection lands when the named input would really make the reader go wrong under that prompt.
5. Ties go to the shortest draft that still does all of the above.

<drafts>
{{DRAFTS}}
</drafts>

<objections>
{{OBJECTIONS}}
</objections>

Reply in at most two hundred words. First line exactly: WINNER: <the name attribute of the winning draft>. Then the single line from the winner that decided it, quoted. Then one sentence per losing draft on what it did better than the winner. Then the assumptions the drafts made about the idea that the human should confirm.
```

## Maintenance

- A seat lives in three files: the row in `seats.tsv`, the profile in `README.md`, and the line in `SPEC.md`'s table. A test holds all three equal, so edit them together and run `python3 -m unittest discover -s "$SKILL/tests"`.
- The six `bench` rows are installed in `seats.tsv`. They are never rolled by default; seat one explicitly with `--seats` or `--wild`.
- The frame in `frame-fable-5.1.md` paraphrases Anthropic's [Claude Fable 5.1 prompting guide](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5-1), accessed 2026-09-04. A new model gets its own `frame-<model>.md` plus new `MODEL` and `FRAME` constants in `council.py`; the three templates that name the model change with it, and the frame itself is never edited to fit a second model.
