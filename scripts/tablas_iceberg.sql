USE nessie.main;


CREATE TABLE dim_date AS
SELECT *
FROM "minio_files"."lakehouse"."dimensions"."dim_date.csv";


CREATE TABLE dim_event AS
SELECT *
FROM "minio_files"."lakehouse"."dimensions"."dim_event.csv";


CREATE TABLE fact_sp500 AS
SELECT *
FROM "minio_files"."lakehouse"."dimensions"."fact_sp500.csv";