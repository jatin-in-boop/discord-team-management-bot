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


class PulsePacing(str, enum.Enum):
    RELAXED = "relaxed"
    BALANCED = "balanced"
    AMBITIOUS = "ambitious"


class XPSource(str, enum.Enum):
    MESSAGE = "message"
    VOICE = "voice"
    REACTION = "reaction"
    EVENT = "event"
    MANUAL = "manual"


class GiveawayStatus(str, enum.Enum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    LIVE = "live"
    ENDING = "ending"
    WINNER_PENDING_CLAIM = "winner_pending_claim"
    COMPLETED = "completed"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    FAILED_REPAIR = "failed_repair"


class GiveawayEntryMode(str, enum.Enum):
    BUTTON = "button"
    REACTION = "reaction"


class ClaimStatus(str, enum.Enum):
    PENDING = "pending"
    CLAIMED = "claimed"
    EXPIRED = "expired"
    FULFILLED_MANUALLY = "fulfilled_manually"


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
    pulse_settings: Mapped[Optional["PulseSettings"]] = relationship(
        back_populates="guild", cascade="all, delete-orphan", uselist=False
    )
    pulse_members: Mapped[List["PulseMember"]] = relationship(
        back_populates="guild", cascade="all, delete-orphan"
    )
    pulse_seasons: Mapped[List["PulseSeason"]] = relationship(
        back_populates="guild", cascade="all, delete-orphan"
    )
    giveaways: Mapped[List["Giveaway"]] = relationship(
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


class PulseSettings(Base):
    __tablename__ = "pulse_settings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("guilds.guild_id", ondelete="CASCADE"),
        unique=True, nullable=False, index=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    display_name: Mapped[str] = mapped_column(String(50), default="Pulse", nullable=False)
    pacing: Mapped[PulsePacing] = mapped_column(
        SQLEnum(PulsePacing), default=PulsePacing.BALANCED, nullable=False
    )
    max_level: Mapped[int] = mapped_column(BigInteger, default=100, nullable=False)
    enabled_sources: Mapped[list] = mapped_column(
        JSON, default=lambda: [XPSource.MESSAGE.value], nullable=False
    )
    source_config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    announcement_channel_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    announcement_mode: Mapped[str] = mapped_column(
        String(30), default="milestones", nullable=False
    )
    leaderboard_channel_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    leaderboard_message_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    leaderboard_scope: Mapped[str] = mapped_column(String(30), default="all_time", nullable=False)
    leaderboard_refresh_interval: Mapped[int] = mapped_column(
        BigInteger, default=300, nullable=False
    )
    leaderboard_last_attempt_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    leaderboard_last_success_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    leaderboard_rendered: Mapped[Optional[str]] = mapped_column(String(6000), nullable=True)
    brand_config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    band_config: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    updated_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    guild: Mapped["Guild"] = relationship(back_populates="pulse_settings")


class PulseMember(Base):
    __tablename__ = "pulse_members"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("guilds.guild_id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    member_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    total_xp: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    current_season_xp: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    current_level: Mapped[int] = mapped_column(BigInteger, default=1, nullable=False)
    last_activity_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_rank: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    seven_day_xp: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    guild: Mapped["Guild"] = relationship(back_populates="pulse_members")
    ledger: Mapped[List["XPLedger"]] = relationship(
        back_populates="member", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("guild_id", "member_id", name="uq_pulse_guild_member"),
    )


class XPLedger(Base):
    __tablename__ = "xp_ledger"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("guilds.guild_id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    member_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    pulse_member_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("pulse_members.id", ondelete="CASCADE"), nullable=False
    )
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source: Mapped[XPSource] = mapped_column(SQLEnum(XPSource), nullable=False)
    source_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    reversal_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    member: Mapped["PulseMember"] = relationship(back_populates="ledger")


class PulseSeason(Base):
    __tablename__ = "pulse_seasons"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("guilds.guild_id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="active", nullable=False)
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    guild: Mapped["Guild"] = relationship(back_populates="pulse_seasons")


class PulseReward(Base):
    __tablename__ = "pulse_rewards"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("guilds.guild_id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    threshold: Mapped[int] = mapped_column(BigInteger, nullable=False)
    band_key: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    role_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    role_source: Mapped[RoleSource] = mapped_column(
        SQLEnum(RoleSource), default=RoleSource.EXISTING, nullable=False
    )
    brand_config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    mutually_exclusive_group: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("guild_id", "kind", "threshold", name="uq_pulse_reward_threshold"),
    )


class Giveaway(Base):
    __tablename__ = "giveaways"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("guilds.guild_id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    message_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    prize_description: Mapped[str] = mapped_column(String(4000), nullable=False)
    organizer_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sponsor_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[GiveawayStatus] = mapped_column(
        SQLEnum(GiveawayStatus), default=GiveawayStatus.DRAFT, nullable=False, index=True
    )
    start_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    claim_window_seconds: Mapped[int] = mapped_column(BigInteger, default=86400, nullable=False)
    winner_count: Mapped[int] = mapped_column(BigInteger, default=1, nullable=False)
    entry_mode: Mapped[GiveawayEntryMode] = mapped_column(
        SQLEnum(GiveawayEntryMode), default=GiveawayEntryMode.BUTTON, nullable=False
    )
    eligibility_config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    presentation_config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    organizer_acknowledged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    cancelled_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    guild: Mapped["Guild"] = relationship(back_populates="giveaways")
    entries: Mapped[List["GiveawayEntry"]] = relationship(
        back_populates="giveaway", cascade="all, delete-orphan"
    )
    draws: Mapped[List["GiveawayDraw"]] = relationship(
        back_populates="giveaway", cascade="all, delete-orphan"
    )


class GiveawayEntry(Base):
    __tablename__ = "giveaway_entries"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    giveaway_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("giveaways.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    member_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    entry_weight: Mapped[int] = mapped_column(BigInteger, default=1, nullable=False)
    eligibility_status: Mapped[str] = mapped_column(String(30), default="eligible", nullable=False)
    eligibility_failure_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    entered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    last_revalidated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    giveaway: Mapped["Giveaway"] = relationship(back_populates="entries")

    __table_args__ = (
        UniqueConstraint("giveaway_id", "member_id", name="uq_giveaway_member_entry"),
    )


class GiveawayDraw(Base):
    __tablename__ = "giveaway_draws"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    giveaway_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("giveaways.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    draw_number: Mapped[int] = mapped_column(BigInteger, nullable=False)
    draw_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    eligible_entry_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    winner_order: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    seed_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    reveal_seed: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    reason: Mapped[str] = mapped_column(String(255), default="scheduled_end", nullable=False)
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)

    giveaway: Mapped["Giveaway"] = relationship(back_populates="draws")
    winners: Mapped[List["GiveawayWinner"]] = relationship(
        back_populates="draw", cascade="all, delete-orphan"
    )


class GiveawayWinner(Base):
    __tablename__ = "giveaway_winners"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    draw_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("giveaway_draws.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    giveaway_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    member_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    position: Mapped[int] = mapped_column(BigInteger, nullable=False)
    claim_status: Mapped[ClaimStatus] = mapped_column(
        SQLEnum(ClaimStatus), default=ClaimStatus.PENDING, nullable=False
    )
    claim_deadline: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    claimed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    expired_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    replacement_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    draw: Mapped["GiveawayDraw"] = relationship(back_populates="winners")
