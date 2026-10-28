# Home — working state

## North star
Build a dependable personal AI with continuity, memory, project knowledge, useful everyday assistance, and eventually more embodied interaction. The user values having the assistant, not the act of implementing every component.

## Current choices
- User is comfortable delegating implementation to AI/Codex; code must remain comprehensible and editable.
- AIRI is an optional avatar/voice/chat interface, not the owner of Home's long-term identity.
- Existing llama.cpp Docker Compose server is the initial LLM backend at `127.0.0.1:8000/v1`.
- Add a minimal local memory gateway at `127.0.0.1:8001/v1`; do not rebuild model hosting, voice, or the desktop client.
- Text conversation transcripts are automatically retained locally; curated facts go into explicit notes; a user-owned profile.md defines a baseline.
- Keep local storage, explicit deletion, and visibility into memory. Current user statements trump old memories.

## Proven previously
- AIRI desktop launched on Linux after resolving an NVIDIA driver/library mismatch.
- AIRI reached locally hosted Qwen through its OpenAI Compatible provider.
- Kokoro voice began working after a cross-renderer lazy-load fix on branch `home/kokoro-local-load-fix` in `andr515i/airi`.
- Speech pacing/segmentation had been poor. The user switched from Heretic to vanilla Qwen; reasoning off improved latency.

## This slice
- Local OpenAI Chat Completions proxy, streaming and non-streaming.
- SQLite FTS retrieval of prior exchanges, editable profile and explicit memories.
- Local authentication, CLI inspection/deletion/pause.
- Tests using a mock llama.cpp backend. Actual behavior with AIRI needs local verification.

## Next experiment
Ask AIRI to remember a distinctive arbitrary fact; begin a separate conversation; ask for it without re-pasting. Check retrieval in `home-memory search`. If the model fails despite retrieved context, inspect prompt injection and reasoning. If retrieval fails for paraphrases, improve retrieval before adding more features.
