# Home Memory Bridge (v0.1)

**Purpose:** Make your existing AIRI + llama.cpp setup remember previous conversations across AIRI sessions, without changing the language model, UI, or NVIDIA setup.

This is a *local* OpenAI-compatible gateway. AIRI talks to the bridge on port 8001; the bridge reads/writes an inspectable SQLite memory database, selectively provides relevant history to the LLM, and forwards requests to your existing llama.cpp server on port 8000. It supports ordinary responses and streamed Chat Completions.

```
AIRI (face/voice/chat)
  -> Home Memory Bridge :8001 (private SQLite + profile.md)
    -> existing llama.cpp :8000 (your model)
```

## Start on Arch / fish

Keep your existing `odysseus-llama` container running. The new bridge runs on **the host**, not in Docker, so both `127.0.0.1` ports refer to your PC.

```fish
cd ~/Documents/repos/airi/extensions/home-memory-bridge
python -m venv .venv
source .venv/bin/activate.fish
pip install -e .
home-memory serve
```

If you downloaded the standalone ZIP rather than the AIRI branch, `cd` into the extracted `home-memory-bridge` folder instead.

In another fish terminal, run:

```fish
cd ~/Documents/repos/airi/extensions/home-memory-bridge
source .venv/bin/activate.fish
home-memory key
```

In AIRI **Settings -> Providers -> OpenAI Compatible**, use:

- Base URL: `http://127.0.0.1:8001/v1`
- API key: output of `home-memory key`
- Protocol: Chat Completions

Then check AIRI **Modules -> Consciousness**: the same Qwen model should still be selected. Only the URL has changed. Do **not** change your llama.cpp Compose setup or port 8000.

To verify:

1. In AIRI, say: `I have decided to call today's temporary project Aurora Sandwich. Please remember that.`
2. Open a **new conversation** in AIRI.
3. Ask: `What was that temporary project called?`
4. You should get the name from the previous conversation without manually pasting context.
5. Inspect the stored exchange with `home-memory history` or `home-memory search 'Aurora Sandwich'`.

For a stronger permanent record, you can run `home-memory remember 'Aurora Sandwich is ...'`.

## Your memory is inspectable

```fish
home-memory status
home-memory profile                 # path to editable profile.md
home-memory remember 'Home prioritizes continuity over avatar polish.'
home-memory memories
home-memory history
home-memory search 'Home'
home-memory forget 1                # remove note #1
home-memory forget-turn 3           # remove recorded exchange #3
home-memory pause                   # stop remembering *and* injecting old records
home-memory resume
```

Your data lives in `~/.local/share/home-memory/` (or `HOME_MEMORY_DIR`), with:

- `profile.md`: editable, always-available baseline profile/working agreements
- `home.sqlite3`: searchable conversations and explicitly saved notes
- `api.key`: 0600 private token, used only for AIRI -> bridge authentication

`profile.md` is created once and never overwritten by updates. This version records completed text conversations automatically. It does **not** scrape the rest of your computer, capture audio/video, run a background model, or send memory anywhere else. Screenshots/other non-text content are not written to the transcript database, although those contents still pass through to your existing model when AIRI sends them.

### What it can and cannot do yet

**Works now:** Persistent local text history, automatic retrieval of recent/relevant past exchanges, streaming passthrough, curated notes, deletion, and recording pause. AIRI remains the user interface and your installed Qwen remains the brain. This should be the first concrete continuity improvement.

**Limitations:** Retrieval is keyword-based SQLite FTS5, not semantic embeddings. The model may still miss older facts phrased differently, or treat an old statement as current. No automated extraction of durable facts, no project indexing, no multi-device sync, no model-independent personality yet. The bridge can inspect only requests made through it; it cannot retroactively import existing AIRI conversations or ChatGPT memory. It stores the final user/assistant text, not complete tool or audio histories. A long answer may still be slow because of the selected LLM or TTS path.

**Privacy:** All persisted data stays on your local machine. The service binds only to `127.0.0.1`, requires a private token, and does not expose a memory HTTP admin endpoint. **Anything typed into AIRI may be stored locally** once recording is on, so don't paste secrets or sensitive information you do not want logged. `pause` stops new records and retrieval but retains existing history. To remove one, use `forget-turn` or delete the database yourself. Back up the folder securely if you value its contents.

## Testing

```fish
python -m unittest discover -s tests -v
```

## Next steps (only if living with this reveals the need)

1. Let this run for a week and identify genuine missing-memory problems.
2. Implement controlled durable memory extraction/summarization from chats, without running a huge model during competitive gaming.
3. Add project-scoped knowledge indexing, with explicit read-only permissions at first.
4. Improve voice latency and pacing separately; do not block memory work on TTS polish.
