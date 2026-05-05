{{ config(materialized='table', schema='staging') }}

with detail as (
    select *
    from {{ source('extract', 'sales_order_detail') }}
),

header as (
    select *
    from {{ source('extract', 'sales_order_header') }}
)

select
    d.sales_order_id,
    d.sales_order_detail_id,
    d.product_id,
    h.customer_id,
    h.sales_person_id,
    h.territory_id,

    h.order_date,
    h.ship_date,

    d.order_qty,
    d.unit_price,
    d.unit_price_discount,
    d.line_total,

    -- basic derived metric
    d.order_qty * d.unit_price as gross_value

from detail d
left join header h
    on d.sales_order_id = h.sales_order_id
