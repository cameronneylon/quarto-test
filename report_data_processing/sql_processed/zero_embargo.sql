/*
## Summary
Identifies Zero Embargo Other-platform open

## Description

## Contacts
cameron.neylon@curtin.edu.au

## Requires
table bigquery://academic-observatory.our_research.unpaywall

## Creates
file zero_embargo.csv
*/

WITH first_repo AS (
    SELECT
     doi,
     year,
     published_date,
     (
        SELECT g.oa_date
        FROM UNNEST(u.oa_locations) as g
        WHERE ((g.host_type = "repository") and (g.version IN ('publishedVersion', 'acceptedVersion')) and
            (g.oa_date is not null))
        ORDER BY g.oa_date ASC
        LIMIT 1
         ) as first_repo_date
    FROM `academic-observatory.our_research.unpaywall` as u
    WHERE year > 2015
    ),
  embargos AS (
  SELECT
    doi,
    year,
    DATE_DIFF(published_date, first_repo_date, MONTH) as embargo
  FROM first_repo
    )
SELECT
    year,
    COUNT(DISTINCT IF(embargo < 1, doi, null)) as count_zero_embargo,
    COUNT(DISTINCT IF(embargo < 3, doi, null)) as count_zeroish
FROM embargos GROUP BY year ORDER BY year ASC