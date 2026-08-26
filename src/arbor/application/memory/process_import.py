from __future__ import annotations

from arbor.application.memory.media_to_inbox import MediaInboxResult, MediaToInbox


class ProcessImportJob:
    """Parse uploaded media into pending Inbox items. Does not write MemoryItem."""

    def __init__(self, *, media_to_inbox: MediaToInbox) -> None:
        self.media_to_inbox = media_to_inbox

    def __call__(
        self,
        *,
        tenant_id,
        user_id,
        persona_id,
        filename: str,
        data: bytes = b"",
        hint: str | None = None,
        capabilities=None,
    ) -> MediaInboxResult:
        return self.media_to_inbox(
            tenant_id=tenant_id,
            user_id=user_id,
            persona_id=persona_id,
            filename=filename,
            data=data,
            hint=hint,
            capabilities=capabilities,
        )
