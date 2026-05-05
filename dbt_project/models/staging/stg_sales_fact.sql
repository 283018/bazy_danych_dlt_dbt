{{ config(materialized='table', schema='staging') }}

with detail as (
    select *
    from {{ source('extract', 'sales_order_detail') }}
),

header as (
    select *
    from {{ source('extract', 'sales_order_header') }}
),

currency as (
    select *
    from {{ ref('stg_currency_rate') }}
)

select
    d.sales_order_id,
    d.sales_order_detail_id,
    d.product_id,
    h.customer_id,
    h.sales_person_id,
    h.territory_id,

    cast(h.order_date as date) as order_date,
    cast(h.ship_date as date) as ship_date,

    d.order_qty,
    d.unit_price,
    d.unit_price_discount,
    d.line_total,

    cast(d.order_qty * d.unit_price as decimal(18,4)) as gross_value,

    c.mid_rate,
    c.rate_direction,

    cast(
        case
            when c.mid_rate is null then null
            else d.line_total * c.mid_rate
        end as decimal(18,4)
    ) as amount_pln

from detail d
left join header h
    on d.sales_order_id = h.sales_order_id
left join currency c
    on cast(h.order_date as date) = c.date_key;
