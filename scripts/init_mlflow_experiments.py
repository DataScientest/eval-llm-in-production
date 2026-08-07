#!/usr/bin/env python3
"""
MLflow experiment initialization script.
Ensures required experiments exist before services start.
"""

import os
import time
import mlflow
from mlflow.tracking import MlflowClient
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def wait_for_mlflow(max_retries=30, delay=2):
    """Wait for MLflow server to be available."""
    mlflow_uri = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
    mlflow.set_tracking_uri(mlflow_uri)
    
    for attempt in range(max_retries):
        try:
            client = MlflowClient()
            # Try to list experiments to test connectivity
            client.search_experiments()
            logger.info(f"✅ MLflow server is available at {mlflow_uri}")
            return client
        except Exception as e:
            if attempt < max_retries - 1:
                logger.info(f"⏳ Waiting for MLflow server... (attempt {attempt + 1}/{max_retries})")
                time.sleep(delay)
            else:
                logger.error(f"❌ Failed to connect to MLflow after {max_retries} attempts: {e}")
                raise

def create_experiment_if_not_exists(client, experiment_name):
    """Create experiment if it doesn't exist."""
    try:
        # Try to get existing experiment
        experiment = mlflow.get_experiment_by_name(experiment_name)
        if experiment:
            logger.info(f"✅ Experiment '{experiment_name}' already exists (ID: {experiment.experiment_id})")
            return experiment.experiment_id
    except Exception:
        pass
    
    # Create new experiment
    try:
        experiment_id = mlflow.create_experiment(experiment_name)
        logger.info(f"🆕 Created experiment '{experiment_name}' (ID: {experiment_id})")
        return experiment_id
    except Exception as e:
        logger.error(f"❌ Failed to create experiment '{experiment_name}': {e}")
        raise

def main():
    """Initialize required MLflow experiments."""
    logger.info("🚀 Initializing MLflow experiments...")
    
    # Wait for MLflow server
    client = wait_for_mlflow()
    
    # Define required experiments
    experiments = [
        "llmops-security",           # For API calls
        "llmops-litellm-security"    # For direct LiteLLM proxy calls
    ]
    
    # Create experiments
    created_experiments = {}
    for exp_name in experiments:
        exp_id = create_experiment_if_not_exists(client, exp_name)
        created_experiments[exp_name] = exp_id
    
    # Verify all experiments exist
    logger.info("📋 Verifying experiments:")
    all_experiments = client.search_experiments()
    for exp in all_experiments:
        logger.info(f"   - {exp.name} (ID: {exp.experiment_id})")
    
    logger.info("✅ MLflow experiments initialization complete!")
    return created_experiments

if __name__ == "__main__":
    main()