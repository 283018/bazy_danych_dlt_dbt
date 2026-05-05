{{ config(materialized='table', schema='staging') }}

select
    sp.business_entity_id as salesperson_key,

    p.first_name,
    p.middle_name,
    p.last_name,
    concat_ws(' ',
        nullif(ltrim(rtrim(p.first_name)), ''),
        nullif(ltrim(rtrim(p.middle_name)), ''),
        nullif(ltrim(rtrim(p.last_name)), '')
    ) as full_name,

    coalesce(sp.territory_id, 0) as territory_id,
    coalesce(st.name, 'Unknown') as territory_name,
    coalesce(upper(st.country_region_code), 'UNK') as country_region_code,
    coalesce(cr.name, 'Unknown') as country_name,
    coalesce(st.[group], 'Unknown') as continent,

    coalesce(sp.sales_quota, 0) as sales_quota,
    coalesce(sp.bonus, 0) as bonus,
    coalesce(sp.commission_pct, 0) as commission_pct,
    coalesce(sp.sales_ytd, 0) as sales_ytd,
    coalesce(sp.sales_last_year, 0) as sales_last_year

from {{ source('extract', 'salesperson') }} sp
left join {{ source('extract', 'person') }} p
    on sp.business_entity_id = p.business_entity_id
left join {{ source('extract', 'sales_territory') }} st
    on sp.territory_id = st.territory_id
left join {{ source('extract', 'country_region') }} cr
    on st.country_region_code = cr.country_region_code;
