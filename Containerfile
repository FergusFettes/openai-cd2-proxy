# Use a base image that includes Python 3 and poetry
FROM python:3.9

# Set the working directory in the container
WORKDIR /app

# Copy the pyproject.toml and poetry.lock into the container
COPY pyproject.toml poetry.lock /app/

# Install poetry dependencies
RUN pip install --upgrade pip
RUN pip install poetry
RUN poetry config virtualenvs.create false
RUN poetry install --no-dev

# Copy the rest of the application code into the container
kCOPY . /app

# Expose ports (replace with the port your apps are running on)
EXPOSE 8000
EXPOSE 5000
