# WhatWay AI and retrieval architecture

## Product rule

The model may explain retrieved records. It may not select records without the
structured search layer, invent a resource, or replace location and eligibility
filters.

## Implemented now

1. Structured JSON supplies canonical resource records.
2. The shared API/WhatsApp pipeline de-duplicates state datasets and removes
   malformed, inactive, or closed records before ranking.
3. Category, state, and language constraints are hard metadata filters. ZIP
   and service are explicit ranking signals.
4. BM25-style lexical ranking handles service names, acronyms, and program
   names.
5. When Ollama and `OLLAMA_EMBEDDING_MODEL` are available, semantic similarity
   is blended into lexical scores. If either is unavailable, retrieval falls
   back to lexical mode without breaking search.
6. Every response includes retrieval mode and stable `STATE:id` source IDs.
   Displayed phone, address, website, and name always come from the record.
7. The optional chat model extracts intent and writes a short introduction for
   already-selected records. Templates cover model outages.

Ollama is the selected local/private chat and embedding provider. The default
embedding model is `nomic-embed-text`; install it separately from the chat
model. Cloudflare can host the website and edge API without exposing local
port 11434 publicly.

## National-data next steps

Do not embed every field and call that RAG. Keep extending hybrid retrieval in
this order:

1. Hard metadata filters: state, category, eligibility, language, and active
   listing status.
2. Geographic scoring: exact ZIP, nearby ZIP, then distance.
3. Keyword search for service names, acronyms, and program names.
4. Vector similarity only for service descriptions, labels, subcategories,
   languages, and availability labels.
5. Merge the keyword and vector candidates, then apply the existing quality and
   distance ranking.

Each returned answer carries resource IDs and displays the source record's
name, phone, address, and last-verified date. Generated prose is never a source.

The current committed state files contain roughly 650 rows before malformed
placeholder rows and duplicates are removed, not 2,000 verified clinics. Do
not publish a 2,000-clinic claim until ingestion and verification evidence
supports it.

## Local Ollama setup

```bash
ollama pull llama3
ollama pull nomic-embed-text
ollama serve
```

Set `OLLAMA_MODEL` for chat and `OLLAMA_EMBEDDING_MODEL` for retrieval. The
`retrieval.mode` API field is `hybrid` when embeddings ran and `lexical` when
the safe fallback was used. Resource embeddings persist in the ignored
`.cache/ollama_embeddings.json` file by default, keyed by model and a hash of
the public service text. Set `WHATWAY_EMBEDDING_CACHE` to move that cache. It
contains neither queries nor chat history.

## Cloudflare target

- D1 or another relational store: canonical resource records and verification
  metadata.
- A private Ollama service: intent extraction, translation, embeddings, and
  concise grounded summaries. Protect it behind an authenticated server-side
  API; never expose port 11434 to the public internet.
- Vectorize or AI Search: optional semantic retrieval over service-description
  text, with metadata filters created before vectors are inserted.
- R2: source documents or snapshots when the national ingestion pipeline needs
  auditable evidence.

The public website and browser client should call one search API. The WhatsApp
channel should call that same API so ranking, citations, safety rules, and
analytics do not fork by channel.

## Privacy and safety

- Do not embed or retain raw chat transcripts, phone numbers, addresses,
  verification notes, immigration status, medical details, or precise user
  location. Only public service descriptors and coarse metadata are embedded.
- Derive coarse search filters in memory and discard the original message after
  the retention window.
- Log resource IDs and aggregate query categories, not sensitive free text.
- Always show that listings are informational and should be confirmed directly.
