from datetime import datetime, timedelta
import uuid
import asyncio
import functools

from tortoise import Tortoise
from tortoise import functions
import typer

from openai_proxy.models import APIKey, Usage


cli = typer.Typer()


async def init_db(db_url='sqlite://data.sqlite'):
    await Tortoise.init(
        db_url=db_url,
        modules={'models': ['openai_proxy.models']}
    )
    await Tortoise.generate_schemas()


def with_db(db_url='sqlite://data.sqlite'):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            asyncio.run(db_task(func, db_url, *args, **kwargs))
        return wrapper
    return decorator


async def db_task(func, db_url, *args, **kwargs):
    await init_db(db_url)  # Use db_url in init_db
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


if __name__ == "__main__":
    cli()
