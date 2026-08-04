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


class RoleSource(str, enum.Enum):
    EXISTING = "existing"
    BOT_CREATED = "bot_created"


class PresentationMode(str, enum.Enum):
    BUTTONS = "buttons"
    SELECT = "select"
    REACTIONS = "reactions"


class SelectionMode(str, enum.Enum):
    MULTIPLE = "multiple"
    SINGLE = "single"


class TogglePolicy(str, enum.Enum):
    REMOVE = "remove"
    STRICT = "strict"


class ManagedRoleOwnerType(str, enum.Enum):
    REACTION_PANEL = "reaction_panel"
    PULSE_BAND = "pulse_band"
    PULSE_REWARD = "pulse_reward"


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
    community_settings: Mapped[Optional["CommunitySettings"]] = relationship(
        back_populates="guild", cascade="all, delete-orphan", uselist=False
    )
    reaction_role_panels: Mapped[List["ReactionRolePanel"]] = relationship(
        back_populates="guild", cascade="all, delete-orphan"
    )
    managed_roles: Mapped[List["ManagedRoleRegistry"]] = relationship(
        back_populates="guild", cascade="all, delete-orphan"
    )


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


class CommunitySettings(Base):
    __tablename__ = "community_settings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("guilds.guild_id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    welcome_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    welcome_channel_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    welcome_message_config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    goodbye_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    goodbye_channel_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    goodbye_message_config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    welcome_status: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    goodbye_status: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    updated_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    guild: Mapped["Guild"] = relationship(back_populates="community_settings")


class ReactionRolePanel(Base):
    __tablename__ = "reaction_role_panels"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("guilds.guild_id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    message_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    presentation_mode: Mapped[PresentationMode] = mapped_column(
        SQLEnum(PresentationMode), default=PresentationMode.BUTTONS, nullable=False
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(String(4000), nullable=False)
    appearance: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    needs_repair: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    repair_status: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    guild: Mapped["Guild"] = relationship(back_populates="reaction_role_panels")
    groups: Mapped[List["ReactionRoleGroup"]] = relationship(
        back_populates="panel", cascade="all, delete-orphan", order_by="ReactionRoleGroup.sort_order"
    )
    options: Mapped[List["ReactionRoleOption"]] = relationship(
        back_populates="panel", cascade="all, delete-orphan", order_by="ReactionRoleOption.sort_order"
    )

    __table_args__ = (
        UniqueConstraint("guild_id", "message_id", name="uq_reaction_panel_guild_message"),
    )


class ReactionRoleGroup(Base):
    __tablename__ = "reaction_role_groups"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    panel_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("reaction_role_panels.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    selection_mode: Mapped[SelectionMode] = mapped_column(
        SQLEnum(SelectionMode), default=SelectionMode.MULTIPLE, nullable=False
    )
    toggle_policy: Mapped[TogglePolicy] = mapped_column(
        SQLEnum(TogglePolicy), default=TogglePolicy.REMOVE, nullable=False
    )
    required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    max_selections: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    sort_order: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)

    panel: Mapped["ReactionRolePanel"] = relationship(back_populates="groups")
    options: Mapped[List["ReactionRoleOption"]] = relationship(back_populates="group")


class ReactionRoleOption(Base):
    __tablename__ = "reaction_role_options"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    panel_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("reaction_role_panels.id", ondelete="CASCADE"), nullable=False, index=True
    )
    group_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("reaction_role_groups.id", ondelete="SET NULL"), nullable=True, index=True
    )
    role_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    role_source: Mapped[RoleSource] = mapped_column(
        SQLEnum(RoleSource), default=RoleSource.EXISTING, nullable=False
    )
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    emoji: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    sort_order: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    removable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    brand_config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    managed_role_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    panel: Mapped["ReactionRolePanel"] = relationship(back_populates="options")
    group: Mapped[Optional["ReactionRoleGroup"]] = relationship(back_populates="options")

    __table_args__ = (
        UniqueConstraint("panel_id", "role_id", name="uq_reaction_panel_role"),
    )


class ManagedRoleRegistry(Base):
    __tablename__ = "managed_role_registry"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("guilds.guild_id", ondelete="CASCADE"), nullable=False, index=True
    )
    discord_role_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True, index=True)
    owner_type: Mapped[ManagedRoleOwnerType] = mapped_column(
        SQLEnum(ManagedRoleOwnerType), nullable=False
    )
    owner_record_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    generated_name: Mapped[str] = mapped_column(String(100), nullable=False)
    brand_tag: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    color: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    symbol: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    creation_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_sync_status: Mapped[str] = mapped_column(String(50), default="synced", nullable=False)
    last_sync_error: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    guild: Mapped["Guild"] = relationship(back_populates="managed_roles")
