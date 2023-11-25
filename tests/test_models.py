from datetime import datetime, timedelta

import pytest
from tortoise import Tortoise

from openai_proxy import get_total_usage, get_usage_per_timeframe, Usage, APIKey, init_db, with_db


@pytest.mark.asyncio
async def test_db_init():
    # Check if the database is initialized correctly
    await init_db(db_url='sqlite://:memory:')
    assert await Usage.all().count() == 0, "Database should be empty after initialization"
    await Tortoise.close_connections()


@pytest.mark.asyncio
@with_db(db_url='sqlite://:memory:')
async def test_db_init_fixture():
    # Check if the database is initialized correctly
    assert await Usage.all().count() == 0, "Database should be empty after initialization"


@pytest.mark.asyncio
@with_db(db_url='sqlite://:memory:')
async def test_get_usage_single_record():
    # Prepare: create a single usage record for user2 on a specific day
    usage_record = Usage(
        name="user2",
        time=(datetime.utcnow() - timedelta(days=1)).timestamp(),
        tokens=30,
        type='typeA'
    )
    await usage_record.save()

    # Execute: retrieve the usage record for user2 for the last day
    usage_user_2_day = await get_total_usage('user2')

    # Assert: check if the usage is as expected
    assert usage_user_2_day == 30, "Usage for user2 per day should be 30 tokens"


async def data():
    # This fixture depends on the db fixture to ensure it is loaded first
    names = ["user1", "user2", "user3"]
    now = datetime.utcnow()
    data = []

    # Create data spans over a week with simple numbers for easy manual checking
    for i in range(7):
        day = now - timedelta(days=i)
        for j, name in enumerate(names):
            # Adjust token numbers to be distinctive and attributable to a specific day/user
            tokens = (i + 1) * 10 + j
            data.append(
                Usage(
                    name=name,
                    time=day.timestamp(),
                    tokens=tokens,
                    type='typeA' if j % 2 == 0 else 'typeB'
                )
            )

    # Save all entries to the database in one go
    await Usage.bulk_create(data)

    # API keys for the three users
    api_keys = [APIKey(name=name, api_key=f'apikey-{name}') for name in names]
    await APIKey.bulk_create(api_keys)

    return data


@pytest.mark.asyncio
@with_db(db_url='sqlite://:memory:')
async def test_get_total_usage():
    await data()
    total_usage_user_1 = await get_total_usage('user1')
    # Assuming user1 has the same amount of tokens each day for simplicity
    assert total_usage_user_1 == sum([10 + i * 10 for i in range(7)]), \
        "Total usage for user1 should be the sum of tokens for 7 days"
