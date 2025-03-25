from app.api.error_report.report import Report
from app.external.result_type.src.result import Err, Ok, Result


def nested_err_4() -> Result[str, Report]:
    try:
        with open("this_file_doesnt_exist.txt", "r") as f:
            content = f.read()
            print(content)
    except FileNotFoundError as e:
        return Err(Report("Something went wrong at level 4", e))

    return Ok("Ok")


def nested_err_3() -> Result[str, Report]:
    res = nested_err_4()
    match res:
        case Ok(_):
            print("Level 4 was OK")
        case Err(report):
            return Err(
                report.change_context("Changing context at level 3. Level 4 haz errors")
                .attach("This is an attachment with more information at level 3")
                .attach(
                    """User tried to send a message.
                    Testing multi line attachments.
                    More explanation here!!!"""
                )
                .attach(
                    {
                        "data": "this is a sensitive message",
                        "recipient": "test_recipient",
                    },
                    name="input",
                    sensitive=True,
                )
            )

    return Ok("Ok")


def nested_err_2() -> Result[str, Report]:
    res = nested_err_3()
    match res:
        case Ok(_):
            print("Level 3 was OK")
        case Err(report):
            return Err(
                report.change_context("Changing context at level 2. Level 3 haz errors")
                .attach("This is an attachment with more information at level 2")
                .attach("Even more context")
            )

    return Ok("Ok")


def nested_err_1() -> Result[str, Report]:
    res = nested_err_2()
    match res:
        case Ok(_):
            print("Level 2 was OK")
        case Err(report):
            return Err(
                report.change_context(
                    "Changing context at level 1. Level 2 or above had errors... teeest"
                )
            )

    return Ok("Ok")


def read_config_file(filename: str) -> Result[bool, Report]:
    """Attempt to read and parse a configuration file."""
    try:
        with open(filename, "r") as f:
            content = f.read()

        # Simulate parsing error
        if not content.strip():
            return Err(Report("Config file not found", ValueError()))

        # In real code, you might parse JSON, YAML, etc.
        return Ok(True)

    except FileNotFoundError as e:
        # Wrap the low-level error with context
        err = Report(f'could not read file "{filename}"', e)
        # You can add additional context or attachments
        err.attach(filename, "filename")
        print("returning err file not found")
        return Err(err)

    except ValueError as e:
        # Another way to wrap errors
        report = Report("Error parsing config", e)
        print("parse error")
        return Err(report)


def process_configuration() -> Result[bool, Report]:
    """Process application configuration with proper error handling."""
    match read_config_file("config.cfg"):
        case Ok(value):
            print(f"Configuration loaded successfully: {value}")
        case Err(report):
            report.change_context("Unable to configure the application")
            return Err(report)

    return Ok(True)


if __name__ == "__main__":
    res = nested_err_1()
    match res:
        case Ok(value):
            print("Success")
        case Err(report):
            print(report.format_verbose())
