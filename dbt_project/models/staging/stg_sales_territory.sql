{{ config(materialized='table', schema='staging') }}

select
    territory_id as territory_key,
    name as territory_name,
    country_region_code,
    [group] as territory_group,

    sales_ytd,
    sales_last_year,
    cost_ytd,
    cost_last_year

from {{ source('extract', 'sales_territory') }};
