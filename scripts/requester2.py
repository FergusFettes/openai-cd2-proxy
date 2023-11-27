import os
import re
import uuid
import asyncio
import signal
import csv
import json
import time
import random
from typing import Optional

import aiohttp
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import numpy as np


async def log_to_csv(logfile, identity, timestamp, duration, status_code):
    # Check if the logfile exists and if not, create it with headers
    file_exists = os.path.isfile(logfile)
    with open(logfile, mode='a', newline='') as file:
        writer = csv.writer(file)
        # If the file didn't exist before this process, write the header
        if not file_exists:
            writer.writerow(['timestamp', 'identity', 'duration', 'status_code'])
            print(f"Created new logfile: {logfile}")
        writer.writerow([timestamp, identity, duration, status_code])


def response_validation(status, response_json, payload, start_time, identity):
    if status == 200:
        # Do the validity check here with "response" and "payload" as needed
        text = response_json["choices"][0]["text"].split("||")[0]
        params = json.loads(response_json["choices"][0]["text"].split("||")[1])
        # Example response validity check
        if text != payload["prompt"] or params["max_tokens"] != payload["max_tokens"]:
            print(
                f"{time.time() - start_time:.2f}s - "
                f"Identity {identity} received invalid response: {text}{params}"
            )
            status = 500
        else:
            print(
                f"{time.time() - start_time:.2f}s - "
                f"Identity {identity} received valid response: {text}{params}"
            )
    else:
        print(
            f"{time.time() - start_time:.2f}s - "
            f"Identity {identity} received error response: {status}"
        )
    return status


class Requester:
    def __init__(self, identity, request_pause, parameters, endpoint_url, logfile, test_api_key_prefix):
        self.identity = identity
        self.request_pause = request_pause
        self.parameters = parameters
        self.endpoint_url = endpoint_url
        self.logfile = logfile
        self.test_api_key_prefix = test_api_key_prefix
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.test_api_key_prefix}{self.identity}"
        }
        self.shutdown_event = asyncio.Event()

    async def make_request(self, session):
        request_payload = {
            "prompt": uuid.uuid4().hex,
            "max_tokens": random.randint(10, 10 + self.parameters - 1)
        }

        start_time = time.time()
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

        try:
            async with session.post(
                self.endpoint_url, json=request_payload, headers=self.headers
            ) as response:
                status = response_validation(
                    response.status,
                    await response.json(),
                    request_payload,
                    start_time,
                    self.identity
                )

        except aiohttp.ClientError as e:
            print(
                f"{time.time() - start_time:.2f}s - "
                f"Request failed for identity {self.identity}: {e}"
            )

        # Calculate duration in all cases
        duration = time.time() - start_time
        await log_to_csv(self.logfile, self.identity, timestamp, duration, status)

    async def wait_random_time(self):
        await asyncio.sleep(random.uniform(
            self.request_pause - 2,
            self.request_pause + 2
        ))

    async def run(self):
        await self.wait_random_time()
        print(f"Identity {self.identity} has been started up.")
        async with aiohttp.ClientSession() as session:
            while not self.shutdown_event.is_set():
                await self.make_request(session)
                await self.wait_random_time()
        print(f"Identity {self.identity} has been shut down.")


