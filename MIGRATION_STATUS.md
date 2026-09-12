# Migration Status

Lifecycle: **FEATURE_FREEZE -> INVENTORY -> MIGRATION -> PARITY_TEST -> DEPRECATED -> ARCHIVE**

This repository is a migration source for the canonical ZeaZ trading architecture.

Preserve and migrate:
- i18n UI and locale assets
- useful strategy metadata/tests
- CCXT/exchange integration patterns
- monitoring, notification and WebSocket patterns

Canonical destinations:
- execution/research/risk -> `cvsz/zksato`
- intelligence/agents -> `cvsz/zworkforce`
- dashboard/UI -> `cvsz/zdash`
- model/provider routing -> `cvsz/zaiman`

Do not add new independent trading-platform features here during consolidation.

Archive/delete is not authorized until parity tests, reference cleanup, CI evidence and rollback documentation exist.

Explicit exclusion: `cvsz/zsme` is not part of this program.
