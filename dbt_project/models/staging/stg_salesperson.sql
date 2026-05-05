{{ config(materialized='table', schema='staging') }}

select
    sp.business_entity_id as salesperson_key,

    concat_ws(' ',
        p.first_name,
        p.middle_name,
        p.last_name
    ) as full_name,

    sp.territory_id,

    sp.sales_quota,
    sp.bonus,
    sp.commission_pct,
    sp.sales_ytd,
    sp.sales_last_year

from {{ source('extract', 'salesperson') }} sp
left join {{ source('extract', 'person') }} p
    on sp.business_entity_id = p.business_entity_id;
