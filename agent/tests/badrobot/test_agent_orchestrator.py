"""Tests for agent_orchestrator.py"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from sparky.agent_orchestrator import criminal_ip_domain_scan_retry


class TestCriminalIPDomainScanRetry:
    """Tests for the criminal_ip_domain_scan_retry function."""

    @pytest.mark.asyncio
    async def test_successful_scan_on_first_try(self):
        """Test that a successful scan returns immediately."""
        mock_result = {
            "status": "success",
            "data": {"domain": "example.com", "score": 95},
        }

        with patch(
            "sparky.agent_orchestrator.criminal_ip_domain_scan",
            new=AsyncMock(return_value=mock_result),
        ) as mock_scan:
            result = await criminal_ip_domain_scan_retry("example.com")

            assert result == mock_result
            assert mock_scan.call_count == 1
            mock_scan.assert_called_with(domain="example.com")

    @pytest.mark.asyncio
    async def test_retry_on_failure(self):
        """Test that the function retries on failure."""
        mock_failure = {"status": "error", "message": "API error"}
        mock_success = {
            "status": "success",
            "data": {"domain": "example.com", "score": 95},
        }

        with patch(
            "sparky.agent_orchestrator.criminal_ip_domain_scan",
            new=AsyncMock(side_effect=[mock_failure, mock_success]),
        ) as mock_scan:
            result = await criminal_ip_domain_scan_retry("example.com", max_retries=3)

            assert result == mock_success
            assert mock_scan.call_count == 2

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self):
        """Test that the function gives up after max retries."""
        mock_failure = {"status": "error", "message": "API error"}

        with patch(
            "sparky.agent_orchestrator.criminal_ip_domain_scan",
            new=AsyncMock(return_value=mock_failure),
        ) as mock_scan:
            result = await criminal_ip_domain_scan_retry(
                "example.com", max_retries=2, delay=0.01
            )

            assert result["status"] == "error"
            assert "failed after multiple retries" in result["message"]
            # Called twice in the loop (attempts 0 and 1)
            assert mock_scan.call_count == 2

    @pytest.mark.asyncio
    async def test_exponential_backoff(self):
        """Test that the delay increases exponentially."""
        mock_failure = {"status": "error", "message": "API error"}

        with patch(
            "sparky.agent_orchestrator.criminal_ip_domain_scan",
            new=AsyncMock(return_value=mock_failure),
        ), patch("asyncio.sleep", new=AsyncMock()) as mock_sleep:
            await criminal_ip_domain_scan_retry(
                "example.com", max_retries=3, delay=1
            )

            # Check that sleep was called with exponentially increasing delays
            # After 1st attempt: sleep(1), after 2nd: sleep(2), after 3rd: sleep(4)
            assert mock_sleep.call_count == 3
            calls = [call.args[0] for call in mock_sleep.call_args_list]
            assert calls == [1, 2, 4]

    @pytest.mark.asyncio
    async def test_exception_handling(self):
        """Test that exceptions are caught and retried."""
        mock_success = {
            "status": "success",
            "data": {"domain": "example.com", "score": 95},
        }

        with patch(
            "sparky.agent_orchestrator.criminal_ip_domain_scan",
            new=AsyncMock(
                side_effect=[Exception("Network error"), Exception("Timeout"), mock_success]
            ),
        ) as mock_scan:
            result = await criminal_ip_domain_scan_retry(
                "example.com", max_retries=3, delay=0.01
            )

            assert result == mock_success
            assert mock_scan.call_count == 3

    @pytest.mark.asyncio
    async def test_no_infinite_recursion(self):
        """Test that the function doesn't call itself recursively."""
        # This is a regression test for the bug where the retry function
        # was calling itself instead of the actual scan function
        mock_result = {"status": "success", "data": {"domain": "example.com"}}

        with patch(
            "sparky.agent_orchestrator.criminal_ip_domain_scan",
            new=AsyncMock(return_value=mock_result),
        ) as mock_scan:
            # If there's infinite recursion, this will hit the recursion limit
            # and raise RecursionError
            result = await criminal_ip_domain_scan_retry("example.com")

            assert result == mock_result
            # Ensure it's calling the actual function, not itself
            assert mock_scan.called

