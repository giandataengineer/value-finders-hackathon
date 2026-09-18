-- SILVER · dimensiones: referencia de activos y perfiles de cliente tipados y validados.
CREATE OR REPLACE TABLE silver.cuarentena (tabla VARCHAR, _row_id BIGINT, motivo VARCHAR, detalle VARCHAR);

CREATE OR REPLACE TABLE silver.asset_reference AS
SELECT _row_id, asset_id, issuer_id, name, sector, country, market, currency
FROM bronze.asset_reference;

CREATE OR REPLACE TABLE silver.client_profiles AS
SELECT _row_id, client_id, profile_name, base_currency,
       CAST(horizon_months AS INTEGER) AS horizon_months, risk_tolerance,
       CAST(max_drawdown_tolerance_pct AS INTEGER) AS max_drawdown_tolerance_pct,
       liquidity_need, priority, "constraint"
FROM bronze.client_profiles;
