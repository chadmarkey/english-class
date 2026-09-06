# English Class Prompt Council

English Class is a Claude Code skill that randomly selects three literary figures as lenses, then
brings in Werner Herzog as a wild card to argue about your prompt. The full roster has
22 seats: 15 regulars, six bench voices you can select manually, and Herzog. The random
draw uses the regulars. Each lens brings a distinct editorial voice and ethos, with its
own criteria for language, structure, and narrative. Their task: shape your prompt for
Claude Fable 5.1.

The three plus Herzog draft in parallel, alongside a plain baseline. The drafts enter
the council: those that fail a fixed lint floor are dropped, and the surviving named
lenses cross-examine one another's work. An installed, authenticated Codex CLI can bring
a GPT model in as judge. Otherwise Claude Opus takes the judge's chair; my recorded
fallback run used Opus 5. The judge weighs the surviving prompts against a fixed rubric
and picks a winner. The skill saves the bare prompt, ready to paste. No Cliff Notes needed.

This is a token- and resource-intensive prompt generator/optimizer. It is intended for
project kickoffs that deserve deliberate planning, or a system prompt worth thinking
through carefully. Parallel drafting, cross-examination, judging, and an optional
`--revise` round mean many model and tool calls, all drawing on your usage allowance.
If you have the tokens to spend and about ten minutes to spare, a one-off can be part of
the fun, too. The run recorded in the prompt example below took about 8 minutes of wall
time; runtime varies, and more deliberation does not guarantee a better prompt.

If you want it slimmer, `--fast` disconnects the council: two lenses plus Herzog draft in
one call, nobody cross-examines anyone, and a faster model judges. Same floor, same rubric,
two model calls instead of about eleven. It is not the default, and I prefer it that way.
Cross-examination is the part where the seats actually argue. Every objection has to name
the exact input where a rival's prompt would go wrong, and a script throws out any that
does not. It is also the part that makes this funny and a little absurd: four editorial
lenses filing sixteen formal objections at one another over a prompt for an audiobook
page. That is the point. The practical version is there for when you need a prompt in a
minute. The council is for when you want to watch the fight.

We're approaching a world where the right question matters more than the answer. English
class, surprisingly, is the best place to learn how to ask those questions.

It is meant to be fun and engaging. Use it as you wish—just keep an eye on the token budget.

## Privacy and data handling

Running the full skill is not local-only. The parser trims surrounding whitespace from the
inline idea or UTF-8 file contents, preserves the remaining characters, and saves that text
with a trailing newline under `~/.council/runs/<slug>-<timestamp>[-N]/`. Claude receives the
idea and frame to draft, and later Claude calls can receive generated drafts, objections, a
verdict, or revision material. If an installed and authenticated Codex CLI is available, the
surviving drafts and valid objections are included in its judge prompt. If Codex is absent,
exits nonzero, or produces no usable verdict, the same judge material goes to a Claude fallback.

Provider-side storage, telemetry, retention, and training follow the policies for your
accounts and services. Local run directories can contain `idea.md`, `roll.json`, drafts,
lint results, objections, the judge prompt and stderr, the verdict, an optional revision, and
`winner.md`. They remain until you delete them; the skill does not expire, prune, overwrite,
or automatically clean them. The adjacent `~/.council/current_run.<sha256>` file is a
per-working-directory bookmark that later runs replace, not the durable record.

Secret detection is heuristic and best effort. It can miss credentials, tokens, or other
sensitive material, so do not paste secrets. A recognized secret-like input is refused
before a new run is created or any model call begins, although `init` can clear an obsolete
run pointer while refusing the input.

To delete one finished run, first list the immediate run directories, then copy exactly one
directory name into `english_class_run_name`:

