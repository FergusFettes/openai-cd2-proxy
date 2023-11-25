from tortoise import fields
from tortoise.models import Model


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
