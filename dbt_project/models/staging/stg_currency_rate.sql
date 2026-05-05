{{ config(materialized='table', schema='staging') }}

with dates as (
    select date_key
    from {{ ref('stg_order_date') }}
),

rates as (
    select
        cast(effective_date as date) as rate_date,
        cast(mid_rate as decimal(18,6)) as mid_rate
    from {{ source('extract', 'currency_rate_data') }}
),

filled as (
    select
        d.date_key,
        r.rate_date,
        r.mid_rate
    from dates d
    outer apply (
        select top 1
            r.rate_date,
            r.mid_rate
        from rates r
        where r.rate_date <= d.date_key
        order by r.rate_date desc
    ) r
)

select
    date_key,
    mid_rate,
    lag(mid_rate) over (order by date_key) as previous_mid_rate,
    case
        when lag(mid_rate) over (order by date_key) is null then null
        when mid_rate > lag(mid_rate) over (order by date_key) then 'RISE'
        when mid_rate < lag(mid_rate) over (order by date_key) then 'FALL'
        else 'NO_CHANGE'
    end as rate_direction
from filled;