```bash
english_class_runs_dir="${HOME:?HOME is not set}/.council/runs"

find "$english_class_runs_dir" \
  -mindepth 1 \
  -maxdepth 1 \
  -type d \
  -print

english_class_run_name='copy-one-exact-directory-name-from-the-list'

case "$english_class_run_name" in
  ''|'.'|'..'|*/*)
    printf 'Refusing unsafe run name\n' >&2
    exit 1
    ;;
esac

english_class_run_path="$english_class_runs_dir/$english_class_run_name"

if [ ! -d "$english_class_run_path" ]; then
  printf 'Run not found: %s\n' "$english_class_run_path" >&2
  exit 1
fi

printf 'Reviewing only: %s\n' "$english_class_run_path"
find "$english_class_run_path" -maxdepth 2 -print
rm -ri -- "$english_class_run_path"
```

Do not substitute a wildcard, the current-run pointer, the `runs/` directory, or
`~/.council` itself. Do not delete an active run, and review each interactive prompt before
confirming. The project never runs this cleanup automatically.

## Install

```bash
git clone https://github.com/chadmarkey/english-class ~/.claude/skills/english-class
python3 -m unittest discover -s ~/.claude/skills/english-class/tests
```

Git is needed for the clone command. The local `council.py` helper needs Python 3.9 or newer,
uses only the standard library, and is self-contained. The full skill needs
an authenticated Claude Code installation with access to the Claude model and subagent
behavior named in `SKILL.md`. The Codex CLI is optional, but must be installed and
authenticated to act as judge; otherwise Claude judges and records the fallback.

The full contributor validation suite also needs Bash, Zsh, and Ruff.
The validation suite has been tested locally on macOS with Python 3.9, 3.12, and the current
default interpreter. The existing CI targets Ubuntu with Python 3.9 and 3.12 and installs Zsh.
Native Windows and other agent hosts have not been validated.

The skill is gated (`disable-model-invocation: true`), so Claude will not trigger it on its own. Type `/english-class` to run it.

## Run

```
/english-class build a weekly scout that reads RSS feeds and files a digest into my notes
/english-class --seed 4127 path/to/rough-prompt.md
/english-class --seats "Mark Twain,Franz Kafka,Oliver Sacks" --wild "Dorothy Parker" <idea>
/english-class --fast tighten the system prompt for the support bot
```

`--seed N` replays a roll. `--seats` names three regular or bench lenses for the regular chairs. `--wild` fills the wild chair instead of seating Herzog. `--no-wild` leaves it empty. `--fast` seats two lenses plus Herzog, skips cross-examination, and judges on a faster model; it takes two names in `--seats` and refuses `--revise`. A bare `--` ends the flags; everything after it is the idea, even when it starts with a known flag name. Every run is saved under `~/.council/runs/` with the drafts, the lint, the objections, the verdict, and the winner.

## Prompt example

One idea, three prompts. Prompt 1 is what the human typed. Prompts 2 and 3 are two tools' attempts to turn it into a prompt for Claude Fable 5.1; the grade at the end of this section refers to them by these numbers.

<details open>
<summary>Prompt 1 — the original request</summary>

````text
please make me a personal web hosted dashboard of all of these books that lets me listen to the book on tape

- Death of a Salesman — Arthur Miller
- The Things They Carried — Tim O'Brien
- When Breath Becomes Air — Paul Kalanithi
- The Count of Monte Cristo — Alexandre Dumas
- Frankenstein — Mary Shelley
- A Confederacy of Dunces — John Kennedy Toole
- Lonesome Dove — Larry McMurtry
- The Witcher: The Last Wish — Andrzej Sapkowski
- Blood Meridian — Cormac McCarthy
- The House of God — Samuel Shem
- Catch-22 — Joseph Heller
- Moby-Dick — Herman Melville
````

</details>

<details open>
<summary>Prompt 2 — the /english-class council winner, written for Claude Fable 5.1</summary>

