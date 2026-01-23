"""MLflow service for experiment tracking and security monitoring."""

import asyncio
import json
import os
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import mlflow
from config.settings import settings
from mlflow.entities.span import SpanType
from mlflow.entities.span_event import SpanEvent


class MLflowService:
    """MLflow service for managing experiments and tracking."""

    def __init__(self):
        self.experiment_id: Optional[str] = None
        self.experiment_name: str = "llmops-security"
        self.tracking_uri = settings.MLFLOW_TRACKING_URI

    async def setup_experiment(self):
        """Setup MLflow experiment."""
        # Initialize MLflow tracking
        mlflow.set_tracking_uri(self.tracking_uri)

        # Set the security experiment for API calls (should already exist from init)
        try:
            mlflow.set_experiment(self.experiment_name)
            print(f"✅ Using MLflow experiment: {self.experiment_name}")
        except Exception as e:
            print(f"⚠️ Warning: Could not set MLflow experiment: {e}")
            # Fallback - try to create it
            try:
                mlflow.create_experiment(self.experiment_name)
                mlflow.set_experiment(self.experiment_name)
                print(f"🆕 Created and set MLflow experiment: {self.experiment_name}")
            except Exception as create_error:
                print(f"❌ Failed to create experiment: {create_error}")

    async def log_metrics(self, metrics: dict):
        """Log metrics to MLflow."""
        print(f"Logging metrics: {metrics}")
        # This would contain actual MLflow logging code
        pass

    async def log_parameters(self, parameters: dict):
        """Log parameters to MLflow."""
        print(f"Logging parameters: {parameters}")
        # This would contain actual MLflow logging code
        pass

    async def finalize_active_runs(self):
        """Finalize any active MLflow runs during shutdown."""
        try:
            # End any active run
            active_run = mlflow.active_run()
            if active_run:
                mlflow.end_run()
                print(f"Finalized active MLflow run: {active_run.info.run_id}")
        except Exception as e:
            print(f"Warning: Could not finalize MLflow runs: {e}")

    @mlflow.trace(name="security_incident", span_type=SpanType.LLM)
    def trace_security_incident(
        self,
        incident_type: str,
        request_data: dict,
        pattern: str = None,
        error_message: str = None,
    ):
        """Trace security incidents in MLflow for blocked attacks."""
        try:
            # Get current span for this security incident
            current_span = mlflow.get_current_active_span()

            if current_span:
                # Set inputs (the malicious request)
                current_span.set_inputs(
                    {
                        "request_data": request_data,
                        "incident_type": incident_type,
                        "detected_pattern": pattern,
                        "blocked": True,
                    }
                )

                # Set outputs (the security response)
                current_span.set_outputs(
                    {
                        "action_taken": "blocked",
                        "error_message": error_message,
                        "security_status": "threat_detected",
                        "blocked_at": "input_validation",
                    }
                )

                # Set security-specific attributes
                current_span.set_attributes(
                    {
                        "security.incident_type": incident_type,
                        "security.threat_level": "high",
                        "security.blocked": True,
                        "security.pattern_matched": pattern or "unknown",
                        "llm.request.blocked": True,
                        "mlflow.spanType": "LLM",  # Mark as LLM span for proper UI display
                    }
                )

                # Add security event
                current_span.add_event(
                    SpanEvent(
                        "Security threat detected and blocked",
                        attributes={
                            "incident_type": incident_type,
                            "pattern": pattern,
                            "timestamp": datetime.now().isoformat(),
                        },
                    )
                )

            print(f"🚨 Security incident traced in MLflow: {incident_type}")
            return True

        except Exception as e:
            print(f"⚠️ Failed to trace security incident: {e}")
            return False

    @mlflow.trace(name="llm_generation", span_type=SpanType.LLM)
    def trace_llm_request(
        self,
        prompt: str,
        model: str,
        response: str,
        tokens: dict,
        cost: float,
        start_time: float,
        cache_hit: bool = False,
        cache_latency_ms: Optional[float] = None,
        cache_type: Optional[str] = None,
        similarity_score: Optional[float] = None,
        response_headers: Optional[Dict[str, str]] = None,
        response_metadata: Optional[Dict[str, Any]] = None,
    ):
        """Trace LLM generation requests with enhanced cache differentiation.

        Args:
            prompt: User input prompt
            model: LLM model name
            response: Generated response
            tokens: Token usage dictionary
            cost: Request cost
            start_time: Request start timestamp
            cache_hit: Whether cache was hit
            cache_latency_ms: Cache retrieval latency in milliseconds
            cache_type: Type of cache hit ('exact', 'semantic', or None)
            similarity_score: Similarity score for semantic cache hits (0-1)
            response_headers: Optional response headers
            response_metadata: Optional response metadata
        """
        try:
            print(f"🔍 Starting MLflow trace for model: {model}")
            print(f"🔍 MLflow tracking URI: {self.tracking_uri}")
            print(f"🔍 Current experiment: {self.experiment_name}")

            current_span = mlflow.get_current_active_span()
            current_time = time.time()
            duration_ms = (current_time - start_time) * 1000

            print(f"🔍 Current span: {current_span}")

            if current_span:
                # Set parent span inputs
                current_span.set_inputs(
                    {
                        "messages": [{"role": "user", "content": prompt}],
                        "model": model,
                        "temperature": 0.7,
                        "cache_enabled": True,
                    }
                )

                # Set parent span outputs
                current_span.set_outputs(
                    {
                        "choices": [
                            {"message": {"role": "assistant", "content": response}}
                        ],
                        "usage": tokens,
                        "cost": cost,
                        "latency_ms": duration_ms,
                        "cache_hit": cache_hit,
                        "cache_type": cache_type if cache_hit else None,
                        "cache_latency_ms": cache_latency_ms if cache_hit else None,
                        "similarity_score": similarity_score
                        if cache_hit and cache_type == "semantic"
                        else (1.0 if cache_hit and cache_type == "exact" else None),
                        "llm_latency_ms": None if cache_hit else duration_ms,
                    }
                )

                # Set parent span attributes
                current_span.set_attributes(
                    {
                        "llm.model": model,
                        "llm.prompt_tokens": tokens.get("prompt_tokens", 0),
                        "llm.completion_tokens": tokens.get("completion_tokens", 0),
                        "llm.total_tokens": tokens.get("total_tokens", 0),
                        "llm.cost": cost,
                        "llm.latency_ms": duration_ms,
                        "cache.enabled": True,
                        "cache.hit": cache_hit,
                        "cache.type": self._normalize_cache_type(cache_type)
                        if cache_hit
                        else "none",
                        "cache.latency_ms": cache_latency_ms if cache_hit else None,
                        "cache.similarity_score": similarity_score
                        if cache_hit and cache_type == "semantic"
                        else (1.0 if cache_hit and cache_type == "exact" else None),
                        "cache.is_exact": cache_type == "exact" if cache_hit else None,
                        "cache.is_semantic": cache_type == "semantic"
                        if cache_hit
                        else None,
                        "llm.actual_latency_ms": None if cache_hit else duration_ms,
                        "performance.cache_speedup": f"{((2000 - cache_latency_ms) / 2000 * 100):.1f}%"
                        if cache_hit and cache_latency_ms
                        else None,
                        "mlflow.spanType": "LLM",
                    }
                )

                # Stage 1: Input Validation (10% of time)
                with mlflow.start_span("1. Input Validation") as validation_span:
                    validation_span.set_attributes(
                        {
                            "stage": "validation",
                            "prompt_length": len(prompt),
                            "start_time": datetime.fromtimestamp(
                                start_time
                            ).isoformat(),
                            "duration_ms": duration_ms * 0.1,
                        }
                    )

                # Stage 2: Cache Check (20% of time)
                with mlflow.start_span("2. Cache Check") as cache_span:
                    cache_attributes = {
                        "stage": "cache",
                        "cache_hit": cache_hit,
                        "cache_type": self._normalize_cache_type(cache_type)
                        if cache_hit
                        else "none",
                        "latency_ms": cache_latency_ms if cache_hit else None,
                        "start_time": datetime.fromtimestamp(
                            start_time + duration_ms * 0.1 / 1000
                        ).isoformat(),
                        "duration_ms": duration_ms * 0.2,
                    }

                    # Add cache-type specific attributes
                    if cache_hit and cache_type:
                        if cache_type == "exact":
                            cache_attributes["exact_match"] = True
                            cache_attributes["similarity_score"] = 1.0
                        elif cache_type == "semantic":
                            cache_attributes["semantic_match"] = True
                            cache_attributes["similarity_score"] = (
                                similarity_score
                                if similarity_score is not None
                                else "unknown"
                            )

                    cache_span.set_attributes(cache_attributes)

                # Stage 3: LLM Processing (60% of time)
                with mlflow.start_span("3. LLM Processing") as process_span:
                    process_span.set_attributes(
                        {
                            "stage": "processing",
                            "tokens": tokens["total_tokens"],
                            "cost": cost,
                            "model": model,
                            "start_time": datetime.fromtimestamp(
                                start_time + duration_ms * 0.3 / 1000
                            ).isoformat(),
                            "duration_ms": duration_ms * 0.6,
                        }
                    )

                # Stage 4: Response Format (10% of time)
                with mlflow.start_span("4. Response Format") as format_span:
                    format_span.set_attributes(
                        {
                            "stage": "formatting",
                            "response_length": len(response),
                            "start_time": datetime.fromtimestamp(
                                start_time + duration_ms * 0.9 / 1000
                            ).isoformat(),
                            "duration_ms": duration_ms * 0.1,
                        }
                    )

                # Add enhanced cache-specific event if hit occurred
                if cache_hit:
                    # Determine event name and attributes based on cache type
                    normalized_cache_type = self._normalize_cache_type(cache_type)
                    event_name = f"Cache Hit - {normalized_cache_type.title()}"

                    event_attributes = {
                        "cache_type": normalized_cache_type,
                        "cache_latency_ms": cache_latency_ms,
                        "speedup_percentage": f"{((2000 - cache_latency_ms) / 2000 * 100):.1f}%"
                        if cache_latency_ms
                        else "N/A",
                        "estimated_llm_latency_ms": 2000,
                        "actual_latency_ms": cache_latency_ms,
                        "timestamp": datetime.fromtimestamp(current_time).isoformat(),
                        "is_exact_match": normalized_cache_type == "exact",
                        "is_semantic_match": normalized_cache_type == "semantic",
                    }

                    # Add similarity score for semantic matches
                    if normalized_cache_type == "exact":
                        event_attributes["similarity_score"] = 1.0
                        event_attributes["match_quality"] = "perfect"
                    elif normalized_cache_type == "semantic":
                        if similarity_score is not None:
                            event_attributes["similarity_score"] = similarity_score
                            event_attributes["match_quality"] = (
                                self._classify_similarity_quality(similarity_score)
                            )
                        else:
                            event_attributes["similarity_score"] = "unknown"
                            event_attributes["match_quality"] = "unknown"

                    current_span.add_event(
                        SpanEvent(event_name, attributes=event_attributes)
                    )

                # Add timing event
                current_span.add_event(
                    SpanEvent(
                        "timing_breakdown",
                        attributes={
                            "validation_ms": duration_ms * 0.1,
                            "cache_ms": duration_ms * 0.2,
                            "processing_ms": 0 if cache_hit else duration_ms * 0.6,
                            "formatting_ms": duration_ms * 0.1,
                            "total_ms": duration_ms,
                            "cache_hit": cache_hit,
                            "timestamp": datetime.fromtimestamp(
                                current_time
                            ).isoformat(),
                        },
                    )
                )

            # Return information for MLflow visualization
            return {
                "prompt": prompt,
                "model": model,
                "response": response,
                "tokens": tokens,
                "cost": cost,
                "latency_ms": duration_ms,
                "cache_hit": cache_hit,
                "cache_type": self._normalize_cache_type(cache_type)
                if cache_hit
                else "none",
                "cache_latency_ms": cache_latency_ms,
                "similarity_score": similarity_score
                if cache_hit and cache_type == "semantic"
                else (1.0 if cache_hit and cache_type == "exact" else None),
            }

        except Exception as e:
            print(f"⚠️ Failed to trace LLM request: {e}")
            return False

    def parse_litellm_response_headers(
        self, response_headers: Dict[str, str], response_metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Parse LiteLLM response headers and metadata for cache information.

        Args:
            response_headers: HTTP response headers from LiteLLM
            response_metadata: Additional metadata from LiteLLM response

        Returns:
            Dictionary containing parsed cache information
        """
        cache_info = {
            "cache_hit": False,
            "cache_type": "none",
            "cache_latency_ms": None,
            "similarity_score": None,
            "cache_key": None,
            "speedup_percentage": None,
        }

        try:
            # Check for cache-related headers (common patterns in LiteLLM)
            cache_headers_map = {
                "x-cache-status": "cache_status",
                "x-cache-hit": "cache_hit",
                "x-cache-type": "cache_type",
                "x-cache-latency": "cache_latency_ms",
                "x-cache-similarity": "similarity_score",
                "x-cache-key": "cache_key",
                "cache-control": "cache_control",
                "x-litellm-cache": "litellm_cache",
            }

            # Parse headers (case-insensitive)
            for header_name, header_value in response_headers.items():
                header_key = header_name.lower()

                if header_key in cache_headers_map:
                    field_name = cache_headers_map[header_key]

                    # Parse specific header values
                    if field_name == "cache_hit":
                        cache_info["cache_hit"] = header_value.lower() in [
                            "true",
                            "hit",
                            "1",
                            "yes",
                        ]
                    elif field_name == "cache_latency_ms":
                        cache_info["cache_latency_ms"] = self._parse_numeric_value(
                            header_value
                        )
                    elif field_name == "similarity_score":
                        cache_info["similarity_score"] = self._parse_numeric_value(
                            header_value
                        )
                    elif field_name in ["cache_type", "cache_key"]:
                        cache_info[field_name] = header_value
                    elif field_name == "litellm_cache":
                        # Parse JSON-like cache info from LiteLLM
                        cache_data = self._parse_json_header(header_value)
                        if cache_data:
                            cache_info.update(cache_data)

            # Parse metadata if provided
            if response_metadata:
                cache_info.update(self._parse_response_metadata(response_metadata))

            # Calculate speedup percentage if we have latency info
            if cache_info["cache_hit"] and cache_info["cache_latency_ms"]:
                estimated_llm_latency = 2000  # Estimated 2s for actual LLM call
                actual_latency = cache_info["cache_latency_ms"]
                speedup = (
                    (estimated_llm_latency - actual_latency) / estimated_llm_latency
                ) * 100
                cache_info["speedup_percentage"] = max(0, round(speedup, 1))

            return cache_info

        except Exception as e:
            print(f"⚠️ Error parsing LiteLLM headers: {e}")
            return cache_info

    def enhance_trace_with_cache_info(
        self,
        prompt: str,
        model: str,
        response: str,
        tokens: dict,
        cost: float,
        start_time: float,
        response_headers: Optional[Dict[str, str]] = None,
        response_metadata: Optional[Dict[str, Any]] = None,
        log_content: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Enhanced trace method that automatically parses cache information from available sources.

        This is a convenience method that combines cache information parsing with tracing.

        Args:
            prompt: User prompt
            model: Model name
            response: LLM response
            tokens: Token usage information
            cost: Request cost
            start_time: Request start time
            response_headers: Optional HTTP response headers
            response_metadata: Optional response metadata
            log_content: Optional log content to parse

        Returns:
            Dictionary containing trace information and parsed cache data
        """
        cache_info = {
            "cache_hit": False,
            "cache_type": "none",
            "cache_latency_ms": None,
            "similarity_score": None,
        }

        try:
            # First, try to parse from response headers/metadata
            if response_headers or response_metadata:
                parsed_cache_info = self.parse_litellm_response_headers(
                    response_headers or {}, response_metadata
                )
                cache_info.update(parsed_cache_info)

            # If no cache info found and log content is provided, try parsing logs
            if not cache_info["cache_hit"] and log_content:
                cache_events = self.parse_cache_logs(log_content)
                if cache_events:
                    # Use the most recent cache event
                    latest_event = cache_events[-1]
                    if latest_event.get("cache_hit"):
                        cache_info.update(
                            {
                                "cache_hit": latest_event["cache_hit"],
                                "cache_type": latest_event["cache_type"]
                                .replace("_", " ")
                                .replace(" hit", ""),
                                "cache_latency_ms": latest_event.get(
                                    "cache_latency_ms"
                                ),
                                "similarity_score": latest_event.get(
                                    "similarity_score"
                                ),
                            }
                        )

            # Now trace with the enhanced cache information
            trace_result = self.trace_llm_request(
                prompt=prompt,
                model=model,
                response=response,
                tokens=tokens,
                cost=cost,
                start_time=start_time,
                cache_hit=cache_info["cache_hit"],
                cache_latency_ms=cache_info["cache_latency_ms"],
                cache_type=cache_info["cache_type"],
                similarity_score=cache_info["similarity_score"],
                response_headers=response_headers,
                response_metadata=response_metadata,
            )

            # Return comprehensive information
            return {
                "trace_result": trace_result,
                "cache_info": cache_info,
                "parsed_successfully": True,
            }

        except Exception as e:
            print(f"⚠️ Error in enhanced trace with cache info: {e}")
            # Fallback to basic tracing without cache info
            trace_result = self.trace_llm_request(
                prompt=prompt,
                model=model,
                response=response,
                tokens=tokens,
                cost=cost,
                start_time=start_time,
            )

            return {
                "trace_result": trace_result,
                "cache_info": cache_info,
                "parsed_successfully": False,
                "error": str(e),
            }

    def parse_cache_logs(self, log_content: str) -> List[Dict[str, Any]]:
        """Parse log content for cache hit information using regex patterns.

        Args:
            log_content: Raw log content as string

        Returns:
            List of cache hit events found in logs
        """
        cache_events = []

        try:
            # Define regex patterns for different cache hit types
            patterns = {
                "exact_cache_hit": [
                    r"cache.*hit.*exact.*latency[:\s]*(\d+\.?\d*)\s*ms",
                    r"exact.*cache.*hit.*in\s*(\d+\.?\d*)\s*ms",
                    r"CACHE_HIT.*exact.*time[:\s]*(\d+\.?\d*)ms",
                ],
                "semantic_cache_hit": [
                    r"semantic.*cache.*hit.*similarity[:\s]*(\d+\.?\d*).*latency[:\s]*(\d+\.?\d*)\s*ms",
                    r"cache.*hit.*semantic.*score[:\s]*(\d+\.?\d*).*time[:\s]*(\d+\.?\d*)ms",
                    r"SEMANTIC_CACHE_HIT.*similarity[:\s]*(\d+\.?\d*).*latency[:\s]*(\d+\.?\d*)ms",
                ],
                "cache_miss": [
                    r"cache.*miss.*proceeding.*llm",
                    r"no.*cache.*found.*calling.*model",
                    r"CACHE_MISS.*forwarding.*request",
                ],
            }

            # Search through log content line by line
            for line_num, line in enumerate(log_content.split("\n"), 1):
                line = line.strip()
                if not line:
                    continue

                # Extract timestamp if present
                timestamp_match = re.search(
                    r"(\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2})", line
                )
                timestamp = timestamp_match.group(1) if timestamp_match else None

                # Check each pattern type
                for cache_type, pattern_list in patterns.items():
                    for pattern in pattern_list:
                        match = re.search(pattern, line, re.IGNORECASE)
                        if match:
                            event = {
                                "line_number": line_num,
                                "timestamp": timestamp,
                                "cache_type": cache_type,
                                "raw_line": line,
                                "cache_hit": cache_type != "cache_miss",
                            }

                            # Extract specific values based on cache type
                            if cache_type == "exact_cache_hit":
                                event["cache_latency_ms"] = (
                                    float(match.group(1)) if match.group(1) else None
                                )
                                event["similarity_score"] = 1.0  # Exact match

                            elif cache_type == "semantic_cache_hit":
                                groups = match.groups()
                                if len(groups) >= 2:
                                    event["similarity_score"] = (
                                        float(groups[0]) if groups[0] else None
                                    )
                                    event["cache_latency_ms"] = (
                                        float(groups[1]) if groups[1] else None
                                    )

                            cache_events.append(event)
                            break  # Stop checking other patterns for this line

            return cache_events

        except Exception as e:
            print(f"⚠️ Error parsing cache logs: {e}")
            return []

    def extract_cache_metrics_from_logs(self, log_content: str) -> Dict[str, Any]:
        """Extract aggregated cache metrics from log content.

        Args:
            log_content: Raw log content as string

        Returns:
            Dictionary containing aggregated cache metrics
        """
        metrics = {
            "total_requests": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "exact_hits": 0,
            "semantic_hits": 0,
            "cache_hit_rate": 0.0,
            "average_cache_latency_ms": 0.0,
            "average_similarity_score": 0.0,
            "total_time_saved_ms": 0.0,
        }

        try:
            cache_events = self.parse_cache_logs(log_content)

            if not cache_events:
                return metrics

            # Count different types of events
            latencies = []
            similarities = []

            for event in cache_events:
                if event.get("cache_hit"):
                    metrics["cache_hits"] += 1

                    if event["cache_type"] == "exact_cache_hit":
                        metrics["exact_hits"] += 1
                    elif event["cache_type"] == "semantic_cache_hit":
                        metrics["semantic_hits"] += 1

                    # Collect latency and similarity data
                    if event.get("cache_latency_ms"):
                        latencies.append(event["cache_latency_ms"])

                    if event.get("similarity_score"):
                        similarities.append(event["similarity_score"])

                else:  # cache miss
                    metrics["cache_misses"] += 1

            # Calculate aggregated metrics
            metrics["total_requests"] = len(cache_events)

            if metrics["total_requests"] > 0:
                metrics["cache_hit_rate"] = (
                    metrics["cache_hits"] / metrics["total_requests"]
                ) * 100

            if latencies:
                metrics["average_cache_latency_ms"] = sum(latencies) / len(latencies)
                # Estimate time saved (assuming 2s average LLM call)
                estimated_llm_time = 2000
                metrics["total_time_saved_ms"] = sum(
                    estimated_llm_time - lat for lat in latencies
                )

            if similarities:
                metrics["average_similarity_score"] = sum(similarities) / len(
                    similarities
                )

            return metrics

        except Exception as e:
            print(f"⚠️ Error extracting cache metrics: {e}")
            return metrics

    def _parse_numeric_value(self, value: str) -> Optional[float]:
        """Parse numeric value from string, handling various formats."""
        try:
            # Remove common suffixes and whitespace
            clean_value = re.sub(r"[ms%\s]", "", value)
            return float(clean_value)
        except (ValueError, TypeError):
            return None

    def _parse_json_header(self, header_value: str) -> Optional[Dict[str, Any]]:
        """Parse JSON-like header value."""
        try:
            # Try to parse as JSON
            return json.loads(header_value)
        except json.JSONDecodeError:
            # Try to parse key=value pairs
            try:
                pairs = re.findall(r"(\w+)=([^,;]+)", header_value)
                return {key: value.strip("\"'") for key, value in pairs}
            except Exception:
                return None

    def _parse_response_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Parse response metadata for cache information."""
        cache_info = {}

        # Look for cache-related fields in metadata
        cache_fields = {
            "cache_hit": "cache_hit",
            "cache_type": "cache_type",
            "cache_latency": "cache_latency_ms",
            "cache_latency_ms": "cache_latency_ms",
            "similarity_score": "similarity_score",
            "cache_key": "cache_key",
            "litellm_cache_hit": "cache_hit",
        }

        for meta_key, cache_key in cache_fields.items():
            if meta_key in metadata:
                value = metadata[meta_key]

                if cache_key == "cache_hit":
                    cache_info[cache_key] = bool(value)
                elif cache_key == "cache_latency_ms":
                    cache_info[cache_key] = self._parse_numeric_value(str(value))
                elif cache_key == "similarity_score":
                    cache_info[cache_key] = self._parse_numeric_value(str(value))
                else:
                    cache_info[cache_key] = value

        return cache_info

    def _normalize_cache_type(self, cache_type: Optional[str]) -> str:
        """Normalize cache type to standard values for consistency.

        Args:
            cache_type: Raw cache type string

        Returns:
            Normalized cache type ('exact', 'semantic', or 'none')
        """
        if not cache_type:
            return "none"

        cache_type_lower = cache_type.lower().strip()

        # Normalize exact cache variations
        if any(
            term in cache_type_lower
            for term in ["exact", "perfect", "identical", "direct"]
        ):
            return "exact"

        # Normalize semantic cache variations
        if any(
            term in cache_type_lower
            for term in ["semantic", "similarity", "approximate", "fuzzy"]
        ):
            return "semantic"

        # Handle cache hit/miss patterns from logs
        if "exact_cache_hit" in cache_type_lower:
            return "exact"
        if "semantic_cache_hit" in cache_type_lower:
            return "semantic"

        # Default fallback
        return cache_type_lower if cache_type_lower != "none" else "none"

    def _classify_similarity_quality(self, similarity_score: float) -> str:
        """Classify similarity score into quality categories.

        Args:
            similarity_score: Similarity score between 0 and 1

        Returns:
            Quality classification string
        """
        if similarity_score >= 0.95:
            return "excellent"
        elif similarity_score >= 0.85:
            return "good"
        elif similarity_score >= 0.75:
            return "fair"
        elif similarity_score >= 0.65:
            return "marginal"
        else:
            return "poor"


# Global instance
mlflow_service = MLflowService()
