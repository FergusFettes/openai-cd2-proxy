from datetime import datetime, timedelta
import uuid
from tortoise import Tortoise, fields
from tortoise.models import Model
from tortoise import functions


class APIKey(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=255, unique=True)
    api_key = fields.CharField(max_length=255, unique=True, index=True)
    leaderboard = fields.BooleanField(default=True)


class Usage(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=255, index=True)
    time = fields.FloatField()
    tokens = fields.IntField()
    type = fields.CharField(max_length=255, index=True)


async def init_db(db_url='sqlite://data.sqlite'):
    await Tortoise.init(
        db_url=db_url,
        modules={'models': ['__main__']}
    )
    await Tortoise.generate_schemas()


import typer
import asyncio
import functools

cli = typer.Typer()


def with_db(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        asyncio.run(db_task(func, *args, **kwargs))
    return wrapper


async def db_task(func, *args, **kwargs):
    await init_db()
    try:
        await func(*args, **kwargs)
    finally:
        await Tortoise.close_connections()


# Function to calculate total token usage for a given name
async def get_total_usage(name: str):
    total = await Usage.filter(name=name).annotate(total=functions.Sum('tokens')).values('total')
    return total[0].get('total')


# Function to calculate usage per given timeframe for a given name
async def get_usage_per_timeframe(name: str, timeframe: str):
    now = datetime.utcnow()
    if timeframe == 'day':
        start_time = now - timedelta(days=1)
    elif timeframe == 'week':
        start_time = now - timedelta(weeks=1)
    elif timeframe == 'hour':
        start_time = now - timedelta(hours=1)
    elif timeframe == 'minute':
        start_time = now - timedelta(minutes=1)
    else:
        raise ValueError('Invalid timeframe provided.')

    total = await (
        Usage
        .filter(name=name, time__gte=start_time.timestamp())
        .annotate(total=functions.Sum('tokens')).values('total')
    )
    return total[0].get('total')


@cli.command()
@with_db
async def add_key(name: str, key: str = None):
    api_key = key or str(uuid.uuid4())
    try:
        await APIKey.create(name=name, api_key=api_key)
        typer.echo(f"Added key for {name}: {api_key}")
    except Exception:
        typer.echo(f"Key for {name} already exists")


@cli.command()
@with_db
async def update_key(name: str):
    api_key = str(uuid.uuid4())
    key_info = await APIKey.filter(name=name).first()
    if key_info:
        key_info.api_key = api_key
        await key_info.save()
        typer.echo(f"Updated key for {name}: {api_key}")
    else:
        typer.echo(f"Key for {name} does not exist")


@cli.command()
@with_db
async def delete_key(name: str):
    key_info = await APIKey.filter(name=name).first()
    if key_info:
        await key_info.delete()
        typer.echo(f"Deleted key for {name}")
    else:
        typer.echo(f"Key for {name} does not exist")


@cli.command()
@with_db
async def list_keys():
    keys = await APIKey.all()
    for key in keys:
        typer.echo(f"{key.name}: {key.api_key}")


@cli.command()
@with_db
async def usage():
    usages = await Usage.all()
    for usage in usages:
        typer.echo(f"{usage.name}: {usage.time}")


# CLI command to get total usage
@cli.command()
@with_db
async def total_usage(name: str):
    total = await get_total_usage(name)
    typer.echo(f"Total tokens used by {name}: {total}")


# CLI command to get usage per timeframe
@cli.command()
@with_db
async def usage_per_timeframe(name: str, timeframe: str = "day"):
    timeframe = timeframe.lower()
    valid_timeframes = ["day", "week", "hour", "minute"]
    if timeframe not in valid_timeframes:
        typer.echo(f"Invalid timeframe. Choose from {valid_timeframes}.")
        raise typer.Abort()
    total = await get_usage_per_timeframe(name, timeframe)
    typer.echo(f"Tokens used by {name} per {timeframe}: {total}")


if __name__ == "__main__":
    cli()
