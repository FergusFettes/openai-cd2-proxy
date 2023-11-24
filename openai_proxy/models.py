import uuid
from tortoise import Tortoise, fields
from tortoise.models import Model


class APIKey(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=255, unique=True)
    api_key = fields.CharField(max_length=255, unique=True, index=True)


class Usage(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=255, index=True)
    time = fields.FloatField()


async def init_db():
    await Tortoise.init(
        db_url='sqlite://data.sqlite',
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


if __name__ == "__main__":
    cli()
