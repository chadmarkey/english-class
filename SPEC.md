# English Class Prompt Council — design spec

Date: 2026-09-03. Command: `/english-class`. Status: built, v0.1.0.

## Purpose

A small, fast, fun skill that turns an idea or a rough prompt into a finished prompt by
letting a council of editorial lenses challenge it. Five drafts, one round of cross-examination,
a deterministic floor, and a cross-vendor judge. Drafts run in parallel, later calls depend
on which drafts survive, and `--revise` can add one revision. The winner is saved as a bare
prompt, ready to paste, shaped for Claude Fable 5.1.

It takes any prompt: a system prompt, a one-off ask, a kickoff brief, or a prompt you
already have and want fixed.

## Non-goals

- No intake interview. The skill takes the idea and goes; the judge lists the assumptions the
  drafts made.
- No simulation of the reader's first turn.
- No revision rounds unless asked for. Drafts are judged as written after one round of
  objections; `--revise` adds one round for the winner alone, re-floored before it ships.
- The complete deterministic floor is implemented in `council.py`; no gate logic is loaded
  from or delegated to another project.

## Files

```
~/.claude/skills/english-class/
  SKILL.md              the run, as the model executes it
  SPEC.md               this file
  frame-fable-5.1.md    the shape every draft must take (the Fable 5.1 frame), read by drafters
  seats.tsv             the council roster: 15 regulars + 6 bench + 1 wild card
  council.py            init, roll, floor, objections, pick; standard library, Python 3.9
  tests/test_council.py roster shape, roll determinism, the floor, the objections, the pick
```

Runs are saved under `~/.council/runs/<slug>-<YYYYmmdd-HHMMSS>/`, with a `-2` suffix in the
unlikely event two runs in one directory land in the same second. Nothing under that tree is
ever edited or deleted by the skill. The run pointer next to it,
`~/.council/current_run.<sha256>`, is rewritten every run; it is a bookmark, not a record.
The digest is the lowercase SHA-256 of the resolved physical working-directory path, encoded
with the filesystem encoding. Symlinked and physical paths therefore share one identity,
while path punctuation, whitespace, and newlines remain distinct inputs. `council.py` alone
derives the pointer; shell blocks consume its JSON `pointer` field.

The helper depends on nothing but Python 3.9 and its standard library. The lint rules,
generic-tells table, and objection filter are implemented in this repository. The full
skill can use the `codex` CLI for the judge, with an opus subagent as fallback.

The council phases, deterministic floor, word limits, and judge rubric are English Class project
policy rather than vendor guidance.

## Data handling

The full skill is not local-only. The parser trims surrounding whitespace from the inline
idea or UTF-8 file contents, preserves the remaining characters, and stores that text in
`idea.md` with a trailing newline. Claude receives the idea and frame for drafting, and later
Claude calls can receive generated drafts, objections, the verdict, or revision material.
If an installed and authenticated Codex CLI is available, it receives the surviving drafts
and valid objections in the judge prompt. If Codex is absent, exits nonzero, or produces no
usable verdict, the same judge material goes to an opus fallback. Provider-side storage,
telemetry, retention, and training follow the policies for the configured accounts and
services.

Run directories can contain `idea.md`, `roll.json`, drafts, lint results, objections, the
judge prompt and stderr, the verdict, an optional revision, and `winner.md`. They are
append-only and remain until a human deliberately deletes one; there is no expiry, pruning,
or automatic cleanup. The current-run pointer is only a replaceable bookmark. Secret
detection is heuristic, covers the submitted idea rather than every generated artifact, and
can miss credentials. Users must not submit secrets. A recognized secret-like input creates
no new run or model call, although `init` can clear an obsolete pointer before refusing it.

## The council

Three named editorial lenses are rolled per run from the fifteen regulars. The six bench
lenses are never rolled, but `--seats` can place regular or bench entries in the three regular chairs. The wild
card is seated every run unless `--wild` fills that chair or `--no-wild` removes it. Profiles
and bench summaries are in `README.md`; the roster of record, including every creed, catch,
and banned word, is `seats.tsv`, and a test keeps this table's names equal to it.

The project does not claim participation, affiliation, or endorsement by any named person,
estate, publisher, or representative.

