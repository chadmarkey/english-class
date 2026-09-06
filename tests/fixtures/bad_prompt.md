<prompt>
You are a coding agent assigned to repair a failing parser.
Inspect the failing test and the nearby implementation.
Show your reasoning before editing.
If in doubt, choose the smallest local change.
Hold all findings until the patch is ready.
Use a robust check for the repaired branch.
Never skip the regression test.
Do not alter unrelated files.
Avoid changing public interfaces.
No speculative refactors are allowed.
Run the focused test after the edit.
Report the changed path and test result.
Assistant: I will begin with the failing test.
<example>Empty input yields an empty record</example>
<example>A missing key yields a clear error</example>
<example>Valid input preserves order</example>
<example>A duplicate key selects the later value</example>
<example>A bad token returns an error</example>
<example>Outer whitespace is accepted</example>
</prompt>
<note>Deliberate multi-rule fixture.</note>
