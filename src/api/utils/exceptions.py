"""Exception handlers for the API."""

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from services.security_service import security_metrics, trace_security_incident


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic validation errors and trace security-relevant ones in MLflow."""
    print(f"DEBUG: Validation error: {exc.errors()}")
    
    # Check if this is a security-relevant validation error
    for error in exc.errors():
        error_type = error.get("type", "")
        error_input = error.get("input", "")
        error_loc = error.get("loc", [])
        
        # Security-relevant validation errors
        security_relevant = False
        incident_type = "input_validation_error"
        
        if error_type == "string_pattern_mismatch" and "model" in error_loc:
            if "../" in str(error_input) or "passwd" in str(error_input) or "\\" in str(error_input):
                security_relevant = True
                incident_type = "model_path_traversal_attempt"
        elif error_type == "greater_than_equal" and any(field in error_loc for field in ["max_tokens", "temperature"]):
            if "max_tokens" in error_loc and int(error_input) < 0:
                security_relevant = True
                incident_type = "negative_token_attack"
        elif error_type == "less_than_equal" and "temperature" in error_loc:
            if float(error_input) > 10:  # Extremely high temperature
                security_relevant = True
                incident_type = "extreme_temperature_attack"
        
        if security_relevant:
            # Update security metrics
            security_metrics["blocked_requests"] += 1
            security_metrics["validation_failures"] += 1
            
            # Trace in MLflow
            try:
                trace_security_incident(
                    incident_type=incident_type,
                    request_data={
                        "error_type": error_type,
                        "error_input": str(error_input),
                        "error_location": error_loc,
                        "field": error_loc[-1] if error_loc else "unknown"
                    },
                    pattern=f"validation_{error_type}",
                    error_message=error.get("msg", "Validation error")
                )
            except Exception as trace_error:
                print(f"Warning: Could not trace validation error: {trace_error}")
    
    # Return the validation error response
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()}
    )