Seed 219652. Seats: Mark Twain, Lewis Carroll, Cormac McCarthy, Werner Herzog (wild), plus the plain seat. All five drafts passed the floor. Sixteen objections filed, sixteen kept. Codex was not installed, so the Claude fallback judged and picked Cormac McCarthy on the line "Persisting a local file across a page reload is the hard part of this build. Solve it and tell me which mechanism you used." The judge asked the human to confirm three things before pasting: the audio files are already in hand, phone plus laptop with no sync is acceptable, and "dashboard" means a player rather than a player plus progress stats.

````text
<context>
I have twelve novels I want to listen to, and I want one page that holds all of them instead of twelve apps and a scattered set of files. The page is for me alone, hosted at a URL I use from a laptop and an iPhone. I supply every audio file myself, from purchases or library loans. The page ships with no audio in it and fetches audio from nowhere except a location I hand it. There is no second user, no login, and no server I control, so anything the page remembers it must remember in the browser.
</context>

<task>
Build one self-contained HTML file that plays my audiobooks and remembers where I stopped in each one.

The twelve books, in this order:

1. Death of a Salesman — Arthur Miller
2. The Things They Carried — Tim O'Brien
3. When Breath Becomes Air — Paul Kalanithi
4. The Count of Monte Cristo — Alexandre Dumas
5. Frankenstein — Mary Shelley
6. A Confederacy of Dunces — John Kennedy Toole
7. Lonesome Dove — Larry McMurtry
8. The Witcher: The Last Wish — Andrzej Sapkowski
9. Blood Meridian — Cormac McCarthy
10. The House of God — Samuel Shem
11. Catch-22 — Joseph Heller
12. Moby-Dick — Herman Melville

Each book is a card holding the title, the author, a control for attaching audio, a player, and the saved position. Attaching audio takes two forms: pick one or more files from the device, or paste a direct URL to an audio file I host. A book may arrive as a single file or as numbered parts, so a card holds an ordered list and tracks which part is playing and how far into it.

Persisting a local file across a page reload is the hard part of this build. Solve it and tell me which mechanism you used: the File object in IndexedDB, a File System Access handle, or a re-pick that seeks back to the saved offset. The saved position survives either way.

Done when all of the following hold: the file opens from a hosted URL with no build step; all twelve titles and authors appear as written above; I attach a local m4a or mp3 to any card and hear it; play, pause, scrub, back thirty seconds, forward thirty seconds, and speeds from 0.75x to 2x all work; I close the page, reopen it, and each attached book returns to within a second of where I stopped; a card with nothing attached shows the attach control rather than a broken player or an error; the console is clean on load and during playback.
</task>

<constraints>
Bundle no audio, no cover images, and no book text, and pull none of those from a third party at runtime. I own or have borrowed every file I will attach, and the page stays a player for files I already hold.

Make the file self-contained. No CDN scripts, no web fonts, no analytics, no outbound request the page issues on its own. The only network traffic is the audio at a URL I typed in.

Store state in the browser on the device I am using. Nothing syncs between my phone and my laptop, and I am not asking for that.

The page must work in Safari on iOS and in Chrome on a desktop. iOS restricts audio playback to a user gesture and reclaims memory from background tabs, so make the first play a tap and make resume survive a tab the system unloaded.

Give it keyboard control on the desktop: space toggles play, left and right arrow seek. Lay it out so it reads at 390 pixels wide and at full laptop width.

Let me clear a book's attached audio and its position without clearing the other eleven.
</constraints>

<working_style>
Settle the storage design before writing the player. Tell me the choice and the reason in one short message, then build.

Report a phase change or a blocker. Skip the running commentary.
</working_style>

<output>
Give me the HTML file and its path.

Then, in the reply and under two hundred words: the storage mechanism and where it fails, what happens on a browser that denies it, and any listed requirement you did not implement.
</output>

<verify>
Run the done-state list against the finished file, item by item, and load it in a browser to check the ones that need a real page. Name every item you could not verify and say what blocked it. An untested platform is a reported gap, not a passed check.
</verify>
````

</details>

<details open>
<summary>Prompt 3 — the /prompt-optimize template output, written for Claude Fable 5.1</summary>

