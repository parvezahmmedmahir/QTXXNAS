"""
QUANTUM X PRO - Quotex Adapter (Direct API)
Uses local PyQuotex library for direct broker authentication.
OTP bypass enabled via session persistence.
"""
from brokers.quotex_pyquotex import QuotexWSAdapter as PyAdapter

# Export the Direct Adapter
QuotexWSAdapter = PyAdapter

__all__ = ['QuotexWSAdapter']
