"""Shared application services: paths, settings, logging, engines, versioning."""

# Antivirus and corporate proxies replace TLS certificates with ones that only
# the system store trusts. Without this, model and update downloads fail with
# CERTIFICATE_VERIFY_FAILED on such machines.
try:
    import truststore

    truststore.inject_into_ssl()
except Exception:
    pass