````text
You are a senior full-stack engineer building a personal, self-hosted audiobook dashboard.

<context>
The user owns (or will legally acquire) audiobook files for 12 novels and wants a
single web page to browse and listen to them. The app must NOT bundle, generate,
scrape, or narrate any book content — it plays audio files the user supplies and
links out to licensed sources for titles they haven't acquired yet.
</context>

<library>
1. Death of a Salesman — Arthur Miller
2. The Things They Carried — Tim O'Brien
3. When Breath Becomes Air — Paul Kalanithi
4. The Count of Monte Cristo — Alexandre Dumas
5. Frankenstein — Mary Shelley
6. A Confederacy of Dunces — John Kennedy Toole
7. Lonesome Dove — Larry McMurtry
8. The Witcher: The Last Wish — Andrzej Sapkowski
9. Blood Meridian — Cormac McCarthy
10. The House of God — Samuel Shem
11. Catch-22 — Joseph Heller
12. Moby-Dick — Herman Melville
</library>

<task>
Build a single-user web app with:

1. LIBRARY VIEW — Grid of 12 book cards (title, author, cover placeholder,
   progress bar, "Owned / Not yet added" status).
2. PLAYER — HTML5 <audio> with play/pause, ±30s skip, speed (0.75x–2x),
   chapter list (if multi-file), sleep timer, remembered playback position.
3. IMPORT — User drops .mp3/.m4b/.m4a files into /audiobooks/<slug>/;
   app scans on startup and matches by folder name.