| Seat | Kind | Editorial lens | What it catches |
|---|---|---|---|
| Cormac McCarthy | regular | Test every sentence for structural weight. Remove decoration, hedges, and punctuation that substitutes for a clear relationship between ideas. | Language that adds surface without carrying meaning. |
| David Foster Wallace | regular | Preserve necessary complexity without letting it become clutter. Add the caveat that would materially change the reader’s decision, and cut the rest. | The omitted qualification that makes a simple answer misleading. |
| Junot Díaz | regular | Use a natural spoken register suited to the actual reader. Keep the language direct, specific, and consistent instead of drifting into institutional prose. | Stiff phrasing, unexplained register changes, and sentences nobody would say aloud. |
| Atul Gawande | regular | Turn complex work into an ordered set of checks. Make every step before an irreversible action visible and verifiable. | A skipped prerequisite or missing check at the point of no return. |
| Oliver Sacks | regular | Ground the instruction in one concrete case that a reader can follow from input to result. Let the example test the abstraction. | A general rule with no worked instance or observable case. |
| Robert Sapolsky | regular | Separate causes by level and timescale. State whether a claim concerns the immediate trigger, surrounding conditions, or longer history. | A single-cause explanation that mixes levels or ignores timing. |
| Ernest Hemingway | regular | Keep only what carries the task, constraint, or consequence. Let precise structure do more work than explanation. | Words or clauses that are not load-bearing. |
| Mark Twain | regular | Choose the exact ordinary word and remove inflated substitutes. Prefer precision over decoration. | Padding, pomposity, and almost-right diction. |
| George Orwell | regular | Use plain, active language that identifies the actor and the action. Replace jargon and hedges with accountable statements. | Passive or abstract phrasing that hides who must do what. |
| Anton Chekhov | regular | Make every setup serve a later instruction, decision, or test. Remove promises and context that never affect the outcome. | A setup with no payoff or an instruction with no downstream effect. |
| Lewis Carroll | regular | Define important terms once and use them consistently. Make exceptions explicit before they can change the rule. | An undefined term, a word used in two senses, or a hidden exception. |
| G.K. Chesterton | regular | Before removing or replacing something, establish the purpose it serves. Preserve that purpose unless the task explicitly changes it. | A refactor or deletion requested without understanding the existing rationale. |
| Franz Kafka | regular | Ensure every constraint is discoverable and satisfiable before asking the reader to comply. Eliminate circular or trap-like requirements. | A rule that can be learned only by violating it, or a requirement that cannot be met. |
| Edgar Allan Poe | regular | Choose one intended effect and a concrete done-state, then make each instruction support them. | A prompt with competing effects or no visible completion condition. |
| Rudyard Kipling | regular | Check that the reader can identify who acts, what changes, why it matters, when and where it applies, and how success is shown. | The missing member of who, what, why, when, where, and how. |
| Jane Austen | bench | Challenge universal claims by naming whose perspective they reflect, what evidence supports them, and where they stop applying. | A local assumption presented as common or universal truth. |
| Sun Tzu | bench | Inspect the actual environment before committing to a plan. Make repository state, tools, constraints, and dependencies explicit. | A plan that assumes its terrain instead of checking it. |
| Agatha Christie | bench | Provide every fact needed for the requested conclusion before asking for a verdict. Let organization create clarity, not withheld evidence. | A conclusion that depends on a clue the prompt never supplies. |
| Voltaire | bench | Ask for the smallest result that is complete, useful, and verifiable. Do not make optional polish a condition of finishing. | Perfectionism that expands scope beyond a usable result. |
| Oscar Wilde | bench | Make clarity engaging without turning seriousness into ceremony. State the strongest relevant objection and require the final answer to survive it. | Dull consensus or a polished claim that avoids the best dissent. |
| Arthur Conan Doyle | bench | Separate direct observations from inferences. Require each conclusion to identify the evidence and reasoning that support it. | An inference reported as fact or a deduction without evidence. |
| Werner Herzog | wild card | Make the stakes and consequences tangible. A technically correct prompt should still reveal why the outcome matters. | A correct but inert instruction with no meaningful consequence. |

## The run

`/english-class <idea, rough prompt, or path to a file holding one>`

Flags: `--seed N` replays a roll. `--seats "A,B,C"` fills the three regular chairs by name
with regular or bench entries. `--wild "Name"` fills the wild chair for one run; `--no-wild`
drops it. `--revise` adds one revision round for the winner. `--fast` seats two regulars, drafts
every seat in one call with no plain seat, skips cross-examination, and judges on a faster
model; with it `--seats` takes two names and `--revise` is refused, since a revision answers
objections a fast run never files. The same name cannot be seated
twice; the script refuses, because two drafters would write one file. Every flag is parsed by
`council.py init` out of the single argument string, because a shell that does not word-split
an unquoted variable cannot be trusted to assemble a command line.

