{{ config(materialized='table', schema='staging') }}

select
    sp.business_entity_id as salesperson_key,

    p.first_name,
    p.middle_name,
    p.last_name,
    concat_ws(' ', p.first_name, p.middle_name, p.last_name) as full_name,

    sp.territory_id,
    st.name as territory_name,
    upper(st.country_region_code) as country_region_code,
    cr.name as country_name,
    st.[group] as continent,

    sp.sales_quota,
    sp.bonus,
    sp.commission_pct,
    sp.sales_ytd,
    sp.sales_last_year

from {{ source('extract', 'salesperson') }} sp
left join {{ source('extract', 'person') }} p
    on sp.business_entity_id = p.business_entity_id
left join {{ source('extract', 'sales_territory') }} st
    on sp.territory_id = st.territory_id
left join {{ source('extract', 'country_region') }} cr
    on st.country_region_code = cr.country_region_code;
