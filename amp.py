import boto3
import requests
from requests_aws4auth import AWS4Auth
import time
from datetime import datetime, timedelta
import metrics_pb2  # Import the compiled Protobuf module
import snappy
import random


class PrometheusQueryClient:
    def __init__(self, region="us-east-1", workspace_id="ws-4a7839ea-b9ae-4e3c-9407-7c38092449ae"):
        self.region = region
        self.workspace_id = workspace_id
        self.endpoint = f"https://aps-workspaces.{region}.amazonaws.com/workspaces/{workspace_id}/api/v1"
        self.write_endpoint = f"https://aps-workspaces.{region}.amazonaws.com/workspaces/{workspace_id}/api/v1/remote_write"
        self.auth = self._get_aws_auth()

    def _get_aws_auth(self):
        session = boto3.Session()
        credentials = session.get_credentials()
        frozen_creds = credentials.get_frozen_credentials()
        print(credentials.access_key)
        print(credentials.secret_key)
        print(credentials.token)
        # return AWS4Auth(
        #     credentials.access_key,
        #     credentials.secret_key,
        #     self.region,
        #     'aps',
        #     session_token=credentials.token
        # )

        return AWS4Auth(
            frozen_creds.access_key,
            frozen_creds.secret_key,
            self.region,
            'aps',
            session_token=frozen_creds.token
        )

    def query(self, query_expr, start_time=None, end_time=None, step='1m'):
        """
        Query Prometheus metrics
        :param query_expr: PromQL query expression
        :param start_time: Start time for range queries (datetime object)
        :param end_time: End time for range queries (datetime object)
        :param step: Step interval for range queries
        :return: Query results
        """
        # Instant query
        if start_time is None and end_time is None:
            endpoint = f"{self.endpoint}/query"
            params = {'query': query_expr}
        # Range query
        else:
            endpoint = f"{self.endpoint}/query_range"
            start = int(start_time.timestamp()) if start_time else int((datetime.now() - timedelta(days=7)).timestamp())
            end = int(end_time.timestamp()) if end_time else int(datetime.now().timestamp())
            params = {
                'query': query_expr,
                'start': start,
                'end': end,
                'step': step
            }

        response = requests.get(
            endpoint,
            params=params,
            auth=self.auth,
            headers={'Content-Type': 'application/json'}
        )

        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Query failed: {response.status_code} - {response.text}")

    def print_results(self, results):
        """Pretty print the query results"""
        if results['status'] == 'success':
            data = results['data']
            if data['resultType'] == 'vector':
                for result in data['result']:
                    print(f"Metric: {result['metric']}")
                    print(f"Value: {result['value'][1]}\n")
            elif data['resultType'] == 'matrix':
                for result in data['result']:
                    print(f"Metric: {result['metric']}")
                    print("Values:")
                    for value in result['values']:
                        timestamp = datetime.fromtimestamp(value[0])
                        print(f"  {timestamp}: {value[1]}")
                    print()
        else:
            print(f"Query failed: {results['error']}")

    def list_metrics(self):
        """
        Fetches all available metric names from AWS Managed Prometheus.
        """
        endpoint = f"{self.endpoint}/label/__name__/values"

        response = requests.get(
            endpoint,
            auth=self.auth,
            headers={'Content-Type': 'application/json'}
        )

        if response.status_code == 200:
            return response.json().get("data", [])
        else:
            raise Exception(f"Failed to list metrics: {response.status_code} - {response.text}")

    def print_metrics(self):
        """Prints the list of available metrics"""
        try:
            metrics = self.list_metrics()
            print("\nAvailable Metrics:")
            for metric in metrics:
                print(f"- {metric}")
        except Exception as e:
            print(f"Error fetching metrics: {e}")

    def write_metric(self, metric_name, value, labels={}):
        timestamp = int(time.time() * 1000)

        # Create Protobuf WriteRequest
        write_request = metrics_pb2.WriteRequest()
        ts = write_request.timeseries.add()
        ts.labels.add(name="__name__", value=metric_name)

        # Add additional labels
        for k, v in labels.items():
            ts.labels.add(name=k, value=v)

        # Add sample value with timestamp
        ts.samples.add(value=value, timestamp=timestamp)

        # Serialize the request and compress with Snappy
        protobuf_data = write_request.SerializeToString()
        compressed_data = snappy.compress(protobuf_data)

        headers = {
            'Content-Encoding': 'snappy',
            'Content-Type': 'application/x-protobuf'
        }

        # Perform the AWS SigV4 signed request
        response = requests.post(
            self.write_endpoint,
            data=compressed_data,
            auth=self.auth,
            headers=headers
        )

        if response.status_code == 200:
            print(f"✅ Successfully wrote metric: {metric_name}={value}")
        else:
            print(f"❌ Failed to write metric: {response.status_code} - {response.text}")

    def simulate_real_metrics(self):
        metrics = [
            {"name": "cpu_usage", "min": 10, "max": 90, "labels": {"host": "server-1", "region": "us-east-1"}},
            {"name": "memory_usage", "min": 1000, "max": 8000, "labels": {"host": "server-1", "region": "us-east-1"}},
            {"name": "http_requests_total", "min": 0, "max": 500, "labels": {"app": "web-service", "env": "prod"}},
            {"name": "disk_io", "min": 50, "max": 500, "labels": {"disk": "sda", "host": "server-1"}},
            {"name": "network_latency", "min": 1, "max": 100, "labels": {"host": "server-1", "region": "us-east-1"}}
        ]

        while True:
            for metric in metrics:
                value = random.uniform(metric["min"], metric["max"])
                self.write_metric(metric["name"], value, metric["labels"])
            print("Wrote 5 metrics. Sleeping for 30 seconds...\n")
            time.sleep(30)

# Example usage
if __name__ == "__main__":
    # Initialize the client
    client = PrometheusQueryClient()

    client.write_metric(
        metric_name="custom_http_requests_total",
        value=20,
        labels={"app": "my-service", "env": "prod"}
    )

    # Example 1: Instant query
    query_expr = 'sum by (app) (sum_over_time(custom_http_requests_total[7d]))'  # Simple query to check which targets are up
    results = client.query(query_expr)
    print("Instant Query Results:")
    client.print_results(results)

    query_expr = 'custom_http_requests_total{app!=""}[7d]'  # Simple query to check which targets are up
    results = client.query(query_expr)
    print("Instant Query Results:")
    client.print_results(results)

    # Example 2: Range query for the last hour
    # end_time = datetime.now()
    # start_time = end_time - timedelta(days=7)
    # query_expr = 'sum(custom_http_requests_total)'  # Rate of HTTP requests
    # results = client.query(query_expr, start_time, end_time, '1m')
    # print("\nRange Query Results:")
    # client.print_results(results)
    # client.print_metrics()
