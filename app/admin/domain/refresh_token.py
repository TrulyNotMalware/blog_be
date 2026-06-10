import datetime as dt
from typing import Literal

from sqlalchemy import DateTime, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.session import Base

RefreshStatus = Literal["active", "rotated", "revoked"]


class RefreshToken(Base):
    """One row per issued refresh token (rotating-jti token family).

    State machine: active -> rotated (normal refresh) or active -> revoked
    (logout / reuse-detection family revocation). A `rotated` jti replayed on
    /refresh means the token was already exchanged once — treated as theft and
    revokes the whole subject family. Expired `active` rows are treated as
    invalid at lookup time; pruning them is a future cron (no scheduler here).
    """

    __tablename__ = "refresh_tokens"

    jti: Mapped[str] = mapped_column(String, primary_key=True)
    subject: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(
        String, nullable=False, default="active", server_default="active"
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    __table_args__ = (Index("ix_refresh_tokens_subject", "subject"),)
