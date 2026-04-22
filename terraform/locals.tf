locals {
  name_prefix = "${var.project_name}-${random_id.suffix.hex}"

  silver_db_name    = "te_lake_silver"
  gold_db_name      = "te_lake_gold"
  silver_table_name = "instantaneous_measurements"

  silver_table_location = "s3://${module.storage.silver_bucket_name}/instantaneous/"

  silver_columns = [
    { name = "device_id", type = "bigint" },
    { name = "measured_at", type = "timestamp" },
    { name = "mac_address", type = "string" },
    { name = "voltage_a", type = "double" },
    { name = "voltage_b", type = "double" },
    { name = "voltage_c", type = "double" },
    { name = "voltage_ab", type = "double" },
    { name = "voltage_bc", type = "double" },
    { name = "voltage_ca", type = "double" },
    { name = "current_a", type = "double" },
    { name = "current_b", type = "double" },
    { name = "current_c", type = "double" },
    { name = "active_power_a", type = "double" },
    { name = "active_power_b", type = "double" },
    { name = "active_power_c", type = "double" },
    { name = "threephase_active_power", type = "double" },
    { name = "reactive_power_a", type = "double" },
    { name = "reactive_power_b", type = "double" },
    { name = "reactive_power_c", type = "double" },
    { name = "threephase_reactive_power", type = "double" },
    { name = "apparent_power_a", type = "double" },
    { name = "apparent_power_b", type = "double" },
    { name = "apparent_power_c", type = "double" },
    { name = "threephase_apparent_power", type = "double" },
    { name = "frequency_a", type = "double" },
    { name = "frequency_b", type = "double" },
    { name = "frequency_c", type = "double" },
    { name = "power_factor_a", type = "double" },
    { name = "power_factor_b", type = "double" },
    { name = "power_factor_c", type = "double" },
    { name = "temperature", type = "double" },
    { name = "angle_a", type = "double" },
    { name = "angle_b", type = "double" },
    { name = "angle_c", type = "double" },
    { name = "neutral_current", type = "double" },
    { name = "timezone", type = "int" },
    { name = "daylight_saving_time", type = "int" },
    { name = "measured_date", type = "date" },
    { name = "_ingested_at", type = "timestamp" },
  ]
}
