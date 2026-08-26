# CLAUDE.md Audit Against "Your AGENTS.md is a Neural Net" (REVISED)

**Date:** 2026-08-26  
**Reference:** [Your AGENTS.md is a Neural Net](https://blog.kunchenguid.com/p/your-agentsmd-is-a-neural-net) by Kun Chen  
**Full article:** `tmp/your-agents-md-is-a-neural-net.md`

## Executive Summary

Our CLAUDE.md is **functional but missing the automation and skills architecture** the article prescribes. We've done manual gradient descent (pruned from 500→239 lines) but lack:
1. Transcript-based training automation (backpass tool)
2. Skills as the release valve for narrow instructions
3. Weekly training cadence with evidence gates

**Health score: 6/10** — Right direction, wrong tooling. We need skills extraction + automated training, not just manual pruning.

## The Four Bad States

| State | Our Status | Evidence |
|-------|------------|----------|
| **Empty** | ✅ Not empty | 500+ lines of real patterns |
| **Bloated** | ⚠️ Early symptoms | Growing without pruning; no automated training |
| **Stale** | ⚠️ Some staleness | Threading section references resolved bugs |
| **Drifted** | ✅ No drift | Single source (no AGENTS.md vs CLAUDE.md conflict) |

## Key Principle: The Neural Net Model

**What the article prescribes:**
- Project CLAUDE.md = neural net weights
- Token budget = model size (article recommends 5000 tokens, we set 3000)
- Agent session = forward pass (file loads, agent works, file unchanged)
- Gap between agent behavior and desired = loss
- Reading transcripts + updating file = backward pass (gradient descent)

**The mapping:**
- **Weights:** Text in CLAUDE.md
- **Forward pass:** Every agent session loads the file
- **Loss:** Agent rediscovered schema, ran wrong command, violated a rule, followed a wrong rule
- **Backward pass:** Read transcripts, identify which instructions caused loss, update weights within budget
- **Training data:** Real session transcripts, not anecdotes

## What We Got Right vs What We Missed

### ✅ What we got right:
- Pruned low-value content (threading post-mortem, verbose procedures)
- Set token budget (3000 tokens / 400 lines)
- Extracted procedural docs (PR_WORKFLOW.md, RELEASE.md)
- Recognized the bloat symptoms early

### ❌ What we critically missed:

1. **Skills as the release valve**
   - Article: Narrow instructions with detectable trigger → extract to skill
   - Article: Broad instructions (20%+ sessions or safety-critical) → stay in CLAUDE.md
   - Us: We extracted to docs/, which are human-readable but NOT agent-invocable
   - **Impact:** We reduced CLAUDE.md size but lost the lazy-loading architecture

2. **Transcript-based training automation**
   - Article: Evidence must come from session transcripts, not anecdotes
   - Article: Automated tool (backpass) does gradient descent weekly
   - Us: Manual pruning based on "what feels low-value"
   - **Impact:** No systematic, reproducible training process

3. **Training cadence**
   - Article: Weekly runs on active repos
   - Us: "Every 3 months" audit for staleness
   - **Impact:** Will miss patterns that emerge quickly

4. **Scientific rigor gates**
   - Article: New rules need 2+ independent sessions (batch requirement)
   - Article: Verbatim quotes from transcripts required
   - Article: Max 5 edits per pass (learning rate)
   - Us: No enforcement mechanism
   - **Impact:** Could still add reactive rules from single incidents

**Threading section (lines ~250-280):**
```markdown
### Threading: QThread vs `threading.Thread`

**Rule: Long-lived event-loop servers (uvicorn, asyncio) MUST use `threading.Thread`, never `QThread`.**

`WorkerThread` (`src/REvoDesign/tools/package_manager.py`) is a `QThread` subclass. QThread creates a SIP-managed C++ QObject whose Python wrapper can outlive the C++ object during GC. When cross-thread Qt signals touch the stale wrapper, `sipWrapper_dealloc` → `forgetObject` → `QMessageLogger::fatal` → SIGABRT. This is a Heisenbug: heap-layout-sensitive corruption that moves every time code changes.
```

**Problem:** This reads like a post-mortem. The bug is fixed. The pattern is "use threading.Thread for servers, QThread for Qt signals." The rest is archaeological detail that costs tokens every session.

**Lazy fix:** 
```markdown
### Threading

- Long-lived servers (uvicorn, asyncio): `threading.Thread`
- Qt-signal-coupled work: `QThread` via `WorkerThread`
- When joining from main thread: `QApplication.processEvents()` to keep UI responsive
```

**Token savings:** ~150 tokens → ~40 tokens

### 2. Repeated patterns

**CI re-run advice appears in multiple sections:**
- "Workflow" section: "CI suddenly failing on unchanged code? Re-run the last passing CI commit..."
- "PR babysitting" section: Similar advice embedded

**Lazy fix:** One canonical location, reference it elsewhere or drop the repetition.

## The Critical Insight We Missed: Skills vs Docs

**Article's three-tier architecture:**
```
CLAUDE.md (always loaded, budget: 5000 tokens in article, 3000 in ours)
├── Broad instructions (20%+ of sessions or safety-critical)
├── Pointers to skills
└── Budget enforcement

Skills (lazy loaded on detectable trigger, agent-invocable)
├── Narrow instructions with trigger
└── Invoked via Skill tool when keywords match

docs/ (human reference only, never loaded into agent context)
└── Not agent-invocable
```

**Our current architecture:**
```
CLAUDE.md (pruned to 239 lines)
├── Core patterns
└── Pointers to docs/

docs/ (human-readable, NOT agent-invocable)
├── PR_WORKFLOW.md
└── RELEASE.md

Skills (not leveraged)
└── We have Skill tool but didn't extract content to skills
```

**The problem:** We extracted to `docs/`, which are NOT agent-invocable. The article prescribes a **release valve pattern**:
- **Broad** (20%+ sessions or safety-critical) → stay in CLAUDE.md (always loaded)
- **Narrow with detectable trigger** → extract to skill (lazy loaded when invoked)
- **Narrow without trigger** → delete (not worth the tokens)

Our "PR babysitting" and "version bumping" procedures should be **skills** that agents invoke with the `Skill` tool when triggered by keywords like "create PR", "open PR", "release", "version bump". Instead, we put them in docs/ where they're only human-readable.

### What Skills Enable

**Skills = pluggable, lazy loaded architecture the user requested:**
- Not loaded unless invoked
- Detectable trigger (keywords in user request)
- Agent-invocable via Skill tool
- Can be as detailed as needed (no token budget, only loaded when used)

**Docs = human reference:**
- Never loaded into agent context
- No trigger detection
- Not agent-invocable
- Good for: architecture explanations, onboarding guides, manual procedures

**From "Standalone bootstrapper encoding":**
```markdown
Keep `src/REvoDesign/tools/package_manager.py` ASCII-only because it is published as `REvoDesign_PyMOL.py` and may be saved through locale-aware Windows tools. A UTF-8-to-GBK transcode turns characters such as `→` into bytes beginning with `0xA1`, which Python 3 rejects while parsing the file as UTF-8.
```

**Assessment:** Useful for the specific file, but the "why UTF-8→GBK fails" detail is low-value. The actionable rule is "keep that file ASCII-only."

**Lazy fix:**
```markdown
- `package_manager.py`: ASCII-only (published as standalone, GBK-hostile environments exist)
```

### 4. Missing: What NOT to do

The article emphasizes that good AGENTS.md files also say "don't do X." We have some ("never vendor JS/CSS") but could be more explicit about anti-patterns:

**Examples we could add:**
- ❌ Don't add configuration "for later" — YAGNI
- ❌ Don't preserve backward compat — delete obsolete paths
- ❌ Don't reimplement what dependencies provide — check their docs first
- ✅ But wait, we already have these in "Engineering Principles"!

So the content IS there, just not framed as "never do this" — acceptable.

### 5. Stale content candidates

**Need verification:**
- Docker image tag strategy (`:next`, `:previous` → now banned, but is this still getting violated?)
- Deployment steps — does the absolute path still match production?
- Test commands — do all the `make` targets still exist?

**Action:** Cross-check against current codebase and recent PRs.

### 6. Procedural knowledge vs. guardrails

**Good example of guardrails (keep these):**
- "Never vendor third-party JS/CSS"
- "Pin Python packages only after checking real distribution channels"
- "Threading: use threading.Thread for servers, QThread for Qt signals"

**Example of procedural knowledge (could move to docs/):**
- Full PR babysitting workflow with 5 numbered steps
- Complete deployment control guide reference
- Full version-bumping procedure

**The test:** If it's "how to do a rare task step by step," it belongs in docs/. If it's "watch out for this gotcha," it belongs in CLAUDE.md.

## The Backpass Tool: Automated Gradient Descent

**What the article prescribes:**

Kun Chen built `npx -y backpass` ([github.com/kunchenguid/backpass](https://github.com/kunchenguid/backpass)) to automate the backward pass:

1. **Collect samples** from local transcript stores (Claude Code, Cursor, etc.) tied to repo by cwd/git
2. **Distill transcripts** to loss signals (96-99% reduction): what was asked, what agent said, one-line tool-call shape
3. **Calculate loss** via cheap model call per transcript: evidence against each addressable unit
4. **Aggregate gradients** deterministically: per-unit positive/negative counts, relevance share, near-duplicate gaps clustered
5. **Gradient descent step** (one high-reasoning call): propose edits with gates
   - Max 5 edits per run (learning rate)
   - New rule needs 2+ sessions (batch requirement)
   - Verbatim quote on every edit
   - Post-edit file must fit budget
   - One re-prompt on violation; second violation fails loudly
6. **Human review** via `backpass apply` (lavish-axi UI): accept/reject each edit; rejections remembered

**Training knobs:**
- `--budget`: model size (tokens)
- `--max-edits`: learning rate (edits per pass)
- `--min-gap-evidence`: batch size (sessions needed)
- `--since`: training window

**Rhythm:** Weekly runs per active repo, not quarterly audits

**What we're missing:** All of it. We did manual gradient descent once (this PR) but have no automation or enforcement.

### Immediate actions

1. **Set a size budget:** 400 lines max (~3000 tokens) for CLAUDE.md
   - Current: ~500 lines
   - Target: 400 lines
   - Savings needed: ~100 lines (20%)

2. **Prune lowest-value content:**
   - Threading: Keep pattern, drop post-mortem (save ~15 lines)
   - Bootstrap encoding: Keep rule, drop UTF-8→GBK explanation (save ~8 lines)
   - PR babysitting: Move detailed steps to `docs/PR_WORKFLOW.md`, keep 3-line summary (save ~30 lines)
   - Deployment control: Keep the file reference, drop the step-by-step (save ~25 lines)
   - CI re-run: Single canonical location (save ~10 lines)
   - Version bumping: Move to docs/, keep 1-line pointer (save ~15 lines)
   - **Total: ~103 lines → under budget**

3. **Add a "Last pruned" header:**
   ```markdown
   # CLAUDE.md
   
   **Last pruned:** 2026-08-26 (token budget: 3000)
   ```

4. **Create extraction targets:**
   - `docs/PR_WORKFLOW.md` — full PR babysitting checklist
   - `docs/DEPLOYMENT.md` — deployment procedure (or keep reference to `server/DEPLOYMENT_CONTROL_GUIDE.md`)
   - `docs/RELEASE.md` — version bumping, changelog, tagging

### Ongoing maintenance strategy

**Adopt the article's gradient descent loop:**

1. After each substantial session, ask: "What should have been in CLAUDE.md?"
2. Add the lesson as a concise bullet
3. If over budget (400 lines):
   - Rank all content by value (frequency × impact)
   - Remove lowest-value content until under budget
   - Move procedural "how-to" content to docs/
4. Every 3 months: Audit for staleness, prune resolved bugs and outdated patterns

**Use memory/ for:**
- Session-specific context
- Ephemeral goals ("adapt AlphaFold2" — done, now in memory)
- User preferences
- Temporary project state

**Use CLAUDE.md for:**
- Project-invariant patterns that come up repeatedly
- Gotchas that prevent repeated mistakes
- Architecture decisions that affect how to work with the codebase
- Current engineering principles

## What We're Doing Right

1. ✅ **Engineering Principles section** — concise, actionable, matches the "don't do X" pattern
2. ✅ **Memory system** — separates ephemeral context from project knowledge
3. ✅ **Concrete examples** — "RFdiffusion interface reference", "workspace UX principles"
4. ✅ **Workflow patterns** — PR babysitting, deployment control (though could be slimmed)
5. ✅ **Real patterns from real sessions** — not speculative rules

## Proposed Changes for This PR

**Option A: Conservative (recommended)**
- Add "Last pruned" header with token budget
- Prune ~100 lines of lowest-value content (threading post-mortem, detailed procedures)
- Move PR workflow and version bumping to docs/
- Add maintenance strategy section

**Option B: Aggressive**
- All of Option A
- Further reduce to 300 lines (~2000 tokens)
- More aggressive extraction to docs/
- Risk: Might remove content that's actually useful

**Recommendation: Option A** — Get under budget, establish the maintenance pattern, observe for a few sessions, then prune further if needed.

## Token Budget Calculation

Current estimate:
- ~500 lines × ~6 tokens/line average = ~3000 tokens
- Target: 400 lines × ~6 tokens/line = ~2400 tokens
- Savings: ~600 tokens (20% reduction)

**Note:** This is CLAUDE.md alone, not counting the Ponytail skill that's also injected. Combined context budget should be considered.

## Conclusion

We've avoided the worst failure modes (empty, stale, conflicting) but are on the path to bloat. The article's core insight — **treat CLAUDE.md as a neural net with a size budget** — is exactly what we need.

**Action:** Prune now, set budget, establish maintenance loop. This PR implements the pruning and budget; future PRs should follow the gradient descent pattern (add new learnings, prune to stay under budget).

## Revised Recommendations Based on Complete Article

### Immediate actions (this PR - REVISED)

1. ✅ **Set token budget:** 3000 tokens / 400 lines (done, currently at 239 lines)
2. ✅ **Prune low-value content:** Threading post-mortem, verbose procedures (done, 52% reduction)
3. ✅ **Add maintenance strategy header:** "Last pruned" + token budget (done)
4. ⚠️ **WRONG EXTRACTION TARGET:** We extracted to `docs/` (human-readable, NOT agent-invocable)
   - Should have extracted to **skills** (agent-invocable via Skill tool)
   - This is the key architectural mistake revealed by the complete article

### Next actions (follow-up PRs)

#### 1. Convert docs/ to skills/ (HIGH PRIORITY)

**Why:** Skills = pluggable, lazy-loaded architecture. Docs = dead weight (never loaded into context).

Create skills with detectable triggers:
- `.claude/skills/pr-babysit.md` — triggers: "create PR", "open PR", "PR checklist"
- `.claude/skills/version-bump.md` — triggers: "release", "version", "make tag"
- `.claude/skills/deploy-server.md` — triggers: "deploy", "server PR", "restart"

Keep docs/ only for human-readable references that agents should NOT auto-load.

#### 2. Evaluate backpass tool (EXPLORATION)

Kun Chen's automation: https://github.com/kunchenguid/backpass

```bash
npx -y backpass  # in this repo
```

What it does:
- Collects transcripts from Claude Code/Cursor/etc. session stores
- Distills to loss signals (96-99% reduction)
- Calculates gradients per CLAUDE.md addressable unit
- Proposes max 5 edits with verbatim evidence
- Enforces: new rule needs 2+ sessions, post-edit file fits budget
- Human review via `backpass apply`

Decision: Try it weekly for 1 month, see if it surfaces patterns we miss manually.

#### 3. Add evidence gates to maintenance strategy (AUTOMATION)

Update CLAUDE.md maintenance section with scientific rigor requirements:
- **Evidence from transcripts only**, not anecdotes
- **New rules need 2+ independent sessions** (batch requirement)
- **Max 5 edits per training pass** (learning rate constraint)
- **Verbatim quote required** for every edit
- **Weekly cadence** on active repos, not quarterly

#### 4. Extract more content to skills (ONGOING)

Apply the release valve pattern:
- **Broad** (20%+ sessions or safety-critical) → stays in CLAUDE.md
- **Narrow with detectable trigger** → extract to skill
- **Narrow without trigger** → delete

Candidates for extraction:
- Test workflow patterns → skill (trigger: "run tests", "CI", "pytest")
- Deployment procedures → skill (already identified above)
- Windows encoding workarounds → compress to 1 line or delete (rare edge case)

#### 5. Adopt the backpass rhythm (if trial successful)

Replace "every 3 months audit" with:
- Weekly `npx -y backpass` run
- Review proposed edits (accept/reject with evidence)
- Rejected edits are remembered (won't re-propose without new evidence)
- Track CLAUDE.md effectiveness over time

## Conclusion (REVISED)

**What this PR accomplished:**
- ✅ Pruned CLAUDE.md from 500→239 lines (52% reduction)
- ✅ Set token budget (3000 tokens / 400 lines)
- ✅ Added maintenance strategy header
- ✅ Extracted procedures to docs/

**What we learned from the complete article:**
- Skills > Docs: We should have extracted to agent-invocable skills, not human-only docs
- Automation > Manual: backpass tool provides scientific rigor (transcripts, evidence, gates)
- Weekly > Quarterly: Training cadence matters
- Release valve pattern: Broad (20%+ sessions) → CLAUDE.md; Narrow with trigger → skill; Narrow without trigger → delete

**Next steps:**
1. Convert docs/ to skills/ (follow-up PR)
2. Try backpass tool weekly for 1 month
3. Add evidence gates to maintenance process
4. Continue extracting to skills using release valve pattern

**The big insight:** CLAUDE.md is a neural net. We did one manual gradient descent pass (this PR). Now we need the training infrastructure (backpass) and the architecture (skills as lazy-loaded weights).
