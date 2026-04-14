# RadioHeader MCP Server

The RadioHeader MCP server exposes the cross-project memory layer as [Model
Context Protocol](https://modelcontextprotocol.io/) tools so **any
MCP-compatible agent** — Claude Desktop, Cursor, Windsurf, Gemini Code
Assist, Continue.dev, the MCP Inspector, custom clients — can run the same
"Search → Apply → Trace" behavior that Claude Code and Codex CLI get through
the native runtime hooks.

All tools are read-only. The server reads from the same
`~/.claude/radioheader/` data layer that your local CLI, Claude Code, and
Codex CLI already use — nothing is duplicated, nothing is cached. Topics and
shortwave entries captured on one agent are immediately searchable from any
other MCP client.

## What the server exposes

| Tool | Purpose |
|------|---------|
| `radioheader_search` | BM25 + synonym search over topics, shortwave, and community entries. Returns structured hits (id, title, symptom, fix, source project, rank). Supports `\|`-separated OR queries and optional single-field restriction. |
| `radioheader_list_projects` | Enumerate every project registered in `project-registry.json` with its tech stack, domains, problems, pain points, and attention weight. |
| `radioheader_trace_project` | Resolve a `[source:ProjectName]` tag to the source project's filesystem path and memory directory so the agent can read the project's local `memory/` files for deeper context. |
| `radioheader_list_topics` | Browse topic files when search returns nothing useful. Returns id, heading, line count. |
| `radioheader_read_topic` | Read the full body of a topic file (truncated to `max_chars`). |
| `radioheader_read_shortwave` | Read a shortwave entry by id. Accepts `sw-foo`, `foo`, `sw-foo.md`, or a full path. Returns parsed frontmatter + body. |
| `radioheader_context_digest` | Return the current `context-digest.md` — the user-profile + project-landscape snapshot produced by `radioheader consolidate`. Useful as a SessionStart-equivalent call so the agent knows who it's helping. |
| `radioheader_stats` | Health snapshot: data-layer path, topic/shortwave/project counts, search-index readiness. Use as a lightweight liveness check before relying on the other tools. |

## Prerequisites

1. RadioHeader installed and initialized (`./install.sh`).
2. Python 3.10+ (for the MCP SDK).
3. The `mcp` package installed in whichever Python your MCP client will use
   to launch the server:

   ```bash
   pip install "mcp[cli]"
   ```

4. A built FTS5 search index — if `radioheader doctor` warns about it, run
   `radioheader index --rebuild` once.

## Installing the server script

`install.sh` copies `radioheader-mcp-server.py` next to the CLI binary. If
you're working from the git checkout before installing, the script lives at
the repo root. Either location is fine — the server auto-discovers
`fts-search.py` next to itself.

You can verify the server script runs locally:

```bash
python3 /path/to/radioheader-mcp-server.py
# It prints nothing and waits for MCP protocol messages on stdin.
# Kill it with Ctrl-C.
```

The server honours `$RADIOHEADER_DIR` if you want to point it at a
non-default data directory.

## Client setup

### Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS)
or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "radioheader": {
      "command": "python3",
      "args": [
        "/Users/you/.local/bin/radioheader-mcp-server.py"
      ]
    }
  }
}
```

If Claude Desktop can't find `python3`, use a full path
(`/opt/homebrew/bin/python3` on Apple Silicon, `/usr/bin/python3` for the
system Python, or the interpreter inside the venv where you `pip install
mcp`'d).

Restart Claude Desktop. A hammer icon appears in the chat composer; clicking
it lists the eight `radioheader_*` tools.

### Cursor

In Cursor's settings, go to **Features → MCP** and add a new server:

```json
{
  "mcpServers": {
    "radioheader": {
      "command": "python3",
      "args": [
        "/Users/you/.local/bin/radioheader-mcp-server.py"
      ]
    }
  }
}
```

Cursor reloads automatically. The tools become available in the composer via
`@radioheader_search` or through the tool picker.

### Windsurf / Continue.dev / other MCP clients

Any client that supports stdio MCP servers follows the same pattern — point
`command` at `python3` and `args` at the absolute path to
`radioheader-mcp-server.py`. The server speaks plain stdio MCP and requires
no special capabilities.

### Claude Code (optional)

Claude Code already has native RadioHeader hooks, so the MCP server is
redundant in that environment. But if you prefer the MCP surface (structured
return values, explicit tool calls) you can add it too:

```bash
claude mcp add radioheader python3 /path/to/radioheader-mcp-server.py
```

### MCP Inspector (debugging)

The official MCP Inspector is the easiest way to sanity-check the server:

```bash
npx @modelcontextprotocol/inspector python3 /path/to/radioheader-mcp-server.py
```

It opens a local web UI where you can list the tools and call them with
arbitrary JSON arguments.

## Suggested system prompt for MCP clients

Unlike Claude Code and Codex, most MCP clients do not inject RadioHeader's
behavioral rules automatically. Paste this into the client's system prompt
so the agent actually uses the tools:

```text
You have access to RadioHeader — a cross-project memory layer — via the
`radioheader_*` tools. When the user reports a technical problem:

1. Call `radioheader_search` with symptom keywords (and `|`-separated
   synonyms) BEFORE starting independent analysis. Example:
   `radioheader_search(query="white screen|blank screen|slow launch")`.
2. If relevant hits come back, cite them in your answer. Name the source
   project from the `projects` field. Call `radioheader_read_shortwave` or
   `radioheader_read_topic` for full detail when needed.
3. If an entry points to a specific solution, verify the solution applies
   before falling back to independent analysis.
4. Use `radioheader_trace_project` to resolve `[source:ProjectName]` tags
   to filesystem paths when more context is needed.

Finding relevant experience but not citing or applying it is explicitly
wrong. If the search has no useful hits, proceed with independent analysis
and say so out loud.

Optionally, at the start of a long session, call
`radioheader_context_digest` once to load the user's project landscape.
```

## Troubleshooting

**`ImportError: No module named mcp`** — the `mcp` package isn't installed in
the Python interpreter your client is using. Check which Python the client
launches (Claude Desktop uses whatever `python3` resolves to in its PATH)
and `pip install "mcp[cli]"` into that interpreter, or point `command` at a
venv that has `mcp` installed.

**`fts-search.py not found next to the MCP server`** — the server expects
`fts-search.py` to live in the same directory. `install.sh` handles this by
copying both scripts next to the CLI. If you moved only one file, copy
`fts-search.py` next to `radioheader-mcp-server.py` and retry.

**`search.db is missing`** — the FTS5 index hasn't been built. Run
`radioheader index --rebuild`.

**Nothing happens when I call a tool** — make sure your MCP client is
actually reading structured output. Some older clients only surface the
serialized text content block; in that case the tool result is in
`result.content[0].text` as JSON, not in `result.structuredContent`.

## Limitations

- **Read-only.** This release does not expose `learn`, `publish`, or `vote`.
  Those commands have side effects and will come in a later release once
  the MCP surface is validated.
- **No semantic search.** Ranking is BM25 + synonym expansion, same as the
  CLI. If a query paraphrases the entry body in a way the synonym table
  doesn't cover, the hit may not surface. Use `|` to stack your own
  symptom synonyms until the global synonym table catches up.
- **Stdio transport only.** The server currently runs as a stdio subprocess
  of each MCP client. A streamable-HTTP variant for remote use is not
  provided here.
