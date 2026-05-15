/*
  mart_blue_carbon.sql
  ────────────────────
  Final analytical mart for blue carbon (Wetland Restoration & Conservation)
  projects on the Verra VCS registry.

  Grain     : one row per blue carbon project
  Join key  : project_id (numeric, Verra)
  Sources   : stg_verra + stg_berkeley
  Published : mart_blue_carbon.csv, Streamlit dashboard

  Key metrics produced:
  · credits_issued / credits_retired / credits_remaining
  · retirement_rate_pct
  · promise_vs_reality_gap_tco2e
  · pipeline_conversion_flag
  · annual issuance trend 2010-2025
*/

with verra as (

    select * from {{ ref('stg_verra') }}
    where is_blue_carbon = true

),

berkeley as (

    select * from {{ ref('stg_berkeley') }}
    where project_type = 'Wetland Restoration'

),

joined as (

    select
        -- identifiers
        b.berkeley_project_id,
        v.project_id,
        b.project_name,
        b.project_developer,

        -- classification
        b.scope,
        b.project_type,
        b.methodology,
        v.afolu_activities,
        b.reduction_or_removal,

        -- geography
        b.country,
        b.region,

        -- status (both sources for cross-validation)
        v.verra_status,
        b.berkeley_status,

        -- dates
        v.registration_date,
        v.crediting_start_date,
        v.crediting_end_date,
        v.crediting_period_years,
        b.first_vintage_year,

        -- credit volumes
        b.credits_issued,
        b.credits_retired,
        b.credits_remaining,
        b.buffer_pool_deposits,
        b.retirement_rate_pct,
        b.has_issued_credits,

        -- promise vs reality gap
        v.est_annual_reductions_tco2e,
        {{ safe_divide('v.est_annual_reductions_tco2e', 'b.credits_issued') }}
                                                        as promise_to_reality_ratio,
        v.est_annual_reductions_tco2e - b.credits_issued
                                                        as promise_vs_reality_gap_tco2e,

        -- pipeline flag
        case
            when b.has_issued_credits = false
             and v.is_active = true
            then 'active_pipeline'
            when b.has_issued_credits = false
             and v.is_active = false
            then 'stalled_pipeline'
            when b.has_issued_credits = true
            then 'issuing'
            else 'unknown'
        end                                             as pipeline_stage,

        -- geographic concentration flag
        case
            when b.country = 'Indonesia' then true
            else false
        end                                             as is_indonesia,

        -- annual issuance by vintage year (2010-2025)
        b.issued_2010,
        b.issued_2011,
        b.issued_2012,
        b.issued_2013,
        b.issued_2014,
        b.issued_2015,
        b.issued_2016,
        b.issued_2017,
        b.issued_2018,
        b.issued_2019,
        b.issued_2020,
        b.issued_2021,
        b.issued_2022,
        b.issued_2023,
        b.issued_2024,
        b.issued_2025,

        -- recent issuance indicator (2023 onwards)
        b.issued_2023 + b.issued_2024 + b.issued_2025   as issued_2023_2025,

        case
            when b.issued_2023 + b.issued_2024 + b.issued_2025 > 0
            then true
            else false
        end                                             as is_recently_active

    from berkeley b
    left join verra v on b.project_id = v.project_id

)

select * from joined
order by credits_issued desc