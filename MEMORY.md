# Memory index

Cross-session facts only. Prune every session, or it becomes rot.

Project-specific memories live under `.claude/projects/-Users-yyy-Documents-protein-design-REvoDesign/memory/`.

- preferences: Ponytail mode active (lazy/senior dev persona). Conventional commits. Detailed comments match surrounding code.
- decisions:
  - **QThread vs threading.Thread** — long-lived event-loop servers (uvicorn, asyncio) MUST use `threading.Thread`, never `QThread`. See [[sip-qt-threading-heisenbug]].
  - **Qt imports** — all go through `REvoDesign.Qt`, never direct PyQt5/PyQt6. Enforced by pre-commit hook.
  - **UI loading** — runtime via `RuntimeUiProxy`, not generated `Ui_REvoDesign.py`. Enforced by `reject-generated-main-ui` hook.
- recent feedback: <corrections you keep re-applying>
