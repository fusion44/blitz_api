# Python Error Stack

A library that emulates Rust's `error_stack` crate, providing nested error context and rich error reporting.

## Overview

The Error Stack library provides a robust way to handle errors in Python applications, inspired by Rust's `error_stack` crate. It allows for:

1. Creating layered error reports with nested context
2. Adding arbitrary attachments to errors, with support for sensitive data handling
3. Capturing source location information automatically
4. Pretty-printing errors in a hierarchical style that shows the error propagation path
5. Proper formatting of multi-line attachments with continuation lines

## Core Components

### `Attachment`

Represents data attached to an error frame:
- Contains a value, optional name, and sensitive flag
- Can be marked as sensitive to prevent accidental exposure in logs
- Handles multi-line text with proper formatting but doesn't preserve whitespace withing the multi-line text

### `Frame`

Represents a single error or context frame in the error stack. Contains:
- A message
- Optional exception
- Source code location
- Arbitrary attachments (including sensitive data)

### `Report`

The main error report containing a stack of frames. Supports:
- Adding new context frames
- Attaching data to frames
- Pretty printing in a hierarchical format
- Capturing exception tracebacks
- Control over display of sensitive information

## Usage Examples

### Basic Usage

```python
from app.api.error_report.report import Report

try:
    # Some operation that might fail
    with open("non_existent_file.txt", "r") as f:
        content = f.read()
except FileNotFoundError as e:
    # Create an error report
    err = Report("Could not load configuration", e)
    # Print it
    print(err)
    # Or return it
    return err
```

### Adding Nested Context

When errors propagate through different layers of your application, you can add context:

```python
from app.api.error_report.report import Report

def low_level_function():
    try:
        with open("config.json", "r") as f:
            return f.read()
    except FileNotFoundError as e:
        return Report("Failed to read configuration file", e)

def mid_level_function():
    result = low_level_function()
    if isinstance(result, Report):
        return result.change_context("Configuration loading failed")
    # Process the file contents...
    return result

def high_level_function():
    result = mid_level_function()
    if isinstance(result, Report):
        return result.change_context("Application initialization error")
    # Continue with application...
    return result
```

### Using with `Result` Type

For more Rust-like error handling, combine with a Result type:

```python
from app.api.error_report.report import Report
from result import Result, Ok, Err  # Use your preferred Result implementation

def read_file(path: str) -> Result[str, Report]:
    try:
        with open(path, "r") as f:
            content = f.read()
            return Ok(content)
    except FileNotFoundError as e:
        return Err(Report(f"Could not read file '{path}'", e))

def process_config() -> Result[dict, Report]:
    match read_file("config.json"):
        case Ok(content):
            # Process content
            return Ok({"success": True})
        case Err(report):
            # Add context and propagate
            return Err(report.change_context("Failed to process configuration"))
```

### Attaching Data

You can attach arbitrary data to error reports for additional context:

```python
def process_user_data(user_id: str) -> Result[dict, Report]:
    try:
        # Process user data
        user = db.get_user(user_id)
        return Ok(user)
    except DatabaseError as e:
        err = Report("User data processing failed", e)
        # Attach contextual information
        err.attach(user_id, "user_id")
        err.attach({"attempted_at": datetime.now()}, "metadata")
        return Err(err)
```

### Multi-line Attachments

The library properly handles multi-line text in attachments:

```python
err = Report("Failed to process message", error)
err.attach("""User tried to send a message.
            This message contained invalid formatting.
            Attempted to process anyway but failed.""")
```

This will produce formatted output with continuation lines:

```
Failed to process message
├╴at /path/to/file.py:35:10
├╴User tried to send a message.
│ This message contained invalid formatting.
│ Attempted to process anyway but failed.
│
╰─▶ [Errno 2] Invalid message format
```

### Handling Sensitive Data

For sensitive information that shouldn't appear in normal logs:

