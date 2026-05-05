{{ config(materialized='table', schema='staging') }}

select
    st.territory_id as territory_key,
    st.name as territory_name,
    upper(st.country_region_code) as country_region_code,
    cr.name as country_name,
    st.[group] as continent,

    st.sales_ytd,
    st.sales_last_year,
    st.cost_ytd,
    st.cost_last_year

from {{ source('extract', 'sales_territory') }} st
left join {{ source('extract', 'country_region') }} cr
    on st.country_region_code = cr.country_region_code;
