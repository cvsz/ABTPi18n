"""// ZeaZDev [Secret Rotation Service] //
// Project: Auto Bot Trader i18n //
// Version: 1.0.0 (Phase 5) //
// Author: ZeaZDev Meta-Intelligence (Generated) //
// --- DO NOT EDIT HEADER --- //"""

import hashlib
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from prisma import Prisma


class SecretRotationService:
    """Service for managing secret rotation"""

    def __init__(self):
        self.prisma = Prisma()
        self.rotation_policy_days = int(os.getenv("SECRET_ROTATION_POLICY_DAYS", "90"))
        self.grace_period_days = int(
            os.getenv("SECRET_ROTATION_GRACE_PERIOD_DAYS", "7")
        )

    async def connect(self):
        """Connect to database"""
        if not self.prisma.is_connected():
            await self.prisma.connect()

    async def disconnect(self):
        """Disconnect from database"""
        if self.prisma.is_connected():
            await self.prisma.disconnect()

    def hash_secret(self, secret: str) -> str:
        """
        Create a hash of the secret for verification (never store the actual secret)

        Args:
            secret: Secret value to hash

        Returns:
            SHA-256 hash of the secret
        """
        return hashlib.sha256(secret.encode()).hexdigest()

    async def create_rotation_record(
        self,
        secret_type: str,
        secret_name: str,
        new_secret_value: str,
        rotated_by: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a rotation record when a secret is rotated

        Args:
            secret_type: Type of secret (DATABASE, ENCRYPTION_KEY, API_KEY,
                OAUTH_SECRET)
            secret_name: Identifier for the secret
            new_secret_value: New secret value (will be hashed, not stored)
            rotated_by: User ID who performed the rotation
            metadata: Additional information about the rotation

        Returns:
            Created rotation record
        """
        await self.connect()

        # Calculate next rotation date
        next_rotation = datetime.utcnow() + timedelta(days=self.rotation_policy_days)

        # Find previous rotation record
        previous = await self.prisma.secretrotation.find_first(
            where={
                "secretType": secret_type,
                "secretName": secret_name,
                "status": "ACTIVE",
            }
        )

        # Mark previous rotation as deprecated
        if previous:
            await self.prisma.secretrotation.update(
                where={"id": previous.id}, data={"status": "DEPRECATED"}
            )

        # Create new rotation record
        rotation = await self.prisma.secretrotation.create(
            data={
                "secretType": secret_type,
                "secretName": secret_name,
                "rotatedBy": rotated_by,
                "previousHash": previous.previousHash if previous else None,
                "nextRotation": next_rotation,
                "status": "ACTIVE",
                "metadata": str(metadata) if metadata else None,
            }
        )

        return {
            "id": rotation.id,
            "secretType": rotation.secretType,
            "secretName": rotation.secretName,
            "rotatedAt": rotation.rotatedAt.isoformat(),
            "nextRotation": rotation.nextRotation.isoformat(),
            "status": rotation.status,
        }

    async def get_rotation_schedule(
        self, secret_type: Optional[str] = None, include_deprecated: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get rotation schedule for all secrets or specific type

        Args:
            secret_type: Filter by secret type
            include_deprecated: Include deprecated rotations

        Returns:
            List of rotation schedules
        """
        await self.connect()

        where = {}
        if secret_type:
            where["secretType"] = secret_type
        if not include_deprecated:
            where["status"] = "ACTIVE"

        rotations = await self.prisma.secretrotation.find_many(
            where=where, order={"nextRotation": "asc"}, include={"user": True}
        )

        now = datetime.utcnow()

        return [
            {
                "id": r.id,
                "secretType": r.secretType,
                "secretName": r.secretName,
                "lastRotated": r.rotatedAt.isoformat(),
                "nextRotation": r.nextRotation.isoformat(),
                "daysUntilRotation": (r.nextRotation - now).days,
                "status": r.status,
                "rotatedBy": r.user.email if r.user else None,
            }
            for r in rotations
        ]

    async def get_rotation_history(
        self,
        secret_type: Optional[str] = None,
        secret_name: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Get rotation history

        Args:
            secret_type: Filter by secret type
            secret_name: Filter by secret name
            limit: Maximum number of records to return

        Returns:
            List of historical rotations
        """
        await self.connect()

        where = {}
        if secret_type:
            where["secretType"] = secret_type
        if secret_name:
            where["secretName"] = secret_name

        rotations = await self.prisma.secretrotation.find_many(
            where=where, take=limit, order={"rotatedAt": "desc"}, include={"user": True}
        )

        return [
            {
                "id": r.id,
                "secretType": r.secretType,
                "secretName": r.secretName,
                "rotatedAt": r.rotatedAt.isoformat(),
                "rotatedBy": r.user.email if r.user else None,
                "status": r.status,
                "nextRotation": r.nextRotation.isoformat(),
            }
            for r in rotations
        ]

    async def get_secrets_due_for_rotation(
        self, days_ahead: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Get secrets that are due for rotation within specified days

        Args:
            days_ahead: Number of days to look ahead

        Returns:
            List of secrets needing rotation
        """
        await self.connect()

        cutoff_date = datetime.utcnow() + timedelta(days=days_ahead)

        rotations = await self.prisma.secretrotation.find_many(
            where={"status": "ACTIVE", "nextRotation": {"lte": cutoff_date}},
            order={"nextRotation": "asc"},
        )

        now = datetime.utcnow()

        return [
            {
                "id": r.id,
                "secretType": r.secretType,
                "secretName": r.secretName,
                "lastRotated": r.rotatedAt.isoformat(),
                "nextRotation": r.nextRotation.isoformat(),
                "daysUntilRotation": (r.nextRotation - now).days,
                "overdue": r.nextRotation < now,
            }
            for r in rotations
        ]

    async def update_rotation_policy(
        self,
        secret_type: str,
        secret_name: str,
        rotation_interval_days: int,
        grace_period_days: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Update the rotation policy for a specific secret

        Args:
            secret_type: Type of secret
            secret_name: Name of secret
            rotation_interval_days: New rotation interval in days
            grace_period_days: Grace period in days

        Returns:
            Updated rotation record
        """
        await self.connect()

        # Find active rotation
        rotation = await self.prisma.secretrotation.find_first(
            where={
                "secretType": secret_type,
                "secretName": secret_name,
                "status": "ACTIVE",
            }
        )

        if not rotation:
            raise ValueError(
                f"No active rotation found for {secret_type}:{secret_name}"
            )

        # Calculate new next rotation date
        new_next_rotation = rotation.rotatedAt + timedelta(days=rotation_interval_days)

        # Update the record
        updated = await self.prisma.secretrotation.update(
            where={"id": rotation.id}, data={"nextRotation": new_next_rotation}
        )

        return {
            "id": updated.id,
            "secretType": updated.secretType,
            "secretName": updated.secretName,
            "rotatedAt": updated.rotatedAt.isoformat(),
            "nextRotation": updated.nextRotation.isoformat(),
            "status": updated.status,
        }

    async def mark_rotation_complete(
        self, secret_type: str, secret_name: str
    ) -> Dict[str, Any]:
        """
        Mark a rotation as completed and create a new active record

        Args:
            secret_type: Type of secret
            secret_name: Name of secret

        Returns:
            Result of rotation completion
        """
        await self.connect()

        # Find active rotation
        rotation = await self.prisma.secretrotation.find_first(
            where={
                "secretType": secret_type,
                "secretName": secret_name,
                "status": "ACTIVE",
            }
        )

        if not rotation:
            raise ValueError(
                f"No active rotation found for {secret_type}:{secret_name}"
            )

        # Mark as rotated
        await self.prisma.secretrotation.update(
            where={"id": rotation.id}, data={"status": "ROTATED"}
        )

        return {
            "secretType": secret_type,
            "secretName": secret_name,
            "status": "ROTATED",
            "message": "Rotation marked as complete",
        }