4. FALLBACK — For unowned titles, show buttons linking to Libby/OverDrive,
   Audible, LibriVox (note: LibriVox won't have these — all are in copyright),
   and the user's local library search.
5. PERSISTENCE — Save progress + settings in SQLite or localStorage.
6. HOSTING — Dockerfile + docker-compose.yml; runs on a home server or
   a $5 VPS behind basic auth.
</task>

<stack>
- Backend: Node.js + Express (or Python + FastAPI — pick one, justify briefly)
- Frontend: vanilla HTML/CSS/JS or a single-file Svelte/React build
- No external CDNs required at runtime; must work offline on LAN
</stack>

<thinking>
Before coding:
1. Confirm the audio-source model (user-supplied files only).
2. Design the folder → book matching scheme.
3. Plan the range-request handling so seeking works in large files.
4. Identify what persists where (server vs. browser).
</thinking>

<constraints>
- Do NOT include, summarize, or generate any passage of the books' text.
- Do NOT implement TTS narration of copyrighted text.
- Do NOT scrape audio from any site.
- Metadata (title/author/year) is fine; cover art must be user-supplied
  or fetched via a public API the user configures (e.g., Open Library).
- Mobile-responsive; works in Safari (iOS audio quirks: no autoplay,
  requires user gesture).
</constraints>

<output_format>
1. One-paragraph architecture summary
2. File tree
3. Complete code for each file (no placeholders like "// rest of code")
4. README: setup, adding books, running with Docker, adding a 13th book
5. Self-review checklist: seeking works, progress persists, iOS tested,
   no copyrighted content bundled
</output_format>

<error_handling>
- Folder found but no audio files → show "Add files" instruction on card
- Unsupported codec → surface browser error, suggest converting to .m4b
- If asked to "include the audiobook itself," respond: "I can't supply
  the audio; drop your purchased files into /audiobooks/<slug>/ and the
  app will pick them up."
</error_handling>
````

</details>

### A third opinion on the three prompts

After the run, a separate grader (Astra) scored the three prompts above against a 100-point rubric for coding tasks whose output is working software. It read the text only; it did not run any prompt through Claude Fable 5.1, so these are written assessments, not measured results. Prompt 1 is the original request, prompt 2 the council winner, prompt 3 the `/prompt-optimize` output.

| Criterion | Max | 1: original | 2: council | 3: `/prompt-optimize` |
|---|---|---|---|---|
| Outcome and user context | 15 | 11 | 15 | 14 |
| Actionable functional requirements | 15 | 5 | 14 | 14 |
| Technical feasibility and internal consistency | 20 | 10 | 16 | 15 |
| Scope control and useful autonomy | 10 | 6 | 9 | 8 |
| Verification and honest completion | 15 | 0 | 15 | 8 |
| Deliverable and handoff clarity | 10 | 3 | 9 | 9 |
| Usability and interaction design | 10 | 2 | 7 | 6 |
| Communication and signal-to-noise | 5 | 5 | 5 | 4 |
| **Total** | **100** | **42** | **90** | **78** |

The grader's one-line reasons. Prompt 1 supplies an idea, not a delivery contract: it never says where the audio comes from or what "web hosted" means as a deliverable. Prompt 2 states a result and a way to prove it, and its verify line "An untested platform is a reported gap, not a passed check" was called the best single instruction of the three; it lost points for promising a one-second resume that browser storage cannot guarantee, for letting "purchased or borrowed" stand in for DRM-free files, and for saying nothing about visual design. Prompt 3 is a solid self-hosted brief but leaves cross-device persistence to the model, asks for a self-review checklist instead of evidence, and requires a LibriVox link it admits will have none of these titles.

Two of those knocks on prompt 2 were filed during the run. Mark Twain's objection said "Solve it" promised more than the browser would keep; the judge ruled the line absorbed the objection, and the grader disagreed. The grader also noted that prompts 2 and 3 each chose a product the original never asked for: a browser-only player with no sync, or a Docker-hosted server. A precise spec for the wrong product is not a better prompt, so the council's closing "confirm before building" list is the part to read first.

## The council

Each named seat carries three things. A **creed**, used as a functional editorial lens rather than an invitation to imitate anyone. What they **catch**, the prompt failure that lens targets. And the words the floor **bans** from the shipped prompt, so the named person's works and world stay out. The council's job is to improve your prompt; notes and objections explain editorial judgments directly.

Each seat also carries a **line**, the passage behind the association. The creed is the project-authored instruction; the line is the literary spark. Source labels identify fictional speakers, translations, and the Christie paraphrase. The project does not claim participation, affiliation, or endorsement by any named person, estate, publisher, or representative.

Three named editorial lenses are rolled per run from the 15 regulars. The six bench lenses are never rolled. Werner Herzog is seated every run unless the wild chair is changed or removed.

### Cormac McCarthy

- **Creed.** Test every sentence for structural weight. Remove decoration, hedges, and punctuation that substitutes for a clear relationship between ideas.
- **Catches.** Language that adds surface without carrying meaning.
- **Bans.** blood meridian, suttree, no country for old men, judge holden, anton chigurh
- **Line.** “I believe in periods, in capitals, in the occasional comma, and that’s it.” “if you write properly you shouldn’t have to punctuate” ([Interview with Oprah Winfrey (2007)](https://www.oprah.com/oprahsbookclub/cormac-mccarthy-on-james-joyce-and-punctuation-video)).

### David Foster Wallace

- **Creed.** Preserve necessary complexity without letting it become clutter. Add the caveat that would materially change the reader’s decision, and cut the rest.
- **Catches.** The omitted qualification that makes a simple answer misleading.
- **Bans.** infinite jest, hideous men, the pale king, enfield, eschaton
- **Line.** “Well, it’s too simple to just wring your hands and claim TV’s ruined readers.” ([“A Conversation with David Foster Wallace”](https://www.dalkeyarchive.com/2013/08/02/a-conversation-with-david-foster-wallace-by-larry-mccaffery/)).

### Junot Díaz

- **Creed.** Use a natural spoken register suited to the actual reader. Keep the language direct, specific, and consistent instead of drifting into institutional prose.
- **Catches.** Stiff phrasing, unexplained register changes, and sentences nobody would say aloud.
- **Bans.** oscar wao, yunior, fukú, brief wondrous life, paterson
- **Line.** “A lot of times we write but forget that there has to be space in the work for a reader.” ([Live chat with Junot Díaz](https://billmoyers.com/2012/12/18/live-chat-with-junot-diaz/)).

### Atul Gawande

- **Creed.** Turn complex work into an ordered set of checks. Make every step before an irreversible action visible and verifiable.
- **Catches.** A skipped prerequisite or missing check at the point of no return.
- **Bans.** checklist manifesto, being mortal, brigham, surgeon's notes, scalpel
- **Line.** “Under conditions of complexity, not only are checklists a help, they are required for success.” ([*The Checklist Manifesto*, chapter 4, p. 79](https://us.macmillan.com/books/9780312430009/thechecklistmanifesto/)).

### Oliver Sacks

- **Creed.** Ground the instruction in one concrete case that a reader can follow from input to result. Let the example test the abstraction.
- **Catches.** A general rule with no worked instance or observable case.
- **Bans.** awakenings, mistook his wife, musicophilia, uncle tungsten, tourette
- **Line.** “Back to individuals and their stories again” ([*An Anthropologist on Mars*](https://www.oliversacks.com/oliver-sacks-books/an-anthropologist-on-mars/)).

### Robert Sapolsky

- **Creed.** Separate causes by level and timescale. State whether a claim concerns the immediate trigger, surrounding conditions, or longer history.
- **Catches.** A single-cause explanation that mixes levels or ignores timing.
- **Bans.** baboon, zebras don't get ulcers, masai mara, serengeti, glucocorticoid
- **Line.** “you need to understand everything from one second before to millions of years before” ([TED2017 talk report](https://blog.ted.com/the-biology-of-behavior-robert-sapolsky-speaks-at-ted2017/)).

### Ernest Hemingway

- **Creed.** Keep only what carries the task, constraint, or consequence. Let precise structure do more work than explanation.
- **Catches.** Words or clauses that are not load-bearing.
- **Bans.** bullfight, marlin, pamplona, santiago, old man and the sea
- **Line.** “I was always embarrassed by the words sacred, glorious, and sacrifice and the expression in vain… There were many words that you could not stand to hear and finally only the names of places had dignity… Abstract words such as glory, honor, courage, or hallow were obscene beside the concrete names of villages, the numbers of roads, the names of rivers, the numbers of regiments and the dates.” ([*A Farewell to Arms* (1929), chapter XXVII (Frederic Henry; abridged)](https://www.gutenberg.org/cache/epub/75201/pg75201-images.html)).

### Mark Twain

- **Creed.** Choose the exact ordinary word and remove inflated substitutes. Prefer precision over decoration.
- **Catches.** Padding, pomposity, and almost-right diction.
- **Bans.** mississippi, huckleberry, tom sawyer, steamboat, hannibal
- **Line.** “Use the right word, not its second cousin.” ([“Fenimore Cooper’s Literary Offences” (1895), rule 13](https://www.gutenberg.org/files/3172/3172-h/3172-h.htm)). “Words are only painted fire; a look is the fire itself.” ([*A Connecticut Yankee in King Arthur’s Court* (1889), chapter XXXV (Hank Morgan)](https://www.gutenberg.org/files/86/86-h/86-h.htm#c35)).

### George Orwell

- **Creed.** Use plain, active language that identifies the actor and the action. Replace jargon and hedges with accountable statements.
- **Catches.** Passive or abstract phrasing that hides who must do what.
- **Bans.** big brother, doublethink, winston smith, animal farm, newspeak
- **Line.** “Never use the passive where you can use the active.” ([“Politics and the English Language”](https://www.orwellfoundation.com/the-orwell-foundation/orwell/essays-and-other-works/politics-and-the-english-language/)).

### Anton Chekhov

- **Creed.** Make every setup serve a later instruction, decision, or test. Remove promises and context that never affect the outcome.
- **Catches.** A setup with no payoff or an instruction with no downstream effect.
- **Bans.** samovar, cherry orchard, the seagull, three sisters, uncle vanya
- **Line.** “One must not put a loaded rifle on the stage if no one is thinking of firing it.” ([Letter to Aleksandr Semenovich Lazarev (A. S. Gruzinsky), November 1, 1889](https://berlin.wolf.ox.ac.uk/lists/quotations/quotations_by_ib.html), translated from Russian).

### Lewis Carroll

- **Creed.** Define important terms once and use them consistently. Make exceptions explicit before they can change the rule.
- **Catches.** An undefined term, a word used in two senses, or a hidden exception.
- **Bans.** wonderland, humpty dumpty, jabberwock, cheshire, looking-glass
- **Line.** “What I tell you three times is true.” ([*The Hunting of the Snark*, Fit the First (the Bellman)](https://www.gutenberg.org/files/13/old/13-h/13-h.htm)). “‘When I use a word,’ … ‘it means just what I choose it to mean—neither more nor less.’” ([*Through the Looking-Glass* (Humpty Dumpty)](https://www.gutenberg.org/files/12/12-h/12-h.htm#link2HCH0006)).

### G.K. Chesterton

- **Creed.** Before removing or replacing something, establish the purpose it serves. Preserve that purpose unless the task explicitly changes it.
- **Catches.** A refactor or deletion requested without understanding the existing rationale.
- **Bans.** father brown, flambeau, chesterton's fence, the man who was thursday
- **Line.** “If you don’t see the use of it, I certainly won’t let you clear it away.” ([*The Thing*, “The Drift from Domesticity”](https://archive.org/details/in.ernet.dli.2015.475818/page/n35/mode/2up)).

### Franz Kafka

- **Creed.** Ensure every constraint is discoverable and satisfiable before asking the reader to comply. Eliminate circular or trap-like requirements.
- **Catches.** A rule that can be learned only by violating it, or a requirement that cannot be met.
- **Bans.** gregor samsa, josef k, penal colony, hunger artist, odradek
- **Line.** “A cage went in search of a bird.” ([Zürau Aphorism 16, Morgan Library exhibition](https://www.themorgan.org/sites/default/files/pdf/exhibitions/FranzKafkaLargePrintLabels.pdf), translated from German).

### Edgar Allan Poe

- **Creed.** Choose one intended effect and a concrete done-state, then make each instruction support them.
- **Catches.** A prompt with competing effects or no visible completion condition.
- **Bans.** the raven, nevermore, tell-tale heart, house of usher, amontillado
- **Line.** “Nothing is more clear than that every plot, worth the name, must be elaborated to its dénouement before any thing be attempted with the pen. It is only with the dénouement constantly in view that we can give a plot its indispensable air of consequence, or causation, by making the incidents, and especially the tone at all points, tend to the development of the intention.” ([“The Philosophy of Composition” (1846)](https://eapoe.org/WORKS/essays/philcomp.htm)).

### Rudyard Kipling

- **Creed.** Check that the reader can identify who acts, what changes, why it matters, when and where it applies, and how success is shown.
- **Catches.** The missing member of who, what, why, when, where, and how.
- **Bans.** mowgli, jungle book, gunga din, shere khan, baloo
- **Line.** “I keep six honest serving-men:<br>(They taught me all I knew)<br>Their names are What and Where and When<br>And How and Why and Who.” ([Verse following “The Elephant’s Child,” *Just So Stories* (1902)](https://www.gutenberg.org/files/2781/2781-h/2781-h.htm)).

### Werner Herzog, the wild card

- **Creed.** Make the stakes and consequences tangible. A technically correct prompt should still reveal why the outcome matters.
- **Catches.** A correct but inert instruction with no meaningful consequence.
- **Bans.** kinski, fitzcarraldo, grizzly man, aguirre, ecstatic truth, bavarian
- **Line.** “I believe the common denominator of the universe is not harmony, but chaos, hostility, and murder.” ([*Grizzly Man* (2005; narration), discussed in an interview with Herzog](https://www.theguardian.com/film/2022/aug/07/werner-herzog-twilight-world-fire-within-stunts-interview)).

### The bench

The six sit in `seats.tsv` as `bench`: they are never rolled by default, but any of them can be seated with `--wild` or `--seats`. They carry the same creed, catch, and line as the rolled seats; the floor bans no words for them.

| Seat | Creed | Catches | Line |
|---|---|---|---|
| Jane Austen | Challenge universal claims by naming whose perspective they reflect, what evidence supports them, and where they stop applying. | A local assumption presented as common or universal truth. | “It is a truth universally acknowledged, that a single man in possession of a good fortune, must be in want of a wife.” ([*Pride and Prejudice* (narrator)](https://gutenberg.org/cache/epub/42671/pg42671-images.html)). |
| Sun Tzu | Inspect the actual environment before committing to a plan. Make repository state, tools, constraints, and dependencies explicit. | A plan that assumes its terrain instead of checking it. | “If you know the enemy and know yourself, you need not fear the result of a hundred battles.” ([*The Art of War*, chapter III, §18](https://www.gutenberg.org/files/132/132-h/132-h.htm), translated by Lionel Giles). |
| Agatha Christie | Provide every fact needed for the requested conclusion before asking for a verdict. Let organization create clarity, not withheld evidence. | A conclusion that depends on a clue the prompt never supplies. | If a fact will not fit into your theory, it is no good putting it aside. It is the theory that is wrong, not the fact. (Paraphrase of Poirot’s principle in [*The Mysterious Affair at Styles* (1920), chapter V](https://www.gutenberg.org/files/863/863-h/863-h.htm#chap05)). |
| Voltaire | Ask for the smallest result that is complete, useful, and verifiable. Do not make optional polish a condition of finishing. | Perfectionism that expands scope beyond a usable result. | “That is well said, but we must cultivate our garden.” (“Cela est bien dit, mais il faut cultiver notre jardin.”) ([*Candide* (1759), chapter XXX (Candide)](https://www.gutenberg.org/cache/epub/4650/pg4650-images.html)). “The better is the enemy of the good.” (“Le mieux est l'ennemi du bien.”) ([*La Bégueule* (1772)](https://fr.wikisource.org/wiki/Contes_en_vers_%28Voltaire%29/La_B%C3%A9gueule); English translations of the French). |
| Oscar Wilde | Make clarity engaging without turning seriousness into ceremony. State the strongest relevant objection and require the final answer to survive it. | Dull consensus or a polished claim that avoids the best dissent. | “The truth is rarely pure and never simple.” ([*The Importance of Being Earnest* (Algernon Moncrieff)](https://www.gutenberg.org/cache/epub/844/pg844-images.html)). |
| Arthur Conan Doyle | Separate direct observations from inferences. Require each conclusion to identify the evidence and reasoning that support it. | An inference reported as fact or a deduction without evidence. | “It is a capital mistake to theorise before one has data. Insensibly one begins to twist facts to suit theories, instead of theories to suit facts.” ([“A Scandal in Bohemia” (1891; Sherlock Holmes)](https://www.gutenberg.org/files/1661/1661-h/1661-h.htm)). “You see, but you do not observe. The distinction is clear.” ([“A Scandal in Bohemia” (1891; Sherlock Holmes)](https://www.gutenberg.org/files/1661/1661-h/1661-h.htm)). |

## Files

| File | Job |
|---|---|
| `SKILL.md` | The run, phase by phase, with the five subagent templates |
| `frame-fable-5.1.md` | The shape every draft takes, built from the Claude Fable 5.1 prompting docs |
| `seats.tsv` | The roster: name, kind, creed, catch, residue |
| `council.py` | `init`, `roll`, `floor`, `objections`, `pick`. Exit 0 pass, 2 fail, 3 could not run |
| `SPEC.md` | The design |
| `tests/` | Roster shape, roll determinism, the floor and its rules, the objections, the pick, the shell the run executes |

## License

MIT.
