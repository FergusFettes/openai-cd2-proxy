from datetime import datetime, timedelta
import pytest

from openai_proxy.models import get_total_usage, get_usage_per_timeframe, Usage


@pytest.mark.asyncio
async def test_db_init(db):
    # Check if the database is initialized correctly
    assert await Usage.all().count() == 0, "Database should be empty after initialization"


@pytest.mark.asyncio
async def test_get_usage_single_record(test_data):
    # Prepare: create a single usage record for user2 on a specific day
    usage_record = Usage(
        name="user2",
        time=(datetime.utcnow() - timedelta(days=1)).timestamp(),
        tokens=30,
        type='typeA'
    )
    await usage_record.save()

    # Execute: retrieve the usage record for user2 for the last day
    usage_user_2_day = await get_usage_per_timeframe('user2', 'day')

    # Assert: check if the usage is as expected
    assert usage_user_2_day == 30, "Usage for user2 per day should be 30 tokens"


@pytest.mark.asyncio
async def test_get_total_usage(test_data):
    total_usage_user_1 = await get_total_usage('user1')
    # Assuming user1 has the same amount of tokens each day for simplicity
    assert total_usage_user_1 == sum([10 + i * 10 for i in range(7)]), \
        "Total usage for user1 should be the sum of tokens for 7 days"


@pytest.mark.asyncio
async def test_get_usage_per_timeframe_day(test_data):
    usage_user_2_day = await get_usage_per_timeframe('user2', 'day')
    # Assuming today user2 used (7*10 + 1) tokens, because it's the last day in the range
    assert usage_user_2_day == 71, "Usage for user2v per day should be 71 tokens"
