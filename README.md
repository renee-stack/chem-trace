## ChemTrace

ChemTrace is an autonomous AI multi-agent platform designed to automate the retrosynthetic analysis and procurement scouting workflow for medicinal chemists. By moving beyond simple LLM text generation into specialized chemical reasoning, ChemTrace reduces the "Search-to-Bench" latency—the time it takes to move from a molecular design to a physical laboratory experiment—from days to minutes.

### Person C: LLM model (Anthropic)

If you see **`model: claude-3-5-sonnet-latest` / 404 not_found**, that model ID is no longer valid for the current API. The code defaults to **`claude-sonnet-4-6`** and tries fallbacks.

Optional `.env` override:

```env
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-sonnet-4-6
```

See [Anthropic models](https://docs.anthropic.com/en/docs/about-claude/models) for current IDs.
