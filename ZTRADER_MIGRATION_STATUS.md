# zTrader Consolidation Status

Date: 2026-09-12
Lifecycle: FEATURE_FREEZE

This repository is a migration/research source for the canonical ZeaZ trading architecture. New standalone trading-platform capabilities should not be added here while consolidation is active.

## Preserve and migrate

- i18n UI
- CCXT patterns
- strategy metadata
- websocket/notification patterns
- useful tests

## Canonical destinations

- execution/research -> cvsz/zksato
- UI -> cvsz/zdash
- intelligence -> cvsz/zworkforce

## Retirement rule

Do not delete or archive implementation code until a feature inventory, parity matrix, migrated tests, runtime-reference cleanup, green CI, and rollback evidence exist.

Live-money automation is not authorized by this migration.

`cvsz/zsme` is explicitly outside this program and must not be inspected or modified.
