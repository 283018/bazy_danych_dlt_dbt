select
    product_id,
    count(*) as reviews_count,
    round(avg(rating_overall), 2) as avg_rating_overall,
    round(avg(rating_product), 2) as avg_rating_product,
    round(avg(rating_shipping), 2) as avg_rating_shipping,
    round(avg(rating_website), 2) as avg_rating_website
from {{ ref('stg_ratings') }}
group by 1