class Benchmark:
    def __init__(self, identities, request_pause, parameters, endpoint_url, logfile, test_api_key_prefix):
        self.identities = identities
        self.logfile = logfile
        self.request_pause = request_pause
        self.parameters = parameters
        self.endpoint_url = endpoint_url
        self.test_api_key_prefix = test_api_key_prefix
        self.requesters = [
            Requester(identity, request_pause, parameters, endpoint_url, logfile, test_api_key_prefix)
            for identity in range(identities)
        ]

    def handle_shutdown_signal(self, signum, frame):
        print(f"Received shutdown signal ({signal.strsignal(signum)}). Shutting down.")
        for requester in self.requesters:
            requester.shutdown_event.set()

    def create_tasks(self):
        # Register system signals for graceful termination (optional based on your environment)
        signal.signal(signal.SIGINT, self.handle_shutdown_signal)
        signal.signal(signal.SIGTERM, self.handle_shutdown_signal)

        tasks = []
        for i, requester in enumerate(self.requesters):
            task = asyncio.create_task(self.staggered_start(requester, i))
            tasks.append(task)

        print(f"Starting benchmark with {len(self.requesters)} benchmarks...")
        return tasks

    async def start(self, tasks):
        await asyncio.gather(*tasks)

    async def shutdown_task(self, seconds):
        await asyncio.sleep(seconds)
        for requester in self.requesters:
            requester.shutdown_event.set()

    async def staggered_start(self, requester, index):
        # Wait a bit before starting each requester based on their index
        initial_wait = random.uniform(0, self.request_pause) * index
        await asyncio.sleep(initial_wait)
        await requester.run()

    async def run_benchmark_with_load(self, requests_per_minute, total_duration_minutes=1):
        # Generate combinations of identities and pauses independent of one another
        identity_options = range(1, 11)  # Example: Test from 1 to 10 identities
        pause_options = np.linspace(0.1, 5, 10)  # Example: Test pauses between 0.1 to 5 seconds, inclusive

        # Create a list of tuples containing all possible combinations between identity_options and pause_options
        combinations = [(identity, pause) for identity in identity_options for pause in pause_options]

        # Rest of the function remains the same
        # Create logfiles for each combination, run benchmark, read results, and prepare for heatmap...
        print(f"Running benchmark with {len(combinations)} combinations of {requests_per_minute} requests per minute")
        # all_results = []

        # Create logfiles for each combination
        logfiles = [
            f"{identities}_ids_{pause}_pause_{self.parameters}_params.csv"
            for identities, pause in combinations
        ]

        for (identities, pause), logfile in zip(combinations, logfiles):
            # Setup benchmark with combination
            self.requesters = [
                Requester(identity, pause, self.parameters, self.endpoint_url, logfile, self.test_api_key_prefix)
                for identity in range(identities)
            ]

            # Start the benchmark experiment
            print(f"Running benchmark with {identities} identities and {pause:.2f} second pause...")
            start_time = time.time()

            seconds = total_duration_minutes * 60
            # seconds = 3
            requester_tasks = self.create_tasks()
            shutdown_task = asyncio.create_task(self.shutdown_task(seconds))
            tasks = [*requester_tasks, shutdown_task]

            await asyncio.gather(*tasks)

            end_time = time.time()
            seconds_elapsed = end_time - start_time
            print(f"Finished benchmark run, elapsed time: {seconds_elapsed:.2f}s")

            # # Read results and append to all_results
            # data = pd.read_csv(logfile)
            # all_results.append((identities, pause, data))

        return logfiles

    def create_durations_graph(self):
        # Read the CSV file into a DataFrame
        try:
            data = pd.read_csv(self.logfile)
        except FileNotFoundError:
            print("Log file not found. Make sure to run the benchmark first.")
            return

        # Assume logfile columns are: ['timestamp', 'identity', 'duration', 'status_code']
        data.columns = ['timestamp', 'identity', 'duration', 'status_code']

        # Convert timestamp to datetime for better plotting
        data['timestamp'] = pd.to_datetime(data['timestamp'])

        # Map status codes to a 'success' boolean
        data['success'] = data['status_code'] == 200

        # Create a figure with two subplots
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(20, 5))

        # First subplot: Scatter plot with fixed y-axis range from 0 to 10
        sns.scatterplot(data=data, x='timestamp', y='duration', hue='success', style='success', palette='deep', ax=ax1)
        ax1.set_title('Successes and Duration Over Time')
        ax1.set_xlabel('Time of Request')
        ax1.set_ylabel('Duration (seconds)')
        ax1.set_ylim(0, 10)  # Set the y-axis to range from 0 to 10

        # Second subplot: Box and whisker plot for distribution of durations
        sns.boxplot(data=data, x='success', y='duration', ax=ax2)
        ax2.set_title('Distribution of Durations by Success')
        ax2.set_xlabel('Success')
        ax2.set_ylabel('Duration (seconds)')
        ax2.set_ylim(0, 10)  # Optional: Set the y-axis for boxplot also from 0 to 10

        # Set layout to fit subplots nicely
        plt.tight_layout()

        # Save the plot to a file
        plt.savefig('benchmark_graph.png')
        plt.show()  # Show the plot for interactive environments

    def process_experiment_data(self, logfiles):
        all_results = []

        # Define the headers assuming we know their order
        log_headers = ['timestamp', 'identity', 'duration', 'status_code']

        # Iterate over each logfile
        for logfile in logfiles:
            # Extract identities and pause durations from the filename using regex
            match = re.match(r"(\d+)_ids_(\d+(\.\d+)?|\.\d+)_pause_.*\.csv$", logfile)
            if match:
                identities = int(match.group(1))
                pause = float(match.group(2))
            else:
                print(f"Could not extract metadata from filename: {logfile}")
                continue

            # Read the CSV file into a DataFrame assuming it has no header row
            data = pd.read_csv(logfile, header=None, names=log_headers)

            # Calculate success rate
            total_requests = len(data)
            successful_requests = data[data['status_code'] == '200'].shape[0]
            success_rate = successful_requests / total_requests if total_requests > 0 else 0

            # Append identities, pause, and success rate to the results list
            all_results.append({
                'identities': identities,
                'pause': pause,
                'success_rate': success_rate,
                'logfile': logfile,  # Include the logfile name in case we need to trace back
            })

        # Convert the results to a DataFrame
        results_df = pd.DataFrame(all_results)

        # Pivot the DataFrame to prepare for heatmap
        heatmap_data = results_df.pivot(index='pause', columns='identities', values='success_rate')

        return heatmap_data

    def generate_heatmap(self, heatmap_data):
        # Ensure the heatmap_data is a DataFrame and not None
        if heatmap_data is not None and isinstance(heatmap_data, pd.DataFrame):
            # Plot the heatmap using Seaborn's heatmap function
            plt.figure(figsize=(12, 8))
            sns.heatmap(
                heatmap_data,
                cmap="YlGnBu",
                annot=True,
                cbar_kws={'label': 'Success Rate'},
                fmt=".2f"  # Optional: Format the annotation to two decimal places
            )

            # Customize the plot
            plt.title('Success Rate Heatmap by Identities and Pause Duration')
            plt.xlabel('Number of Identities')
            plt.ylabel('Pause Duration (seconds)')

            # Ensure the plot displays full axes labels and not cutting off the edges
            plt.xticks(rotation=45)
            plt.yticks(rotation=45)
            plt.tight_layout()

            # Save and show the heatmap
            plt.savefig('success_rate_heatmap.png')
            plt.show()
        else:
            print("Invalid or empty heatmap data provided.")


