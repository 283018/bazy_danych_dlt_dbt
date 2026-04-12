select
    product_id,
    coalesce(max(product_name), 'UNKNOWN') as product_name,
    count(*) as reviews_count,
    round(avg(rating_overall), 2) as avg_rating_overall,
    round(avg(rating_product), 2) as avg_rating_product,
    round(avg(rating_shipping), 2) as avg_rating_shipping,
    round(avg(rating_website), 2) as avg_rating_website,
    min(review_date) as first_review_date,
    max(review_date) as last_review_date
from {{ ref('product_reviews_enriched') }}
group by 1