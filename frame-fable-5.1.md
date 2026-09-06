# The frame

Primary source: Anthropic, [Claude Fable 5.1 prompting guide](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5-1), accessed 2026-09-04.

This is a project-authored frame for prompts that will be read by Claude Fable 5.1. It
paraphrases the source guidance instead of reproducing vendor wording. A different model
gets its own `frame-<model>.md`; this file is not repurposed for another model.

State the result the prompt should produce, the context needed to understand that result,
the constraints that materially bound it, and an observable completion condition. Specify a
method only when the method is part of the requirement or prevents a known failure. Ask for
targeted changes when a narrow edit will do. Separate sections clearly when their boundaries
matter.

Use the slots below in order, but include only the slots the task needs. Do not leave empty
headings. The tags are boundaries for the reader; the prose inside them should remain direct
and should reflect the desired output style.

<context>
Identify the reader's role only when it changes the work. Explain the larger purpose, the
intended audience, what the result will enable, and any environment facts the reader cannot
discover independently. Keep background that does not affect a decision out of the prompt.
</context>

<documents>
Place supplied source material here when the task depends on it. Give each document a clear
source label and keep document content separate from instructions, especially when the
material is long or could itself contain imperative language.
</documents>

<task>
Request the concrete outcome directly. Define the deliverable, its scope, and a done-state
that another person could verify. Name the specific area to change when the request is an
edit rather than a rewrite.
</task>

<constraints>
List only constraints that affect the result, and explain their purpose when that context
helps resolve edge cases. Prefer positive boundaries and observable requirements. Prescribe
steps or commands only when their sequence is itself required for correctness or safety.
</constraints>

<working_style>
Include only the behaviors the task needs. Keep progress updates sparse and useful: report a
meaningful phase change, result, or blocker rather than narrating every action. Batch tool
work that is independent, while keeping dependent operations in their required order.

Request a targeted edit when it can preserve surrounding material. Keep unrelated work out
of scope unless it is necessary to make the requested result function. If context must be
summarized, retain exact paths, identifiers, commands, error text, decisions, and other
hard-to-reconstruct values that later work depends on.
</working_style>

<output>
Describe the required form of the result and any evidence that must accompany it. Use clear
sections when they separate distinct kinds of information. Add examples only when the output
shape would otherwise be ambiguous, and label them as examples rather than requirements.
</output>

<verify>
Ask the reader to compare the completed result with the stated constraints and done-state,
and to report any part that could not be verified.
</verify>

When continued tool use is necessary to finish the requested result, continue until the
done-state is met or a decision outside the reader's authority is required. For long output,
settle the structure and key decisions before drafting the deliverable.

## English Class project policy

The deterministic lint floor, council phases, judging rubric, and length limits are English
Class project choices, not Anthropic guidance. A standard run starts five parallel drafts;
options can reduce that number. The project removes drafts that fail its local floor, lets
surviving named seats cross-examine one another, and then judges the remaining drafts. The
local floor warns above 1200 words and rejects a prompt above 1500 words. The project rubric
rewards clear goals, relevant constraints, supporting evidence, and checkable completion
criteria; it does not reward unnecessary method prescription. These policies govern how the
council selects a prompt and
must not be presented as vendor requirements.