import typer


cli = typer.Typer()


@cli.command()
def main(
    identities: int = typer.Option(10, help="Number of identities to simulate"),
    request_pause: int = typer.Option(1, help="Pause duration between requests"),
    parameters: int = typer.Option(1, help="Variability in max_tokens of the payload"),
    endpoint_url: str = typer.Option(
        "http://localhost:5000/v1/completions",
        help="Endpoint URL to send requests to"
    ),
    logfile: str = typer.Option("benchmark_results.csv", help="File to log the benchmark results"),
    test_api_key_prefix: str = typer.Option("test_api_key_", help="Prefix for the simulated API keys")
):
    """
    Starts the benchmark with the provided options.
    """
    benchmark = Benchmark(identities, request_pause, parameters, endpoint_url, logfile, test_api_key_prefix)

    asyncio.run(benchmark.start())

    # After benchmark is done, create the graph of the results
    benchmark.create_durations_graph()


@cli.command()
def run_load_test(
    requests_per_minute: float = typer.Option(30.0, help="Target number of requests per minute"),
    total_duration_minutes: Optional[int] = typer.Option(1, help="Total minutes to run each test scenario"),
    endpoint_url: str = typer.Option(
        "http://localhost:5000/v1/completions",
        help="Endpoint URL to send requests to"
    ),
    logfile: str = typer.Option("load_test_results.csv", help="File to log the load test results"),
    test_api_key_prefix: str = typer.Option("test_api_key_", help="Prefix for the simulated API keys"),
    parameters: int = typer.Option(1, help="Variability in max_tokens of the payload")
):
    """
    Runs an automated load-testing experiment and generates a heatmap based on the results.
    """
    benchmark = Benchmark(0, 0, parameters, endpoint_url, logfile, test_api_key_prefix)
    # logfiles = asyncio.run(
    #     benchmark.run_benchmark_with_load(requests_per_minute, total_duration_minutes=total_duration_minutes)
    # )
    #
    try:
        # # Logfiles is actually all the csv files in the current dir
        logfiles = [logfile for logfile in os.listdir() if logfile.endswith(".csv")]
        experiment_results = benchmark.process_experiment_data(logfiles)
        benchmark.generate_heatmap(experiment_results)
    except FileNotFoundError:
        typer.echo(f"Log file {logfile} not found. Make sure the test runs before attempting to generate a heatmap.")


if __name__ == "__main__":
    cli()
