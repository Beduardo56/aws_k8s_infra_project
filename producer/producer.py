"""Local producer: simulates N energy meters, PUTs InstantaneousData to Firehose."""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator

import boto3
from botocore.exceptions import ClientError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fake_data_generator import DeviceConfig, InstantaneousGenerator  # noqa: E402

LOG = logging.getLogger("producer")
FIREHOSE_MAX_BATCH = 500


def build_devices(n: int) -> list[DeviceConfig]:
    return [
        DeviceConfig(
            device_id=1000 + i,
            mac_address=f"aa:bb:cc:dd:ee:{i:02x}",
            serial=f"TE{1000 + i}",
        )
        for i in range(n)
    ]


def iter_records(
    generators: list[InstantaneousGenerator], measured_at: datetime
) -> Iterator[dict]:
    for gen in generators:
        yield gen.generate(measured_at).to_dict()


def chunked(it: Iterable[dict], size: int) -> Iterator[list[dict]]:
    batch: list[dict] = []
    for item in it:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def put_batch(firehose, stream: str, records: list[dict]) -> int:
    payload = [{"Data": (json.dumps(r, default=str) + "\n").encode("utf-8")} for r in records]
    resp = firehose.put_record_batch(DeliveryStreamName=stream, Records=payload)
    failed = resp.get("FailedPutCount", 0)
    if failed:
        LOG.warning("Firehose reported %d failed records out of %d", failed, len(records))
    return len(records) - failed


def main() -> int:
    p = argparse.ArgumentParser(description="Simulate IoT energy meters and push to Firehose.")
    p.add_argument("--devices", type=int, default=10, help="Number of simulated devices")
    p.add_argument("--duration-min", type=int, default=60, help="How long to run (minutes)")
    p.add_argument("--stream-name", required=True, help="Firehose delivery stream name")
    p.add_argument("--region", default="us-east-1")
    p.add_argument("--profile", default="te-lake-producer", help="AWS CLI profile to use")
    p.add_argument("--tick-seconds", type=int, default=60, help="Seconds between ticks")
    p.add_argument("--log-level", default="INFO")
    args = p.parse_args()

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s %(levelname)s %(name)s | %(message)s",
    )

    session = boto3.Session(profile_name=args.profile, region_name=args.region)
    firehose = session.client("firehose")

    devices = build_devices(args.devices)
    generators = [InstantaneousGenerator(d) for d in devices]
    LOG.info("Configured %d devices on stream %s (region=%s)", len(devices), args.stream_name, args.region)

    end = time.monotonic() + args.duration_min * 60
    tick = 0
    total = 0

    while time.monotonic() < end:
        tick += 1
        measured_at = datetime.now(timezone.utc)
        sent = 0
        try:
            for batch in chunked(iter_records(generators, measured_at), FIREHOSE_MAX_BATCH):
                sent += put_batch(firehose, args.stream_name, batch)
        except ClientError as e:
            LOG.error("Firehose error on tick %d: %s", tick, e)
        total += sent
        LOG.info("tick=%d measured_at=%s sent=%d total=%d", tick, measured_at.isoformat(), sent, total)

        remaining = end - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(args.tick_seconds, remaining))

    LOG.info("Done. total_records=%d ticks=%d", total, tick)
    return 0


if __name__ == "__main__":
    sys.exit(main())
