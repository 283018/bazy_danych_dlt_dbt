{{ config(materialized='table', schema='staging') }}

with bounds as (
    select
        cast(min(order_date) as date) as start_date,
        cast(max(order_date) as date) as end_date
    from {{ source('extract', 'sales_order_header') }}
),

numbers as (
    select top (10000)
        row_number() over (order by (select null)) - 1 as n
    from sys.all_objects a
    cross join sys.all_objects b
),

dates as (
    select
        dateadd(day, n, start_date) as d
    from numbers
    cross join bounds
    where dateadd(day, n, start_date) <= end_date
)

select
    d as date_key,

    day(d) as day_of_month,
    datename(weekday, d) as day_name,

    month(d) as month_number,
    datename(month, d) as month_name,

    datepart(quarter, d) as quarter,

    case when month(d) <= 6 then 1 else 2 end as half_year,
    year(d) as year_number,

    case when datename(weekday, d) in ('Saturday', 'Sunday') then 1 else 0 end as is_weekend

from dates;
