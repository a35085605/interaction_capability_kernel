from __future__ import annotations

import unittest
from datetime import datetime, timezone

from native_attempt import (
    NativeAttemptResult,
    NativeAttemptStatus,
    NativeCompletionScope,
)


class NativeAttemptResultTests(unittest.TestCase):
    def test_result_declares_the_completed_native_boundary(self) -> None:
        now = datetime(2026, 8, 13, tzinfo=timezone.utc)
        result = NativeAttemptResult(
            status=NativeAttemptStatus.SUCCEEDED,
            completion_scope=NativeCompletionScope.SUBMISSION,
            backend_id="send-input",
            started_at=now,
            finished_at=now,
            native_code="1",
        )

        self.assertIs(result.status, NativeAttemptStatus.SUCCEEDED)
        self.assertIs(
            result.completion_scope,
            NativeCompletionScope.SUBMISSION,
        )

    def test_completion_scope_requires_domain_enum(self) -> None:
        now = datetime(2026, 8, 13, tzinfo=timezone.utc)
        with self.assertRaisesRegex(TypeError, "NativeCompletionScope"):
            NativeAttemptResult(
                status=NativeAttemptStatus.SUCCEEDED,
                completion_scope="submission",  # type: ignore[arg-type]
                backend_id="backend",
                started_at=now,
                finished_at=now,
            )

    def test_success_requires_a_completed_native_boundary(self) -> None:
        now = datetime(2026, 8, 13, tzinfo=timezone.utc)
        with self.assertRaisesRegex(ValueError, "requires completion_scope"):
            NativeAttemptResult(
                status=NativeAttemptStatus.SUCCEEDED,
                completion_scope=None,
                backend_id="backend",
                started_at=now,
                finished_at=now,
            )

    def test_failure_may_occur_before_a_native_boundary_completes(self) -> None:
        now = datetime(2026, 8, 13, tzinfo=timezone.utc)
        result = NativeAttemptResult(
            status=NativeAttemptStatus.FAILED,
            completion_scope=None,
            backend_id="backend",
            started_at=now,
            finished_at=now,
        )

        self.assertIsNone(result.completion_scope)


if __name__ == "__main__":
    unittest.main()
