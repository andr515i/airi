"""Small CLI for owning, inspecting and deleting Home's memory."""

from __future__ import annotations

import argparse
import os

import uvicorn

from . import store


def main() -> None:
    parser = argparse.ArgumentParser(prog="home-memory", description="Home's local continuity layer")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("serve", help="Start the localhost OpenAI-compatible bridge")
    commands.add_parser("key", help="Show the local API key to put in AIRI")
    commands.add_parser("profile", help="Show the editable profile.md path")
    commands.add_parser("status", help="Show the recording state and stored counts")
    remember = commands.add_parser("remember", help="Save one durable personal/project fact")
    remember.add_argument("text", help="What to remember, in your own words")
    forget = commands.add_parser("forget", help="Delete a saved memory by ID")
    forget.add_argument("id", type=int)
    forget_turn = commands.add_parser("forget-turn", help="Delete one stored exchange by ID")
    forget_turn.add_argument("id", type=int)
    commands.add_parser("memories", help="List manually saved memories")
    commands.add_parser("history", help="List recent exchanges")
    search = commands.add_parser("search", help="Search stored dialogue and memories")
    search.add_argument("query")
    commands.add_parser("pause", help="Stop recording AND injecting memories")
    commands.add_parser("resume", help="Resume memory recording and retrieval")
    args = parser.parse_args()

    root = store.data_home()
    store.init(root)
    if args.command == "serve":
        from .server import create_app
        app = create_app(root)
        print("Home Memory Bridge: http://127.0.0.1:8001/v1")
        print("Local API key: run `home-memory key` in another terminal")
        uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("HOME_MEMORY_PORT", "8001")), access_log=False)
    elif args.command == "key":
        print(store.get_api_key(root))
    elif args.command == "profile":
        print(root / "profile.md")
    elif args.command == "status":
        with store.connect(root) as db:
            count = db.execute("SELECT count(*) FROM exchanges").fetchone()[0]
            notes = db.execute("SELECT count(*) FROM notes").fetchone()[0]
        print(f"History recording: {'on' if store.recording(root) else 'paused'}; {count} exchanges, {notes} memories")
        print(f"Local data: {root}")
    elif args.command == "remember":
        print(f"Saved memory #{store.add_note(root, args.text)}")
    elif args.command == "forget":
        print("Memory deleted" if store.forget_note(root, args.id) else "No memory with that ID")
    elif args.command == "forget-turn":
        print("Exchange deleted" if store.forget_exchange(root, args.id) else "No exchange with that ID")
    elif args.command == "memories":
        for r in reversed(store.list_notes(root)):
            print(f"#{r['id']} [{r['created_at']}] {r['text']}")
    elif args.command == "history":
        for r in reversed(store.recent(root, 20)):
            print(f"#{r['id']} [{r['created_at']}] You: {r['user_text'][:180]}\n  AI: {r['assistant_text'][:180]}\n")
    elif args.command == "search":
        for name in ("notes", "exchanges"):
            for r in store.search(root, args.query, name, 10):
                excerpt = r["text"] if name == "notes" else f"You: {r['user_text'][:200]} | AI: {r['assistant_text'][:200]}"
                print(f"{name} #{r['id']}: {excerpt}")
    elif args.command in ("pause", "resume"):
        store.set_recording(root, args.command == "resume")
        print("Memory resumed" if args.command == "resume" else "Memory paused; existing data untouched")


if __name__ == "__main__":
    main()
