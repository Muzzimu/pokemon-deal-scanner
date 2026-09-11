# External research references

These files are retained as research/inspiration inputs. They are not production source-of-truth and should not override the scanner's tested rules.

## `ai_trading_agent_discussion_2026-06.json`

Telegram-export discussion covering FinMem-style memory, multi-agent trading architectures, deterministic execution layers, local/cloud LLM splits, walk-forward/backtesting/Monte Carlo ideas, and development workflows.

Original uploaded file SHA-256:
`8e78446c2e3014242e5b7b6f4cacdec8eadd9060ae9387b0bec856c3002e95dc`

Because the GitHub connector used from ChatGPT accepts text payloads rather than arbitrary large binary uploads, the exact JSON is stored losslessly as a gzip+base64 multipart archive under:

`docs/references/ai_trading_agent_discussion_2026-06.parts/`

Reconstruction contract:

```bash
cat docs/references/ai_trading_agent_discussion_2026-06.parts/part*.b64 \
  | base64 -d \
  | gunzip > ai_trading_agent_discussion_2026-06.json
sha256sum ai_trading_agent_discussion_2026-06.json
```

The reconstructed SHA-256 must equal the original hash above.

Useful project takeaways are incorporated selectively into `AGENTS.md` and `docs/EXPERIENCE_STORE.md`; anecdotal model rankings and unrelated trading infrastructure claims are not treated as evidence.

## `claude_code_tips_boris_anthropic_it.pdf`

Italian transcript/reformat of a Boris/Anthropic Claude Code tips talk. Relevant engineering patterns include codebase Q&A before edits, planning before coding, feedback loops through tests, concise project context files, Git/GitHub workflows, and parallel/worktree usage.

Original uploaded file SHA-256:
`d9e5e9f67c3c7162d18f88b27d4e5932cb3e57b6c28a0296067aab2978d06d1d`

The original PDF is stored directly at:

`docs/references/claude_code_tips_boris_anthropic_it.pdf`

The repository remains tool/model agnostic.
