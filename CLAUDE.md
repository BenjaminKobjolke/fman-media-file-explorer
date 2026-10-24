# Version
2

# Coding Rules (Pointer)

This project's rules live in two files in the project root:

- `CODING_RULES.md` — code quality and conventions. BINDING for all code work in
  this repository, always.
- `IMPLEMENTATION_FLOW.md` — the end-to-end flow to follow when planning and
  implementing a change (checks, gates, Definition of Done).

MANDATORY: Before writing or editing ANY code, you MUST Read BOTH files in full
**in the current session**. Do not rely on memory of a previous session, a
summary, or partial reads.

If you are about to make a code change and have not read both files in this
session: STOP, read them, then continue.

An external tool may orchestrate the implementation itself. When a skill or run
states that the implementation is orchestrated, ignore `IMPLEMENTATION_FLOW.md`
entirely — the orchestrator runs those steps as its own phases. `CODING_RULES.md`
stays binding either way.

Do not inline rules back into this file and do not use `@import` for either file —
they are intentionally referenced, not imported.


# graphify

This project's code directory is `media_file_explorer/`.

## Code Analysis

Run the changed-files analyzer after implementing a feature or fixing a bug:

```powershell
powershell -Command "cd 'C:\Users\XIDA\AppData\Roaming\fman\Plugins\User\fman-media-file-explorer'; cmd /c '.\tools\analyze_changed_and_new_files.bat'"
```

The changed-files run reports findings only for new or modified files, including untracked files.
Use the full project scan for an explicit audit or when the working tree is clean:

```powershell
powershell -Command "cd 'C:\Users\XIDA\AppData\Roaming\fman\Plugins\User\fman-media-file-explorer'; cmd /c '.\tools\analyze_code.bat'"
```

Both scripts write per-rule reports under `code_analysis_results/` and return a non-zero exit code
when findings are reported. Copy `tools/analyze_code_config.example.bat` to
`tools/analyze_code_config.bat` and set the local analyzer path if needed.
