/*
  stg_berkeley.sql
  ────────────────
  Staging model for the Berkeley Voluntary Registry Offsets Database (VROD).
  Source: gspp.berkeley.edu — Voluntary-Registry-Offsets-Database v2026-02.xlsx
  Grain: one row per project (all registries)
  Filter: VCS registry only for this pipeline
*/

with source as (

    select * from st_read(
        '{{ env_var("BERKELEY_RAW_PATH") }}',
        layer = 'PROJECTS',
        open_options = ['HEADERS=FORCE', 'AUTODETECT_TYPE=NO']
    )

),

vcs_only as (

    select *
    from source
    where "Voluntary Registry" = 'VCS'

),

renamed as (

    select
        -- keys
        "Project ID"                                          as berkeley_project_id,

        -- extract numeric ID to join with Verra (VCS1234 → 1234)
        cast(
            regexp_replace("Project ID", '[^0-9]', '', 'g')
            as integer
        )                                                     as project_id,

        -- project metadata
        "Project Name"                                        as project_name,
        "Voluntary Registry"                                  as registry,
        "Voluntary Status"                                    as berkeley_status,
        "Scope"                                               as scope,
        "Type"                                                as project_type,
        "Reduction / Removal"                                 as reduction_or_removal,
        "Methodology / Protocol"                              as methodology,
        "Country"                                             as country,
        "Region"                                              as region,
        "Project Developer"                                   as project_developer,
        "First Year of Project (Vintage)"                     as first_vintage_year,

        -- credit volumes (core metrics)
        coalesce(cast("Total Credits \nIssued"    as double), 0) as credits_issued,
        coalesce(cast("Total Credits \nRetired"   as double), 0) as credits_retired,
        coalesce(cast("Total Credits Remaining"   as double), 0) as credits_remaining,
        coalesce(cast("Total Buffer \nPool Deposits" as double), 0) as buffer_pool_deposits,

        -- derived credit metrics
        case
            when cast("Total Credits \nIssued" as double) > 0
            then round(
                cast("Total Credits \nRetired" as double) /
                cast("Total Credits \nIssued" as double) * 100,
                1
            )
            else null
        end                                                    as retirement_rate_pct,

        case
            when coalesce(cast("Total Credits \nIssued" as double), 0) > 0
            then true
            else false
        end                                                    as has_issued_credits,

        -- annual vintage issuances 2010-2025
        coalesce(cast("2010" as double), 0)  as issued_2010,
        coalesce(cast("2011" as double), 0)  as issued_2011,
        coalesce(cast("2012" as double), 0)  as issued_2012,
        coalesce(cast("2013" as double), 0)  as issued_2013,
        coalesce(cast("2014" as double), 0)  as issued_2014,
        coalesce(cast("2015" as double), 0)  as issued_2015,
        coalesce(cast("2016" as double), 0)  as issued_2016,
        coalesce(cast("2017" as double), 0)  as issued_2017,
        coalesce(cast("2018" as double), 0)  as issued_2018,
        coalesce(cast("2019" as double), 0)  as issued_2019,
        coalesce(cast("2020" as double), 0)  as issued_2020,
        coalesce(cast("2021" as double), 0)  as issued_2021,
        coalesce(cast("2022" as double), 0)  as issued_2022,
        coalesce(cast("2023" as double), 0)  as issued_2023,
        coalesce(cast("2024" as double), 0)  as issued_2024,
        coalesce(cast("2025" as double), 0)  as issued_2025

    from vcs_only

)

select * from renamed