"""User management commands for Sparky CLI."""

import getpass
import os
from typing import Optional

import typer
from rich.table import Table

from cli.common import console, logger
from utils.async_util import run_async

user = typer.Typer(name="user", help="Manage users and passwords")


async def _get_db_url() -> str:
    """Resolve database URL from environment."""
    db_url = os.getenv("SPARKY_DB_URL")
    if not db_url:
        raise typer.BadParameter(
            "SPARKY_DB_URL environment variable is not set. "
            "Inside Docker this is set automatically; on the host use the compose DB URL "
            "(e.g. postgresql://user:pass@localhost:9433/sparky_db)."
        )
    return db_url


async def _with_user_service(callback):
    """Run an async callback with a connected UserManagementService."""
    from database.database import get_database_manager
    from services.user_management_service import UserManagementService

    db_url = await _get_db_url()
    db_manager = get_database_manager(db_url=db_url)
    await db_manager.connect()
    try:
        async with db_manager.SessionLocal() as session:
            service = UserManagementService(session)
            return await callback(service)
    finally:
        await db_manager.close()


async def _resolve_user(service, username_or_email: str):
    """Find a user by username or email."""
    user_obj = await service.get_user_by_username(username_or_email)
    if not user_obj:
        user_obj = await service.get_user_by_email(username_or_email)
    return user_obj


def _prompt_password(prompt: str = "New password") -> str:
    """Prompt for a password twice, or fail clearly in non-interactive mode."""
    try:
        password = getpass.getpass(f"{prompt}: ")
        confirm = getpass.getpass("Confirm password: ")
    except (EOFError, OSError) as exc:
        raise typer.BadParameter(
            "Cannot read password interactively. Pass --password explicitly, "
            "or run with a TTY (e.g. docker exec -it ...)."
        ) from exc

    if not password:
        raise typer.BadParameter("Password cannot be empty")
    if password != confirm:
        raise typer.BadParameter("Passwords do not match")
    if len(password) < 8:
        raise typer.BadParameter("Password must be at least 8 characters")
    return password


@user.command("list")
def list_users(
    limit: int = typer.Option(100, "--limit", "-n", help="Maximum users to show"),
    active_only: bool = typer.Option(
        False, "--active-only", help="Only show active users"
    ),
):
    """List users in the database."""

    async def _list(service):
        users = await service.list_users(
            limit=limit, is_active=True if active_only else None
        )
        rows = []
        for u in users:
            roles = await service.get_user_roles(u.id)
            rows.append(
                (
                    u.username,
                    u.email,
                    "yes" if u.is_active else "no",
                    "yes" if u.is_verified else "no",
                    ", ".join(roles) or "-",
                    u.last_login.isoformat(sep=" ", timespec="seconds")
                    if u.last_login
                    else "-",
                    u.id,
                )
            )
        return rows

    rows = run_async(_with_user_service(_list))
    if not rows:
        logger.info("No users found")
        return

    table = Table(title="Users")
    table.add_column("Username")
    table.add_column("Email")
    table.add_column("Active")
    table.add_column("Verified")
    table.add_column("Roles")
    table.add_column("Last login")
    table.add_column("ID")
    for row in rows:
        table.add_row(*row)
    console.print(table)


@user.command("info")
def user_info(
    username_or_email: str = typer.Argument(
        ..., help="Username or email of the user to show"
    ),
):
    """Show details for a single user."""

    async def _info(service):
        user_obj = await _resolve_user(service, username_or_email)
        if not user_obj:
            return None
        roles = await service.get_user_roles(user_obj.id)
        return user_obj, roles

    result = run_async(_with_user_service(_info))
    if not result:
        logger.error(f"User not found: {username_or_email}")
        raise typer.Exit(1)

    user_obj, roles = result
    logger.info(f"Username:   {user_obj.username}")
    logger.info(f"Email:      {user_obj.email}")
    logger.info(f"ID:         {user_obj.id}")
    logger.info(f"Active:     {user_obj.is_active}")
    logger.info(f"Verified:   {user_obj.is_verified}")
    logger.info(f"Roles:      {', '.join(roles) or '(none)'}")
    logger.info(f"Created:    {user_obj.created_at}")
    logger.info(f"Last login: {user_obj.last_login or 'never'}")


@user.command("set-password")
def set_password(
    username_or_email: str = typer.Argument(
        ..., help="Username or email of the user"
    ),
    password: Optional[str] = typer.Option(
        None,
        "--password",
        "-p",
        help="New password (omit to prompt securely)",
    ),
):
    """Reset a user's password (admin / ops use; does not require old password)."""
    new_password = password if password is not None else _prompt_password()
    if password is not None:
        if len(password) < 8:
            logger.error("Password must be at least 8 characters")
            raise typer.Exit(1)

    async def _reset(service):
        user_obj = await _resolve_user(service, username_or_email)
        if not user_obj:
            return None, "not_found"
        updated = await service.update_user(user_obj.id, password=new_password)
        return updated, "ok" if updated else "failed"

    updated, status = run_async(_with_user_service(_reset))
    if status == "not_found":
        logger.error(f"User not found: {username_or_email}")
        raise typer.Exit(1)
    if status != "ok":
        logger.error("Failed to update password")
        raise typer.Exit(1)

    logger.info(
        f"✓ Password updated for {updated.username} ({updated.email})"
    )


@user.command("assign-role")
def assign_role(
    username_or_email: str = typer.Argument(
        ..., help="Username or email of the user"
    ),
    role: str = typer.Argument(..., help="Role to assign (e.g. admin, user)"),
):
    """Assign a role to a user."""

    async def _assign(service):
        user_obj = await _resolve_user(service, username_or_email)
        if not user_obj:
            return None, False
        success = await service.assign_role(user_obj.id, role)
        return user_obj, success

    user_obj, success = run_async(_with_user_service(_assign))
    if not user_obj:
        logger.error(f"User not found: {username_or_email}")
        raise typer.Exit(1)
    if not success:
        logger.error(f"Failed to assign role '{role}' to {user_obj.username}")
        raise typer.Exit(1)
    logger.info(f"✓ Assigned role '{role}' to {user_obj.username}")
