"""Standalone trust regression, runnable without service configuration.

Run directly: python tests/test_ca_trust.py
Full incident-chain and pip-context coverage lives in RaspiBlitz's manual
python-trust-regression.py, since RaspiBlitz owns the venv installer.
"""
import hashlib
import ssl
import unittest

import certifi
import httpx
import requests


BLOCKED = {
    "86a1ecba089c4a8d3bbe2734c612ba341d813e043cf9e8a862cd5c57a36bbe6b",
    "d7a7a0fb5d7e2731d771e9484ebcdef71d5f0c3e0a2948782bc83ee0ea699ef4",
}


class CATrustTests(unittest.TestCase):
    def assert_clean(self, context):
        roots = context.get_ca_certs(binary_form=True)
        self.assertTrue(roots)
        self.assertFalse({hashlib.sha256(c).hexdigest() for c in roots} & BLOCKED)

    def test_certifi(self):
        self.assert_clean(ssl.create_default_context(cafile=certifi.where()))

    def test_requests_default(self):
        with requests.Session() as session:
            session.trust_env = False
            request = requests.Request("GET", "https://pypi.org").prepare()
            adapter = session.get_adapter(request.url)
            conn = adapter.get_connection_with_tls_context(request, True)
            adapter.cert_verify(conn, request.url, True, None)
            self.assert_clean(ssl.create_default_context(cafile=conn.ca_certs))

    def test_httpx_default(self):
        with httpx.Client(trust_env=False) as client:
            self.assert_clean(client._transport._pool._ssl_context)


if __name__ == "__main__":
    unittest.main()