Flags precede the idea and match complete names. Unknown words such as `--wild-card`
start the idea. A bare `--` ends flag parsing, so `-- --wild behavior` preserves the
flag-leading idea. Value-taking flags reject missing, empty, quoted-empty, and
whitespace-only values; `--seats` also rejects lists containing only commas and whitespace.
A following known flag or bare `--` is not a value. Quote a literal flag-leading value
inside the raw argument or attach it with `=`; attached values start immediately after `=`.
The bare flags `--no-wild`, `--revise` and `--fast` reject attached values.

CLI contract: each invocation failure prints exactly one JSON object containing `error`
to stdout, exits 3, and leaves stderr empty. The direct subcommands reject unknown or
abbreviated options, missing operands, missing values, and invalid or blank values before
running. Direct option values beginning with a flag use `--option=value`; positional paths
beginning with a flag use the bare `--` separator. Successful top-level and direct-subcommand
help requests retain help text and exit 0. With no subcommand, the CLI also displays help.
`init` takes one raw shell argument; `--help` inside it is idea text.

Refusals, checked first:
- No argument: say so in one line and stop.
- The input contains a secret longer than ten characters: mask it in every output and stop.

Phase 0, init. `council.py init "<the whole argument>"` splits the argument, lifts the flags
out of it, and treats the rest as the idea or as the file to read when it names one. It exits
3 on malformed flags or separately supplied shell arguments, on an empty idea,
on a `--seed` that is not a number, and on an idea holding something
key-shaped, token-shaped, or password-shaped, masking the value and creating no new run. It
clears the run pointer before anything else, so a refused run leaves no bookmark for the
next step to follow into someone else's run. The idea is never shell-tokenized: the parser
trims surrounding whitespace from the inline remainder or UTF-8 file contents, preserves
the remaining punctuation, spaces, tabs, and newlines, and writes the result to `idea.md`
with a trailing newline. Otherwise it makes `runs/<slug>-<stamp>/` with `drafts/`, `lint/`
and `objections/` inside, rolls, writes `roll.json`, writes the run pointer, and returns that
pointer in its JSON result. Phase 0 consumes the returned field only after init succeeds.
Later shell blocks use the zero-argument `council.py pointer` JSON command to recover the
same Python-derived pointer without reproducing its digest or canonicalization rules.

`roll` reads `seats.tsv`, picks three regulars with the seed (or the three regular or bench
entries named by `--seats`), adds the wild chair, and returns
`{"seed","seats":[{name,kind,creed,catch,residue,slug}], "critics":[{name}],
"graft":{residue}, "target_model", "frame"}`. `critics` and `graft` are the shape the residue
check reads; `target_model` and `frame` record which model a run was written for. `kind` names
the occupied chair: a bench entry selected with `--seats` is `regular`, and any entry
selected with `--wild` is `wild`. Print the seed and the four names. The run pointer is keyed
by working directory, so two councils in two repos never read each other's run.

Phase 1, draft. Five subagents in parallel, all on opus: one per seat plus one plain seat.
Each gets the idea, `frame-fable-5.1.md`, and its supplied editorial lens. It is told to edit
rather than imitate or narrate: write the prompt in the frame, then give three sentences of
direct editorial rationale about what it cut and why. The plain seat gets the idea and the frame, no lens. Each writes to
`drafts/<slug>.md` (prompt inside `<prompt>` tags, note inside `<note>`) and returns only the
path; the main session reads the file, never the returned message.

Phase 2, floor. `council.py floor drafts/<slug>.md --roll roll.json --idea idea.md` for each
draft. The floor reads what is between the `<prompt>` tags, or the whole file when there are no
tags, and applies nine local rules implemented in `council.py`: L1 assistant prefill, L3 more
than five examples, L4 over-trigger clauses, L5 negation-heavy instructions, L6 the seated
names and banned words, and L7 the generic tells. C1 through C3 cover reasoning
reproduction, fossilized instructions, and length:
- C1, reasoning reproduction ("show your thinking", "think step by step", thinking or
  scratchpad tags), because the project does not treat private reasoning reproduction as a
  useful prompt deliverable;
