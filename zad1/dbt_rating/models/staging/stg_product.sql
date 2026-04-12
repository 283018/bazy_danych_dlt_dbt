with source_data as (
    select *
    from {{ source('raw', 'product') }}
)

select
    cast(product_id as integer) as product_id,
    nullif(name, '') as product_name,
    nullif(product_number, '') as product_number,
    cast(make_flag as boolean) as make_flag,
    cast(finished_goods_flag as boolean) as finished_goods_flag,
    cast(safety_stock_level as integer) as safety_stock_level,
    cast(reorder_point as integer) as reorder_point,
    cast(standard_cost as numeric(18, 4)) as standard_cost,
    cast(list_price as numeric(18, 4)) as list_price,
    cast(days_to_manufacture as integer) as days_to_manufacture,
    cast(sell_start_date as timestamp) as sell_start_date,
    cast(discontinued_date as timestamp) as discontinued_date,
    nullif(color, '') as color,
    nullif(class, '') as product_class,
    nullif(size, '') as size,
    nullif(style, '') as style,
    cast(product_subcategory_id as integer) as product_subcategory_id,
    cast(product_model_id as integer) as product_model_id
from source_data