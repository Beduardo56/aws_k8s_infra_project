# Producer — local IoT simulator

Reuses `../fake_data_generator` to simulate N energy meters and push
`InstantaneousData` JSON records to the Firehose delivery stream
provisioned by Terraform.

## One-time setup

```bash
# From the repo root
python -m venv .venv
source .venv/bin/activate
pip install -r producer/requirements.txt

# Configure the dedicated IAM profile with the access key emitted by Terraform.
# The key is NOT printed to stdout by `terraform apply` — use `terraform output`:
terraform -chdir=terraform output -raw producer_access_key_id
terraform -chdir=terraform output -raw producer_secret_access_key

# Then:
aws configure --profile te-lake-producer
#   AWS Access Key ID     : <paste the access key id>
#   AWS Secret Access Key : <paste the secret>
#   Default region        : us-east-1
#   Default output format : json
```

## Running

Terraform conveniently emits a copy-paste command:

```bash
terraform -chdir=terraform output -raw run_producer_command
```

Or run directly:

```bash
python producer/producer.py \
  --stream-name <output:firehose_stream_name> \
  --region us-east-1 \
  --devices 10 \
  --duration-min 60 \
  --profile te-lake-producer
```

Each tick (every `--tick-seconds`, default 60) the producer generates
one `InstantaneousData` record per device and sends them in batches
(≤ 500 per batch — Firehose hard limit).

## Flags

| Flag | Default | Meaning |
|------|---------|---------|
| `--devices` | 10 | Number of simulated meters |
| `--duration-min` | 60 | How long the producer runs |
| `--stream-name` | *(required)* | Firehose delivery-stream name |
| `--region` | `us-east-1` | AWS region |
| `--profile` | `te-lake-producer` | Local AWS profile to use |
| `--tick-seconds` | 60 | Seconds between batches |
| `--log-level` | `INFO` | Python logging level |

## Verify delivery

```bash
aws s3 ls s3://$(terraform -chdir=terraform output -raw landing_bucket)/instantaneous/ \
  --recursive --human-readable
```

Records appear within ~5 minutes (Firehose 300 s buffer interval).
