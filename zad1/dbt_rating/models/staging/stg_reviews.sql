with source_data as (
    select *
    from {{ source('raw', 'reviews') }}
)

select
    cast(reviewid as integer) as review_id,
    cast(productid as integer) as product_id,
    case
        when nullif(trim(date), '') is null then null
        when nullif(trim(date), '') ~ '^\d{1,2}/\d{1,2}/\d{4}$' then
            case
                when split_part(date, '/', 1)::int > 12 then to_date(date, 'DD/MM/YYYY')
                when split_part(date, '/', 2)::int > 12 then to_date(date, 'MM/DD/YYYY')
                else to_date(date, 'MM/DD/YYYY')
            end
        else null
    end as review_date,
    cast(rating_website as numeric(10, 4)) as rating_website,
    cast(rating_shipping as numeric(10, 4)) as rating_shipping,
    cast(rating_product as numeric(10, 4)) as rating_product,
    cast(rating_overall as numeric(10, 4)) as rating_overall,
    nullif(lower(trim(gender)), '') as gender,
    nullif(email, '') as email,
    nullif(job, '') as job,
    case
        when post_code is null then null
        else cast(cast(post_code as bigint) as text)
    end as post_code,
    nullif(source, '') as source,
    case
        when lower(trim(cast(did_purchase as text))) in ('1', 'true', 't', 'yes', 'y') then true
        when lower(trim(cast(did_purchase as text))) in ('0', 'false', 'f', 'no', 'n') then false
        else null
    end as did_purchase,
    case
        when cast(did_recommend as integer) = 1 then true
        when cast(did_recommend as integer) = 0 then false
        else null
    end as did_recommend,
    cast(is_usefull as integer) as is_useful_votes,
    nullif(user_agent, '') as user_agent,
    nullif(ip, '') as ip
from source_data