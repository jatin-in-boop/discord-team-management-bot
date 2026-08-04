from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    BigInteger, String, Boolean, DateTime, ForeignKey, JSON, Enum as SQLEnum, UniqueConstraint, Index
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.engine import Base
import enum


class RoleType(str, enum.Enum):
    TEAM = "team"
    TEAM_LEADER = "team_leader"


class ChannelType(str, enum.Enum):
    PLAN = "plan"
    DISCUSSION = "discussion"
    OPPONENTS = "opponents"
    PLAYERS = "players"


class Guild(Base):
    __tablename__ = "guilds"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    configurations: Mapped[List["GuildConfiguration"]] = relationship(back_populates="guild", cascade="all, delete-orphan")
    teams: Mapped[List["Team"]] = relationship(back_populates="guild", cascade="all, delete-orphan")
    roles: Mapped[List["Role"]] = relationship(back_populates="guild", cascade="all, delete-orphan")
    channels: Mapped[List["Channel"]] = relationship(back_populates="guild", cascade="all, delete-orphan")
    audit_logs: Mapped[List["AuditLog"]] = relationship(back_populates="guild", cascade="all, delete-orphan")


class GuildConfiguration(Base):
    __tablename__ = "guild_configurations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("guilds.guild_id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    management_category_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    management_channel_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    management_message_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    setup_complete: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    bot_version: Mapped[str] = mapped_column(String(50), nullable=False)
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    guild: Mapped["Guild"] = relationship(back_populates="configurations")


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("guilds.guild_id", ondelete="CASCADE"), nullable=False, index=True)
    team_number: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sp_range: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    category_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    team_role_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    team_leader_role_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    plan_channel_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    discussion_channel_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    opponents_channel_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    players_channel_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    guild: Mapped["Guild"] = relationship(back_populates="teams")
    members: Mapped[List["TeamMember"]] = relationship(back_populates="team", cascade="all, delete-orphan")
    roles: Mapped[List["Role"]] = relationship(back_populates="team", cascade="all, delete-orphan")
    channels: Mapped[List["Channel"]] = relationship(back_populates="team", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("guild_id", "team_number", name="uq_guild_team_number"),
        Index("ix_team_guild_number", "guild_id", "team_number"),
    )


class Player(Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    team_memberships: Mapped[List["TeamMember"]] = relationship(back_populates="player", cascade="all, delete-orphan")


class TeamMember(Base):
    __tablename__ = "team_members"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)
    player_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("players.id", ondelete="CASCADE"), nullable=False, index=True)
    is_team_leader: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    team: Mapped["Team"] = relationship(back_populates="members")
    player: Mapped["Player"] = relationship(back_populates="team_memberships")

    __table_args__ = (
        UniqueConstraint("team_id", "player_id", name="uq_team_player"),
    )


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("guilds.guild_id", ondelete="CASCADE"), nullable=False, index=True)
    team_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("teams.id", ondelete="CASCADE"), nullable=True, index=True)
    discord_role_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    role_type: Mapped[RoleType] = mapped_column(SQLEnum(RoleType), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    guild: Mapped["Guild"] = relationship(back_populates="roles")
    team: Mapped[Optional["Team"]] = relationship(back_populates="roles")


class Channel(Base):
    __tablename__ = "channels"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("guilds.guild_id", ondelete="CASCADE"), nullable=False, index=True)
    team_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("teams.id", ondelete="CASCADE"), nullable=True, index=True)
    discord_channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    channel_type: Mapped[ChannelType] = mapped_column(SQLEnum(ChannelType), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    guild: Mapped["Guild"] = relationship(back_populates="channels")
    team: Mapped[Optional["Team"]] = relationship(back_populates="channels")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("guilds.guild_id", ondelete="CASCADE"), nullable=False, index=True)
    executor_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    audit_metadata: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    guild: Mapped["Guild"] = relationship(back_populates="audit_logs")


class BotMetadata(Base):
    __tablename__ = "bot_metadata"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
