# Let task routes own retrieval views and prompt contracts

The Evidence Retrieval Gateway will classify stable user task families, select the corresponding observation view, and compile a task-specific prompt and output contract from one Evidence Bundle. This replaces the current combination of keyword intent rules, one general system prompt, and caller-specific context assembly; exact item navigation remains deterministic and bypasses the LLM, while trend, evidence, relationship, and verification tasks receive distinct evidence and answer constraints.

## Consequences

- Ordinary queries collapse repeated observations by internal content identity; timeline queries expand them; exact Daily Item ID queries return only the requested observation.
- Prompt modules are organized by task family rather than company, product, or keyword.
- Confirmed graph relationships and Inferred Relationships remain distinguishable in both prompts and answers.
- Routes fail explicitly when their required evidence shape is unavailable instead of silently falling back to an unrelated answer mode.
