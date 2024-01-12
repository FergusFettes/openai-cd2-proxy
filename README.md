# Openai Proxy

# Quickstart

Use Make to install just:
```
make
```

Use Just to install:
```
just
```

There are convenience functions in just, for example:

```
just run    # This runs the server
just mock   # This runs the mock server which will respond to queries with the parameters and a bunch of 'a's
just add    # This adds a new user to the database with a key
just test   # This sends a test request which will be authenticated with the key, routed to the mock server, and returned.
```

You can also look at these convenience functions to see how to use the server.

For example, `just add` is:

```
poetry run proxy add-key --key test_api_key USERNAME
```

if you want to see what other commands are available, run

```
poetry run proxy --help
```

These commands are for checking out usage.

# Leaderboard and Usage

Admins can check usage with

```
poetry run proxy total-usage USERNAME
$ Total tokens used by USERNAME: 3499
```

And users can check their usage simply by getting 
```
curl -X GET http://localhost:5000/v1/leaderboard_toggle \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test_api_key"
$ 3499
```

There is also an endpoint for leaderboard info, and users can control whether they are visible to the public leaderboard with the leaderbaord_toggle endpoint.
