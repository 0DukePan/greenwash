"""greenwash -- a report on what an agent's "done" claim is actually worth.

The public surface is small and stable:

    greenwash.domain          Run, Claim, Signal, VerificationResult, Verdict,
                              TrustReport -- the versioned wire format
    greenwash.confidence      deterministic, explainable scoring
    greenwash.scan            static diff analysis -> Signal[]
    greenwash.verify          behavioral verification -> VerificationResult
    greenwash.report          terminal / json / markdown renderers
    greenwash.cli             zero-config entry point

Nothing here requires a network call, an account, or a model. The tool reads
your diff and runs your tests; that is the whole mechanism.
"""

__version__ = "0.4.0"

__all__ = ["__version__"]
