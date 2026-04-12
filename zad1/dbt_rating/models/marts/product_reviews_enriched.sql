select
    r.review_id,
    r.product_id,
    p.product_name,
    p.product_number,
    p.color,
    p.product_class,
    p.standard_cost,
    p.list_price,
    r.review_date,
    r.rating_overall,
    r.rating_product,
    r.rating_shipping,
    r.rating_website,
    r.did_purchase,
    r.did_recommend,
    r.source,
    (p.product_id is not null) as product_found
from {{ ref('stg_reviews') }} r
left join {{ ref('stg_product') }} p
    on r.product_id = p.product_id