- C2, fossils ("hold all findings", "don't narrate", "no interim updates", "never use
  bullets", "no headers", "no bold"), because project policy allows concise progress and
  useful structure instead of suppressing them categorically;
- C3, length: a warning above 1200 words, a failure above 1500, and a failure at zero,
  because every other rule is vacuously satisfied by an empty prompt.
L6 waives a banned word the idea itself uses, and records the waiver, because a word the user
wrote belongs to the user's request, not to the editorial lens. A draft with any fail is dropped, and the skill prints
who was dropped and the rule. If every draft fails, the run writes `NO WINNER` and ships
nothing; a council that cannot clear its own floor has no winner to hand over.

Phase 3, cross-examination. One subagent per surviving named seat, in parallel, on opus.
Each reads every other surviving draft and files one lens-based objection per rival in the
`<objection>` format `council.py objections` parses. Every objection must name a literal
input, at least twenty characters, on which the two prompts would make the reader behave
differently; the filter drops the rest. `objections` accepts one file or a directory.
`objections objections/ --roll roll.json` is the normal run: with a roll, every source file
must be named for a seated entry, `axis` and `critic` are restamped from that filename and
the roll because examiners mislabel themselves, and an unseated source is counted as
received but dropped. The filter also drops any block aimed at its own seat or at an entry
who was never seated. Without a roll, embedded `axis` and `critic` values are preserved and
filename and candidate seating checks are skipped, while the ordinary content checks still
apply. An empty directory returns `received 0`, which is what happens when no named seat
survived the floor. Print the tally: received, kept, dropped.

Phase 4, judge. Build `judge_prompt.md`: the rubric, every surviving draft, every surviving
objection. Run Codex non-interactively, read-only, no saved session:

```bash
codex exec -s read-only -C "$RUN" --skip-git-repo-check --ephemeral \
  -o "$RUN/verdict.md" - < "$RUN/judge_prompt.md"
```

If `codex` is not on the path or exits non-zero, run the same prompt through an opus
subagent and write `JUDGE: claude-opus (codex unavailable)` as the first line of the verdict.

The rubric, in order: goal over method (outcome, constraints, done-state stated; method left
to the reader; choreography penalized); every slot the prompt type needs is present and none
is empty or generic; a new colleague with no context could follow it without confusion; which
objections land. Ties go to the shortest complete draft. The verdict's first line is
`WINNER: <seat>`, then the deciding line quoted, one sentence per loser on what it did
better, and the assumptions the drafts made, in at most two hundred words.

Phase 4b, revise, only when `--revise` was given and the winner is not the plain seat. The
winning seat gets its own prompt, the valid objections aimed at it, and the verdict, and
returns one revision to `revision.md`. The revision goes through the same floor as every
draft. It ships only if it passes; otherwise the original ships and the run says which rule
the revision broke.

A fast run (`--fast`) keeps phases 0, 2, 4 and 5 and shortens the rest: one drafting call
writes every seated draft, no examiners run, `objections` returns `received 0`, and the judge
reads the drafts alone. The seeded roll, the floor, the no-imitation rule and the final
recheck in `pick` are unchanged. Only the objections are given up, and the run says so.

Phase 5, ship. `council.py pick verdict.md drafts/ --roll roll.json --idea idea.md --out
winner.md` runs the selected source through the final floor with the same roll and idea, then
copies its `<prompt>` block to `winner.md`, bare. This applies to the ordinary winner and to a
revision selected with `--draft`. A floor failure returns its one JSON result, exits 2, and
creates no `winner.md`; an invocation, parsing, or I/O failure exits 3. A passing prompt ships
normally, and an existing `winner.md` is never altered. With `--roll`, `pick` resolves the
verdict's `WINNER:` line against the seated names, accepting the name, the slug, or the name
without its accents, and naming the seated entries when it matches none. Print, in order: the
seed and seats, who was dropped at the floor, the objection tally, the verdict, the winner in
a fenced block, and the run path.

## The frame

`frame-fable-5.1.md` is the shape every draft takes. It paraphrases Anthropic's
[Claude Fable 5.1 prompting guide](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5-1), accessed 2026-09-04. Top to bottom:

1. `<context>`: one sentence of role, then what larger task this serves, who it is for, what
   the output lets them do, and the environment facts the reader cannot discover on its own.
2. `<documents>`: long material, if any, above the task, each document in its own tagged
   block with a source.
3. `<task>`: the request in the imperative. The scope is the deliverable. What done looks
   like, checkable by a stranger.
4. `<constraints>`: the few real ones, each with its reason. Boundaries as what to do. Exact
   commands only where one sequence is safe.
5. `<working_style>`: only the behaviors the prompt needs: sparse progress updates, batched
   independent tool work, targeted edits, scope control, and exact preservation of
   hard-to-reconstruct values when context is summarized.
6. `<output>`: the required result, its evidence, and clear sections or illustrative examples
   only where they disambiguate the requested form.
7. `<verify>`: one line, check the result against the done-state before finishing.
8. Closing guidance: finish the requested result when continued tool use can do so, batch
   independent work, and settle the structure before producing a long deliverable.

A slot is used only when the prompt needs it, with no empty headings. The frame states the
source-backed ideas in original language: define the outcome, constraints, and done-state;
avoid unnecessary method prescription; request targeted changes; separate sections when
boundaries matter; keep progress updates sparse; batch independent tool work; and preserve
exact hard-to-reconstruct values through context summaries. Its deterministic floor, council
workflow, word cap, and preference for goals and evidence over gratuitous choreography are
identified separately as English Class project policy.

## Tests

`tests/test_council.py`, standard library `unittest`, run with
`python3 -m unittest discover -s ~/.claude/skills/english-class/tests`:

- `seats.tsv` has twenty-two rows: fifteen regulars, six bench entries, and one wild card;
  names are unique, every creed, catch, and residue is nonempty, and the names in this spec's
  table equal the roster.
- `roll(seed)` returns the same three regulars twice for the same seed, three distinct names,
  the wild card last; bench entries are never rolled; `--seats` overrides the roll with
  regular or bench entries and rejects a repeated name; `--wild` rejects an entry already
  seated.
- every floor rule has a failing case; `floor` on a clean draft returns no fails; "think
  step by step" fails with C1; "hold all findings for the end" fails with C2; the word caps
  warn then fail; a seated entry's banned word fails, unless the idea uses it, in which case
  it warns; "fork in the road" passes a McCarthy seat; `tests/fixtures/corpus.txt`, twelve
  everyday sentences, draws no failure from any seat on the roster.
- `objections` tests use a standalone synthetic fixture with 12 received, 12 valid, and 0 dropped;
  they drop a short falsifying input and apply the same filename provenance rule
  to direct and directory-discovered files,
  restamps a seated direct file despite spoofed metadata, counts and drops an unseated direct
  file, preserves embedded provenance for both input forms without a roll, drops a block
  aimed at its own seat, and returns `received 0` for an empty directory. A direct CLI case
  also holds the received-and-dropped result to the JSON process-boundary contract.
- `pick` reads `WINNER: Mark Twain`, rechecks the selected normal or `--draft` source through
  the final floor with the same roll and idea, copies a passing `<prompt>` block, and refuses
  failing and empty prompts without writing. It returns floor failures at exit 2 and
  invocation or I/O failures at exit 3, never alters an existing output, raises when the
  verdict names nobody, resolves an accented name written either way, and rejects a name
  nobody on the roll answers to.
- `init` lifts every flag out of the one argument, reads an idea from a file, refuses an empty
  idea, and refuses a secret without echoing it. Table-driven parser tests cover missing,
  empty, quoted-empty, whitespace-only, unknown, next-flag, and flag-leading inputs; valid
  values and idea punctuation, spaces, tabs, and newlines remain intact. Malformed init
  calls clear the stale pointer, create no run, and preserve earlier run files byte for byte.
- Run-pointer tests cover the formerly colliding `/tmp/a_b/c` and `/tmp/a/b_c` shapes,
  repeatability, physical/symlink equivalence, distinct newline and unusual-character paths,
  the filename-safe SHA-256 format, and the JSON `pointer` command. The skill preamble obtains
  that value from Python, and Phase 0 consumes the pointer returned by a successful `init`.
- Direct CLI tests cover every value-taking flag and each subcommand's missing operands,
  unknown options, invalid values, empty seat lists, and empty paths that could bypass a
  check or write a winner. They parse all stdout as one JSON object, require exit 3 and
  empty stderr, and retain successful help and valid negative seeds and flag-leading values.
- `SKILL.md` runs no command held in a variable and no conditional expansion that hides a word
  split, names only subcommands that exist, states the word caps in every template that writes
  a prompt, gates the revision round on the flag, and names one model across the frame and the
  templates. `README.md`'s roster equals `seats.tsv`, creed, catch and banned words included.

## Call topology

A standard run starts five draft calls. Each surviving named seat can add an objection
call, and the judge runs after the floor and objections. Floor drops and `--no-wild` reduce
later calls; a failed Codex attempt can invoke the Claude fallback; `--revise` can add one
revision. Wall-clock time depends on the environment, authentication, provider load, and
configured model effort.

## Later, if wanted

- A `--fast` mode: the plain seat and two others, drafted on a cheaper model, examined on opus.
- A stats line across runs: which seats win, which objections survive.
- Whether `--revise` should be the default, once it has been run enough times to tell.
- Have `floor` synthesize the lint-shaped roll file at call time so `roll.json` stays in the
  council's own words.
