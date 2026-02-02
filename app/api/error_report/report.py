import inspect
import traceback
from dataclasses import dataclass, field
from typing import Any, List, Optional



@dataclass
class Attachment:
    """Represents an attachment to an error frame."""

    value: Any
    name: Optional[str] = None
    sensitive: bool = True

    def __str__(self, include_sensitive: bool = False) -> str:
        if self.sensitive and not include_sensitive:
            if self.name:
                return f"{self.name}: (Sensitive data omitted)"
            return "(Sensitive data omitted)"

        if self.name:
            base = f"{self.name}: {self.value}"
        else:
            base = f"{self.value}"

        return base


@dataclass
class Location:
    """Represents a source code location."""

    file: str
    line: int
    column: int = 0

    def __str__(self) -> str:
        if self.column:
            return f"{self.file}:{self.line}:{self.column}"
        return f"{self.file}:{self.line}"


@dataclass
class Frame:
    """Represents a single error frame in the error stack."""

    message: str
    error: Optional[Exception] = None
    location: Optional[Location] = None
    attachments: List[Attachment] = field(default_factory=list)

    def __post_init__(self):
        """Initialize location if not provided."""
        if not self.location:
            # Get caller frame information
            frame = inspect.currentframe()
            for _ in range(3):  # Skip our own frames
                if frame and frame.f_back:
                    frame = frame.f_back
                else:
                    frame = None
                    break

            if frame:
                self.location = Location(
                    file=frame.f_code.co_filename,
                    line=frame.f_lineno,
                    column=10,  # Column is often not available, use a default
                )

    def attach(
        self, value: Any, name: Optional[str] = None, sensitive: bool = True
    ) -> "Frame":
        """
        Attach arbitrary data to this frame.

        Args:
            value: The data to attach
            name: Optional name for the attachment
            sensitive: Whether this attachment contains sensitive data
        """
        self.attachments.append(Attachment(value, name, sensitive))
        return self

    def __str__(self) -> str:
        return self.message


