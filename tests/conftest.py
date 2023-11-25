import pytest
from datetime import datetime, timedelta

from tortoise import Tortoise

from openai_proxy.models import init_db, Usage, APIKey
import openai_proxy.models as model_module


@pytest.fixture(scope="module")
async def db():
    # Initialize the in-memory database for tests
    await init_db(db_url='sqlite://:memory:', modules=model_module)
    yield
    # Teardown the in-memory database
    await Tortoise.close_connections()


@pytest.fixture(scope="module")
async def test_data(db):
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


@pytest.fixture(scope="function")
async def clean_up(db):
    # Clean up the data after every test function
    await Usage.all().delete()
    await APIKey.all().delete()
