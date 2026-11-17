from datetime import timedelta

from feast import Entity, FeatureView, Field, FileSource
from feast.types import Int64, Float64

origin_entity = Entity(
    name="origin_account",
    join_keys=["nameOrig"],
    description="PaySim originating account"
)

destination_entity = Entity(
    name="destination_account",
    join_keys=["nameDest"],
    description="PaySim receiving account"
)

origin_source = FileSource(
    name="origin_account_file",
    path='/content/drive/MyDrive/Madhusudan_Kumar_Singh_Capstone_Projects/AIML-01/feast_repo/data/origin_account_history.parquet',
    timestamp_field="event_timestamp"
)

destination_source = FileSource(
    name="destination_account_file",
    path='/content/drive/MyDrive/Madhusudan_Kumar_Singh_Capstone_Projects/AIML-01/feast_repo/data/destination_account_history.parquet',
    timestamp_field="event_timestamp"
)

origin_account_history = FeatureView(
    name="origin_account_history",
    entities=[origin_entity],
    ttl=timedelta(days=365),
    schema=[
        Field(name="origin_previous_count", dtype=Int64),
        Field(name="origin_previous_total", dtype=Float64),
        Field(name="origin_previous_mean", dtype=Float64),
        Field(name="origin_hours_since_previous", dtype=Int64),
    ],
    source=origin_source,
    online=True,
    description="Origin account history from earlier hours only"
)

destination_account_history = FeatureView(
    name="destination_account_history",
    entities=[destination_entity],
    ttl=timedelta(days=365),
    schema=[
        Field(name="destination_previous_count", dtype=Int64),
        Field(name="destination_previous_total", dtype=Float64),
        Field(name="destination_previous_mean", dtype=Float64),
        Field(name="destination_hours_since_previous", dtype=Int64),
    ],
    source=destination_source,
    online=True,
    description="Destination account history from earlier hours only"
)