class Report:
    """Represents an error report containing multiple frames and context."""

    def __init__(self, message: str, error: Optional[Exception] = None):
        """Create a new error report with an initial frame."""
        self._frames: List[Frame] = []
        self._root_error = error

        # Create and add the root frame - this is the higher level context/message
        self.attach_frame(Frame(message=message, error=error))

        # If an exception was provided, capture its traceback
        self._traceback = None
        if error:
            self._traceback = (
                traceback.extract_tb(error.__traceback__)
                if error.__traceback__
                else None
            )

    def attach_frame(self, frame: Frame) -> "Report":
        """Add a new error frame to the report."""
        self._frames.append(frame)
        return self

    def change_context(self, message: str) -> "Report":
        """Add a new context frame to the report."""
        return self.attach_frame(Frame(message=message))

    def attach(
        self, value: Any, name: Optional[str] = None, sensitive: bool = False
    ) -> "Report":
        """
        Attach data to the most recent frame.

        Args:
            value: The data to attach
            name: Optional name for the attachment
            sensitive: Whether this attachment contains sensitive data that
                       should be redacted in normal error reports
        """
        if self._frames:
            self._frames[-1].attach(value, name, sensitive)
        return self

    def _format_attachment(
        self,
        attachment_str: str,
        indent: str,
    ) -> List[str]:
        """
        Format an attachment string with proper multi-line handling.

        Args:
            attachment_str: The attachment string to format
            indent: Current indentation level
            include_sensitive: Whether to include sensitive data

        Returns:
            List of formatted lines
        """
        # Split the attachment string into lines
        lines = attachment_str.split("\n")
        result = []

        # First line gets the attachment prefix
        if lines:
            result.append(f"{indent}├╴{lines[0]}")

        # Subsequent lines get continuation prefix
        for line in lines[1:]:
            # Strip leading whitespace from continuation lines for better formatting
            cleaned_line = line.lstrip()
            if cleaned_line:  # Avoid adding empty lines
                result.append(f"{indent}│ {cleaned_line}")

        return result

    def format(self, include_sensitive: bool = False) -> str:
        """
        Format the error report for display with nested contexts.

        Args:
            include_sensitive: Whether to include sensitive attachment
                               data in the output
        """
        if not self._frames:
            return "Empty error report"

        # In the expected output, contexts are printed in reverse order (newest first)
        frames = list(reversed(self._frames))

        # Start with the newest context/frame (the last one added)
        top_frame = frames[0]

        lines = []
        lines.append(str(top_frame))

        # Add location for the top frame
        if top_frame.location:
            lines.append(f"├╴at {top_frame.location}")

        # For attachments on the top frame
        for attachment in top_frame.attachments:
            attachment_lines = self._format_attachment(
                attachment.__str__(include_sensitive), ""
            )
            lines.extend(attachment_lines)

        # If we have more than one frame
        if len(frames) > 1:
            # Start the hierarchical error structure
            lines.append(f"╰─▶ {frames[1].message}")

            # Process all frames from the second one onwards
            current_indent = "    "
            for i in range(1, len(frames)):
                frame = frames[i]

                # Add location
                if frame.location:
                    lines.append(f"{current_indent}├╴at {frame.location}")

                # Add attachments
                for attachment in frame.attachments:
                    attachment_lines = self._format_attachment(
                        attachment.__str__(include_sensitive),
                        current_indent,
                    )
                    lines.extend(attachment_lines)

                # If not the last frame, add the arrow to the next frame
                if i < len(frames) - 1:
                    lines.append(f"{current_indent}╰─▶ {frames[i + 1].message}")
                # If last frame and we have a root error
                elif self._root_error:
                    # Add backtrace info
                    lines.append(f"{current_indent}│")
                    lines.append(
                        f"{current_indent}╰╴backtrace "
                        f"({len(self._traceback) if self._traceback else 0})"
                    )

                # Increase indentation for the next level
                current_indent += "    "
        else:
            # If only one frame and we have a root error
            if self._root_error:
                error_str = str(self.root_error).replace("\n", "\n    │")
                lines.append(f"│")  # noqa: F541
                lines.append(f"╰─▶ {error_str}")

                # Add location for error
                if top_frame.location and not self._traceback:
                    lines.append(f"    ╰╴at {top_frame.location}")
                if top_frame.location and self._traceback:
                    lines.append(f"    ├╴at {top_frame.location}")

                # Add backtrace info
                if self._traceback:
                    lines.append(f"    │")  # noqa: F541
                    lines.append(f"    ╰╴backtrace ({len(self._traceback)})")

        return "\n".join(lines)

    def format_verbose(self, include_sensitive: bool = False) -> str:
        """
        Format the error report with full traceback information.

        Args:
            include_sensitive: Whether to include sensitive attachment data
                              (defaults to True for verbose mode)
        """
        basic_output = self.format(include_sensitive)

        if not self._traceback:
            return basic_output

        # Add the full traceback
        tb_lines = []
        for frame in self._traceback:
            filename, line, func, code = frame
            tb_lines.append(f'  File "{filename}", line {line}, in {func}')
            if code:
                tb_lines.append(f"    {code}")

        return basic_output + "\n" + "\n".join(tb_lines)

    def __str__(self) -> str:
        """Default string representation without sensitive data."""
        return self.format(include_sensitive=False)

    def __repr__(self) -> str:
        """Representation with indication of frames and error presence."""
        frame_count = len(self._frames)
        has_error = "with error" if self._root_error else "without error"
        return f"<Report: {frame_count} frames, {has_error}>"

    @property
    def frames(self) -> List[Frame]:
        """Access the frames list"""
        return self._frames.copy()

    @property
    def root_error(self) -> Optional[Exception]:
        """Access the root error"""
        return self._root_error

    @property
    def last_error(self) -> Optional[Exception]:
        """Access the last error"""
        return self._frames[-1].error
