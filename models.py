from peewee import Model, SqliteDatabase, CharField, FloatField
import uuid

db = SqliteDatabase('data.sqlite')


class BaseModel(Model):
    class Meta:
        database = db


class APIKey(BaseModel):
    name = CharField(unique=True)
    api_key = CharField(default=lambda: str(uuid.uuid4()), unique=True, index=True)


class Usage(BaseModel):
    name = CharField(index=True)
    time = FloatField()


# Create tables
db.connect()
db.create_tables([APIKey, Usage])
