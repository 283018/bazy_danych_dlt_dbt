{{ config(materialized='table', schema='staging') }}

with cost as (
    select
        product_id,
        start_date,
        end_date,
        standard_cost,
        row_number() over (
            partition by product_id
            order by start_date desc
        ) as rn
    from {{ source('extract', 'product_cost_history') }}
),

latest_cost as (
    select *
    from cost
    where rn = 1
)

select
    p.product_id as product_key,
    p.name as product_name,
    p.product_number,
    p.color,
    p.size,
    p.weight,

    p.product_subcategory_id,

    coalesce(c.standard_cost, 0) as standard_cost,
    coalesce(p.list_price, 0) as list_price,

    (coalesce(p.list_price, 0) - coalesce(c.standard_cost, 0)) as profit,

    case
        when p.list_price = 0 then 0
        else (p.list_price - coalesce(c.standard_cost, 0)) / p.list_price
    end as margin,

    case
        when p.sell_end_date is null then 'ACTIVE'
        else 'INACTIVE'
    end as active_status,

    datediff(month, p.sell_start_date, coalesce(p.sell_end_date, getdate())) as sold_for_months,

    case
        when p.list_price < 100 then 'LOW'
        when p.list_price < 300 then 'MEDIUM'
        when p.list_price < 500 then 'HIGH'
        else 'VERY HIGH'
    end as price_segment

from {{ source('extract', 'product') }} p
left join latest_cost c
    on p.product_id = c.product_id;
