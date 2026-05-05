{{ config(materialized='table', schema='staging') }}

with dates as (
    select date_key
    from {{ ref('stg_order_date') }}
),

rates as (
    select
        cast(effective_date as date) as rate_date,
        mid_rate
    from {{ source('extract', 'currency_rate_data') }}
)

select
    d.date_key,

    (
        select top 1 r.mid_rate
        from rates r
        where r.rate_date <= d.date_key
        order by r.rate_date desc
    ) as mid_rate

from dates d;
