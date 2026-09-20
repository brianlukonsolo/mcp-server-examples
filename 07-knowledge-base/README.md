# 07 — Versioned knowledge base

Combines SQLite FTS5 search, immutable revisions, resource templates and
optimistic concurrency. This is lexical search, without an embedding model.
Export MCP_AUTH_TOKEN (see the root guide), then use separate terminals:

```bash
python 07-knowledge-base/server.py
python clients/05-interactive-cli.py http://localhost:8107/mcp
```

Paste these commands into the interactive client:

```text
put_document {"slug":"onboarding","title":"Team onboarding","body":"New teammates pair with a mentor for their first week."}
search_documents {"query":"mentor"}
get_document {"slug":"onboarding"}
put_document {"slug":"onboarding","title":"Team onboarding","body":"New teammates pair with a mentor for two weeks.","expected_version":1}
get_document {"slug":"onboarding","version":1}
```

Repeat the update with expected_version 1: it fails because the current version
is 2. Creation uses version 0. The version check, document write, revision insert
and search index replacement share a transaction. Two clients cannot both
successfully overwrite the same version.

`search_documents` treats input as literal words with AND semantics, quotes each
FTS term and returns ranked snippets. `list_documents` pages through metadata.
`knowledge://documents/{slug}` exposes the current document as a resource;
`answer_with_sources` is a prompt asking clients to cite slug and version.

Limits: 200-character titles, 100,000-character bodies and 20-word search queries.
Data lives in `DATA_DIR/knowledge.db`, persisted by Compose. Revision history is
retained indefinitely. This example does not implement retention policies,
per-document permissions, or semantic similarity search.
