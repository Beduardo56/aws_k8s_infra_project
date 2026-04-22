"""Bronze -> Silver ETL for the te-lake Iceberg lakehouse.

Reads the last N hours of JSON-gzip records written by Firehose, casts and
deduplicates them, and MERGEs into the Iceberg Silver table. Creates the
table on first run if it does not yet exist.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import boto3
from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    DoubleType,
    IntegerType,
    LongType,
    StringType,
    StructField,
    StructType,
)


def build_schema() -> StructType:
    return StructType(
        [
            StructField("device_id", LongType(), nullable=True),
            StructField("measured_at", StringType(), nullable=True),
            StructField("mac_address", StringType(), nullable=True),
            StructField("voltage_a", DoubleType(), nullable=True),
            StructField("voltage_b", DoubleType(), nullable=True),
            StructField("voltage_c", DoubleType(), nullable=True),
            StructField("voltage_ab", DoubleType(), nullable=True),
            StructField("voltage_bc", DoubleType(), nullable=True),
            StructField("voltage_ca", DoubleType(), nullable=True),
            StructField("current_a", DoubleType(), nullable=True),
            StructField("current_b", DoubleType(), nullable=True),
            StructField("current_c", DoubleType(), nullable=True),
            StructField("active_power_a", DoubleType(), nullable=True),
            StructField("active_power_b", DoubleType(), nullable=True),
            StructField("active_power_c", DoubleType(), nullable=True),
            StructField("threephase_active_power", DoubleType(), nullable=True),
            StructField("reactive_power_a", DoubleType(), nullable=True),
            StructField("reactive_power_b", DoubleType(), nullable=True),
            StructField("reactive_power_c", DoubleType(), nullable=True),
            StructField("threephase_reactive_power", DoubleType(), nullable=True),
            StructField("apparent_power_a", DoubleType(), nullable=True),
            StructField("apparent_power_b", DoubleType(), nullable=True),
            StructField("apparent_power_c", DoubleType(), nullable=True),
            StructField("threephase_apparent_power", DoubleType(), nullable=True),
            StructField("frequency_a", DoubleType(), nullable=True),
            StructField("frequency_b", DoubleType(), nullable=True),
            StructField("frequency_c", DoubleType(), nullable=True),
            StructField("power_factor_a", DoubleType(), nullable=True),
            StructField("power_factor_b", DoubleType(), nullable=True),
            StructField("power_factor_c", DoubleType(), nullable=True),
            StructField("temperature", DoubleType(), nullable=True),
            StructField("angle_a", DoubleType(), nullable=True),
            StructField("angle_b", DoubleType(), nullable=True),
            StructField("angle_c", DoubleType(), nullable=True),
            StructField("neutral_current", DoubleType(), nullable=True),
            StructField("timezone", IntegerType(), nullable=True),
            StructField("daylight_saving_time", IntegerType(), nullable=True),
        ]
    )


def existing_hour_paths(bronze_path: str, watermark_hours: int) -> list[str]:
    """Return only the hour-prefixes that actually contain objects in S3.

    Firehose only creates the path prefix when it flushes the first batch for
    that hour. On first deployment (before any producer run) none exist; on a
    typical run only a subset of the watermark window exists. Spark will fail
    with PATH_NOT_FOUND if any passed path does not exist, even with
    `ignoreMissingFiles = true`, so we filter down to real prefixes first.
    """
    parsed = urlparse(bronze_path)
    bucket = parsed.netloc
    prefix_root = parsed.path.lstrip("/").rstrip("/")

    s3 = boto3.client("s3")
    now = datetime.now(timezone.utc)
    start = now - timedelta(hours=watermark_hours)

    paths: list[str] = []
    for h in range(watermark_hours + 2):
        ts = start + timedelta(hours=h)
        key_prefix = (
            f"{prefix_root}/year={ts.strftime('%Y')}"
            f"/month={ts.strftime('%m')}"
            f"/day={ts.strftime('%d')}"
            f"/hour={ts.strftime('%H')}/"
        )
        resp = s3.list_objects_v2(Bucket=bucket, Prefix=key_prefix, MaxKeys=1)
        if resp.get("KeyCount", 0) > 0:
            paths.append(f"s3://{bucket}/{key_prefix}")
    return paths


def read_bronze(spark: SparkSession, bronze_path: str, watermark_hours: int) -> DataFrame:
    paths = existing_hour_paths(bronze_path, watermark_hours)
    if not paths:
        return spark.createDataFrame([], build_schema())
    return (
        spark.read.schema(build_schema())
        .option("mode", "PERMISSIVE")
        .option("recursiveFileLookup", "false")
        .option("ignoreMissingFiles", "true")
        .option("ignoreCorruptFiles", "true")
        .json(paths)
    )


def transform(df: DataFrame) -> DataFrame:
    return (
        df.filter(F.col("device_id").isNotNull() & F.col("measured_at").isNotNull())
        .withColumn("measured_at", F.to_timestamp("measured_at"))
        .filter(F.col("measured_at").isNotNull())
        .withColumn("measured_date", F.to_date("measured_at"))
        .withColumn("_ingested_at", F.current_timestamp())
        .dropDuplicates(["device_id", "measured_at"])
    )


def ensure_table(spark: SparkSession, full_table: str, warehouse_location: str) -> None:
    spark.sql(
        f"""
        CREATE TABLE IF NOT EXISTS {full_table} (
            device_id BIGINT,
            measured_at TIMESTAMP,
            mac_address STRING,
            voltage_a DOUBLE, voltage_b DOUBLE, voltage_c DOUBLE,
            voltage_ab DOUBLE, voltage_bc DOUBLE, voltage_ca DOUBLE,
            current_a DOUBLE, current_b DOUBLE, current_c DOUBLE,
            active_power_a DOUBLE, active_power_b DOUBLE, active_power_c DOUBLE,
            threephase_active_power DOUBLE,
            reactive_power_a DOUBLE, reactive_power_b DOUBLE, reactive_power_c DOUBLE,
            threephase_reactive_power DOUBLE,
            apparent_power_a DOUBLE, apparent_power_b DOUBLE, apparent_power_c DOUBLE,
            threephase_apparent_power DOUBLE,
            frequency_a DOUBLE, frequency_b DOUBLE, frequency_c DOUBLE,
            power_factor_a DOUBLE, power_factor_b DOUBLE, power_factor_c DOUBLE,
            temperature DOUBLE,
            angle_a DOUBLE, angle_b DOUBLE, angle_c DOUBLE,
            neutral_current DOUBLE,
            timezone INT, daylight_saving_time INT,
            measured_date DATE,
            _ingested_at TIMESTAMP
        )
        USING iceberg
        PARTITIONED BY (measured_date, bucket(8, device_id))
        LOCATION '{warehouse_location}'
        TBLPROPERTIES (
            'format-version' = '2',
            'write.format.default' = 'parquet',
            'write.parquet.compression-codec' = 'zstd'
        )
        """
    )


def merge_into_silver(spark: SparkSession, source: DataFrame, full_table: str) -> None:
    source.createOrReplaceTempView("bronze_batch")
    spark.sql(
        f"""
        MERGE INTO {full_table} t
        USING bronze_batch s
        ON t.device_id = s.device_id AND t.measured_at = s.measured_at
        WHEN NOT MATCHED THEN INSERT *
        """
    )


def main() -> None:
    args = getResolvedOptions(
        sys.argv,
        [
            "JOB_NAME",
            "bronze_path",
            "silver_table",
            "silver_warehouse_location",
            "watermark_hours",
        ],
    )

    sc = SparkContext()
    glue_context = GlueContext(sc)
    spark = glue_context.spark_session
    logger = glue_context.get_logger()

    job = Job(glue_context)
    job.init(args["JOB_NAME"], args)

    full_table = args["silver_table"]
    warehouse_location = args["silver_warehouse_location"]
    watermark_hours = int(args["watermark_hours"])

    ensure_table(spark, full_table, warehouse_location)

    bronze = read_bronze(spark, args["bronze_path"], watermark_hours)
    read_count = bronze.count()
    logger.info(f"Bronze records read in {watermark_hours}h window: {read_count}")

    if read_count == 0:
        logger.warn("No Bronze records found; exiting successfully.")
        job.commit()
        return

    silver = transform(bronze)
    candidate_count = silver.count()
    logger.info(f"Records passing transform filter: {candidate_count}")

    merge_into_silver(spark, silver, full_table)
    logger.info(f"MERGE into {full_table} complete.")

    job.commit()


if __name__ == "__main__":
    main()