```python
def authenticate_user(username: str, password: str) -> Result[User, Report]:
    try:
        # Authentication process
        user = auth_service.authenticate(username, password)
        return Ok(user)
    except AuthenticationError as e:
        err = Report("Authentication failed", e)

        # Safe to include in all logs
        err.attach(username, "username")

        # Mark sensitive data to be redacted in normal output
        # Example purposes, never ever include passwords in logs in production deployments
        err.attach(password, "password", sensitive=True)
        err.attach({"ip": "192.168.1.1", "api_key": "sk_test_123"}, "connection_info", sensitive=True)

        return Err(err)

# Usage:
match authenticate_user("johndoe", "secret123"):
    case Ok(user):
        print(f"Authenticated: {user.name}")
    case Err(report):
        # Normal output (safe for logs, no sensitive data)
        print(report)

        # For debug purposes only, include sensitive data
        print(report.format(include_sensitive=True))

        # Or with full traceback and sensitive data
        print(report.format_verbose())
```

The normal output would show:
```
Authentication failed
├╴at /path/to/file.py:35:10
├╴username: johndoe
├╴password: (Sensitive data omitted)
├╴connection_info: (Sensitive data omitted)
...
```

But the sensitive version would show:
```
Authentication failed
├╴at /path/to/file.py:35:10
├╴username: johndoe
├╴password: secret123
├╴connection_info: {'ip': '192.168.1.1', 'api_key': 'sk_test_123'}
...
```

### Nested Errors Example

Here's a more complete example showing nested error handling through multiple layers:

```python
def level_4_function() -> Result[str, Report]:
    try:
        with open("missing_file.txt", "r") as f:
            content = f.read()
        return Ok(content)
    except FileNotFoundError as e:
        return Err(Report("Something went wrong at level 4", e))

def level_3_function() -> Result[str, Report]:
    match level_4_function():
        case Ok(content):
            return Ok(content)
        case Err(report):
            return Err(
                report.change_context("Changing context at level 3")
                      .attach("Additional context for debugging")
            )

def level_2_function() -> Result[str, Report]:
    match level_3_function():
        case Ok(content):
            return Ok(content)
        case Err(report):
            return Err(report.change_context("Error occurred at level 2"))

def level_1_function() -> Result[str, Report]:
    match level_2_function():
        case Ok(content):
            return Ok(content)
        case Err(report):
            return Err(report.change_context("Top level error context"))

# Usage
match level_1_function():
    case Ok(content):
        print("Success:", content)
    case Err(report):
        print(report.format())  # Prints the nested error context
```

## Benefits

1. **Clear Error Context**: Creates a hierarchy of error contexts that help track down the root cause.
2. **Rich Debugging Information**: Automatically captures source locations and provides detailed error traces.
3. **Separation of Concerns**: Allows different layers of your application to add appropriate context without losing the original error.
4. **Consistent Error Handling**: Provides a uniform way to handle errors throughout your application.
5. **Security Conscious**: Allows including sensitive data for debugging while preventing accidental exposure in logs.
6. **Readable Formatting**: Maintains proper formatting for multi-line text with continuation lines.

## Potential Downsides

1. **Overhead**: Creating detailed error reports with locations and tracebacks adds computational and memory overhead compared to simple exceptions.

2. **Learning Curve**: The pattern is different from traditional Python exception handling, requiring developers to learn a new approach.

3. **Return Value Checking**: Without using a Result type, you need explicit type checking on return values to determine if you got a Report or a valid result.

4. **Memory Usage**: For long error chains with many attachments, memory usage can grow significantly.

5. **Limited Integration**: Not all third-party libraries support this pattern, requiring adapter code at integration boundaries.

6. **Potential for Data Leakage**: Despite the sensitive data handling, there's a risk of accidentally exposing sensitive information if `include_sensitive=True` is used inappropriately.

7. **Serialization Challenges**: When serializing errors (for logging or API responses), ensuring consistent handling of complex nested data structures requires careful implementation.

## Best Practices

1. Create error reports at the lowest level where exceptions occur
2. Add context as errors propagate up through your application layers
3. Mark sensitive data appropriately using the `sensitive=True` flag
4. Only use `include_sensitive=True` or `format_verbose()` in controlled environments
5. Use multi-line text for detailed explanations that need more than a single line
6. Use with a Result type for more predictable error handling
7. Format reports at the application boundary for logging or user display
