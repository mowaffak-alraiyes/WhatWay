# WhatWay AI and retrieval architecture

## Product rule

The model may explain retrieved records. It may not select records without the
structured search layer, invent a resource, or replace location and eligibility
filters.

## Today

1. Structured JSON supplies resource records.
2. Deterministic search applies category, state, ZIP, service, language, day,
   and availability signals.
3. The optional LLM extracts intent from conversational wording and writes a
   short introduction for the already-selected records.
4. If the LLM is off or unavailable, the same search completes with templates.

Ollama is the local-development provider. It is not a production dependency.
Cloudflare Workers AI is the production provider when credentials are supplied.

## When the national dataset is ready

Do not embed every field and call that RAG. Use hybrid retrieval in this order:

1. Hard metadata filters: state, category, eligibility, language, and active
   listing status.
2. Geographic scoring: exact ZIP, nearby ZIP, then distance.
3. Keyword search for service names, acronyms, and program names.
4. Vector similarity only for the remaining free-text service descriptions.
5. Merge the keyword and vector candidates, then apply the existing quality and
   distance ranking.

Each returned answer must carry resource IDs and display the source record's
name, phone, address, and last-verified date. Generated prose is never a source.

## Cloudflare target

- D1 or another relational store: canonical resource records and verification
  metadata.
- Workers AI: intent extraction, translation, and concise grounded summaries.
- Vectorize or AI Search: optional semantic retrieval over service-description
  text, with metadata filters created before vectors are inserted.
- R2: source documents or snapshots when the national ingestion pipeline needs
  auditable evidence.

The public website and browser client should call one search API. The WhatsApp
channel should call that same API so ranking, citations, safety rules, and
analytics do not fork by channel.

## Privacy and safety

- Do not embed or retain raw chat transcripts, phone numbers, immigration
  status, medical details, or precise user location.
- Derive coarse search filters in memory and discard the original message after
  the retention window.
- Log resource IDs and aggregate query categories, not sensitive free text.
- Always show that listings are informational and should be confirmed directly.
