#!/usr/bin/env python3

import os
import mlflow
from mlflow.tracking import MlflowClient



try:
    # Create client
    client = MlflowClient()
    
    # List experiments
    experiments = client.search_experiments()
    print("Available experiments:")
    for exp in experiments:
        print(f"  - {exp.name} (ID: {exp.experiment_id})")
    
    # Try to search traces
    print("\nSearching for traces...")
    
    # Search traces for each experiment
    for exp in experiments:
        try:
            print(f"\nSearching traces in experiment '{exp.name}' (ID: {exp.experiment_id})...")
            traces = client.search_traces(experiment_ids=[exp.experiment_id])
            print(f"Found {len(traces)} traces in experiment {exp.experiment_id}")
            
            for trace in traces[:3]:  # Show first 3 traces
                print(f"  - Trace ID: {trace.info.request_id}")
                print(f"    Status: {trace.info.status}")
                print(f"    Execution time: {trace.info.execution_time_ms}ms")
                print(f"    Timestamp: {trace.info.timestamp_ms}")
                if trace.data.request:
                    print(f"    Request: {str(trace.data.request)[:100]}...")
                if trace.data.response:
                    print(f"    Response: {str(trace.data.response)[:100]}...")
                print("    ---")
                
        except Exception as e:
            print(f"Error searching traces in experiment {exp.experiment_id}: {e}")

except Exception as e:
    print(f"Error connecting to MLflow: {e}")