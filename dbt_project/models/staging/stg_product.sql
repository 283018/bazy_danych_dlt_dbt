{{ config(materialized='table', schema='staging') }}

with cost as (
    select
        product_id,
        standard_cost,
        start_date,
        end_date,
        row_number() over (
            partition by product_id
            order by coalesce(end_date, start_date) desc, start_date desc
        ) as rn
    from {{ source('extract', 'product_cost_history') }}
),

latest_cost as (
    select *
    from cost
    where rn = 1
),

ratings as (
    select
        productid as product_id,
        avg(cast(rating_product as decimal(10,4))) as avg_rating_product,
        min(cast(rating_product as decimal(10,4))) as min_rating_product,
        max(cast(rating_product as decimal(10,4))) as max_rating_product,
        count(*) as rating_count
    from {{ source('extract', 'product_rating') }}
    group by productid
)

select
    p.product_id as product_key,
    p.name as product_name,
    p.product_number,
    coalesce(nullif(ltrim(rtrim(p.color)), ''), 'Unknown') as color,
    p.size,
    p.weight,
    upper(coalesce(nullif(ltrim(rtrim(p.size_unit_measure_code)), ''), 'UNKNOWN')) as size_unit_measure_code,
    upper(coalesce(nullif(ltrim(rtrim(p.weight_unit_measure_code)), ''), 'UNKNOWN')) as weight_unit_measure_code,

    p.product_subcategory_id,
    coalesce(ps.name, 'Unknown') as product_subcategory_name,
    ps.product_category_id,
    coalesce(pc.name, 'Unknown') as product_category_name,

    coalesce(c.standard_cost, 0) as standard_cost,
    coalesce(p.list_price, 0) as list_price,

    cast(coalesce(p.list_price, 0) - coalesce(c.standard_cost, 0) as decimal(18,4)) as profit,

    cast(
        case
            when coalesce(p.list_price, 0) = 0 then 0
            else (coalesce(p.list_price, 0) - coalesce(c.standard_cost, 0)) / nullif(p.list_price, 0)
        end as decimal(18,4)
    ) as margin,

    case
        when p.sell_end_date is null then 'ACTIVE'
        else 'INACTIVE'
    end as active_status,

    case
        when p.sell_start_date is null then null
        else datediff(
            month,
            p.sell_start_date,
            coalesce(p.sell_end_date, getdate())
        )
    end as sold_for_months,

    case
        when coalesce(p.list_price, 0) <= 100 then 'LOW'
        when coalesce(p.list_price, 0) <= 300 then 'MEDIUM'
        when coalesce(p.list_price, 0) <= 500 then 'HIGH'
        else 'VERY HIGH'
    end as discrete_price,

    r.avg_rating_product,
    r.min_rating_product,
    r.max_rating_product,
    r.rating_count

from {{ source('extract', 'product') }} p
left join latest_cost c
    on p.product_id = c.product_id
left join {{ source('extract', 'product_subcategory') }} ps
    on p.product_subcategory_id = ps.product_subcategory_id
left join {{ source('extract', 'product_category') }} pc
    on ps.product_category_id = pc.product_category_id
left join ratings r
    on p.product_id = r.product_id;
