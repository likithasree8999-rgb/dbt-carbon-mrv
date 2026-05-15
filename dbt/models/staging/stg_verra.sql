/*
  stg_verra.sql
  ─────────────
  Staging model for the Verra VCS Project Registry.
  Source: registry.verra.org — allprojects.csv
  Grain: one row per Verra project (project_id)
*/

with source as (

    select * from read_csv_auto(
        '{{ env_var("VERRA_RAW_PATH") }}',
        header = true,
        ignore_errors = true
    )

),

renamed as (

    select
        -- keys
        cast("ID" as integer)                          as project_id,
        "Name"                                         as project_name,
        "Proponent"                                    as proponent,

        -- classification
        "Project Type"                                 as project_type,
        "AFOLU Activities"                             as afolu_activities,
        "Methodology"                                  as methodology,

        -- status
        "Status"                                       as verra_status,

        -- geography
        "Country/Area"                                 as country,
        "Region"                                       as region,

        -- financials
        cast(
            replace("Estimated Annual Emission Reductions", ',', '')
            as double
        )                                              as est_annual_reductions_tco2e,

        -- dates
        cast("Project Registration Date" as date)      as registration_date,
        cast("Crediting Period Start Date" as date)    as crediting_start_date,
        cast("Crediting Period End Date" as date)      as crediting_end_date,

        -- derived flags
        case
            when "AFOLU Activities" ilike '%WRC%' then true
            else false
        end                                            as is_blue_carbon,

        case
            when "Status" in (
                'Registered',
                'Verification approval requested',
                'Registration and verification approval requested',
                'Crediting Period Renewal Requested'
            ) then true
            else false
        end                                            as is_active,

        case
            when "Status" in ('Withdrawn', 'Rejected by Administrator',
                              'Registration request denied',
                              'Registration and verification approval request denied')
            then true
            else false
        end                                            as is_failed,

        -- crediting period length
        datediff(
            'day',
            cast("Crediting Period Start Date" as date),
            cast("Crediting Period End Date" as date)
        ) / 365.25                                     as crediting_period_years

    from source
    where "ID" is not null

)

select * from renamed