with source_data as (
    select *
    from {{ source('raw', 'ratings') }}
)

select
    cast(review_id as integer) as review_id,
    cast(product_id as integer) as product_id,
    cast(review_date as date) as review_date,
    cast(rating_website as numeric(10, 4)) as rating_website,
    cast(rating_shipping as numeric(10, 4)) as rating_shipping,
    cast(rating_product as numeric(10, 4)) as rating_product,
    cast(rating_overall as numeric(10, 4)) as rating_overall,
    nullif(lower(trim(gender)), '') as gender,
    nullif(email, '') as email,
    nullif(job, '') as job,
    nullif(post_code, '') as post_code,
    nullif(source, '') as source,
    cast(did_purchase as boolean) as did_purchase,
    cast(did_recommend as boolean) as did_recommend,
    cast(is_useful_votes as integer) as is_useful_votes,
    nullif(user_agent, '') as user_agent,
    nullif(ip, '') as ip
from source_data