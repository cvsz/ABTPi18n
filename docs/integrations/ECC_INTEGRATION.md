# ECC Integration (affaan-m/ECC)

This project supports external strategy packs under `strategies/external/`.
Because external network access may be restricted in some runtime environments,
this integration is designed to be **safe by default** and **manual-approval friendly**.

## What was integrated

- A dedicated integration descriptor was added at `strategies/external/ecc_integration.yaml`.
- The descriptor keeps execution in dry-run mode by default.
- No live trading is enabled automatically.

## Installation

1. Clone the ECC repository locally:

   ```bash
   git clone https://github.com/affaan-m/ECC.git /tmp/ECC
   ```

2. Copy the strategy files you want to use into this project:

   ```bash
   mkdir -p strategies/external/ecc
   cp -r /tmp/ECC/* strategies/external/ecc/
   ```

3. If ECC provides Python strategy modules, make sure each strategy class:
   - Inherits from `core.strategy_base.Strategy`
   - Defines a unique `name`
   - Registers itself with `StrategyRegistry.register(...)` (or relies on autoload class detection)

4. Load external strategies from your startup/runtime hook:

   ```python
   from core.strategy_autoload import load_external_strategies

   loaded = load_external_strategies("strategies/external/ecc")
   print("Loaded ECC strategies:", loaded)
   ```

## Safety defaults

Before enabling any ECC strategy for production:

- Keep `auto_trade: false` unless an operator explicitly approves it.
- Use paper trading/sandbox exchange credentials first.
- Validate max position size, stop loss, and drawdown limits.
- Ensure audit logging is active for every order event.

## Notes

- This integration document intentionally avoids pulling remote code automatically.
- Manual vendor/import keeps supply-chain review explicit and auditable.
