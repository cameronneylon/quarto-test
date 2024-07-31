/*
## Summary
Calculates overall OA figures for global outputs

## Description
Using the DOI table in Academic Observatory calculate various OA parameters by publication year

## Contacts
cameron.neylon@curtin.edu.au

## Requires
table bigquery://academic-observatory.observatory.doi20211211

## Creates
file oa_global_trend.csv
*/

SELECT
  crossref.published_year AS year,
  COUNT(doi) AS total,
  COUNTIF(unpaywall.is_oa IS true) AS open,
  COUNTIF(unpaywall.is_oa IS false) AS closed,
  COUNTIF((unpaywall.gold IS true) OR (unpaywall.bronze IS TRUE)) AS publisher,
  COUNTIF(unpaywall.green IS true) AS other_platform,
  COUNTIF(((unpaywall.gold IS true) OR (unpaywall.bronze IS TRUE))
              AND (unpaywall.green IS FALSE)) AS publisher_only,
  COUNTIF(((unpaywall.gold IS true) OR (unpaywall.bronze IS TRUE))
              AND (unpaywall.green IS TRUE)) AS both,
  COUNTIF(unpaywall.green_only_ignoring_bronze IS true) AS other_platform_only
FROM `academic-observatory.observatory.doi20211211`
WHERE crossref.published_year>2010 AND crossref.published_year<2021 AND unpaywall.is_oa IS NOT NULL
GROUP BY year
ORDER BY year