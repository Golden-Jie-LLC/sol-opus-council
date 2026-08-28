"""Typed council errors."""


class CouncilError(RuntimeError):
    """Base class for expected council failures."""


class PreflightError(CouncilError):
    """A required executable or feature is unavailable."""


class AuthenticationError(PreflightError):
    """Claude Code is not authenticated."""


class OpusUnavailableError(PreflightError):
    """The requested Opus model cannot be used."""


class ProcessError(CouncilError):
    """The Claude child process failed."""


class ProcessTimeoutError(ProcessError):
    """The Claude child process exceeded its bounded timeout."""


class MalformedOutputError(ProcessError):
    """Claude returned empty, invalid, or contract-incompatible JSON."""


class SchemaValidationError(MalformedOutputError):
    """Structured output did not satisfy the selected schema."""


class ProtocolStateError(CouncilError):
    """A protocol action was attempted out of order."""


class ContextRepairLimitError(ProtocolStateError):
    """The bounded context-repair allowance was exhausted."""


class CandidateValidationError(ProtocolStateError):
    """A candidate is empty or not execution-ready at the mechanical level."""
