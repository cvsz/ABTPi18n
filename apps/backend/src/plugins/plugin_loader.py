"""// ZeaZDev [Plugin Loader Service] //
// Project: Auto Bot Trader i18n //
// Version: 1.0.0 (Phase 4) //
// Author: ZeaZDev Meta-Intelligence (Generated) //
// --- DO NOT EDIT HEADER --- //"""

import importlib
import importlib.metadata
import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type

from prisma import Prisma

logger = logging.getLogger(__name__)


class PluginInterface(ABC):
    """Base interface for all plugins"""

    name: str = "base_plugin"
    version: str = "1.0.0"
    type: str = "STRATEGY"  # STRATEGY, INDICATOR, NOTIFICATION, DATASOURCE
    description: str = ""
    author: str = ""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(f"plugin.{self.name}")

    @abstractmethod
    def initialize(self):
        """Called when plugin is loaded"""
        pass

    @abstractmethod
    def cleanup(self):
        """Called when plugin is unloaded"""
        pass


class StrategyPlugin(PluginInterface):
    """Base class for strategy plugins"""

    type: str = "STRATEGY"

    @abstractmethod
    def on_candle(self, candle: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Called on each new candle

        Args:
            candle: Dict with OHLCV data

        Returns:
            Dict with action (BUY/SELL) and quantity, or None
        """
        pass


class IndicatorPlugin(PluginInterface):
    """Base class for indicator plugins"""

    type: str = "INDICATOR"

    @abstractmethod
    def calculate(self, data: List[float]) -> float:
        """
        Calculate indicator value

        Args:
            data: List of price data

        Returns:
            Indicator value
        """
        pass


class PluginLoader:
    """Service for loading and managing plugins"""

    def __init__(self):
        self.prisma = Prisma()
        self.loaded_plugins: Dict[str, Type[PluginInterface]] = {}
        self.plugin_instances: Dict[str, PluginInterface] = {}
        self.verify_signatures = (
            os.getenv("PLUGIN_VERIFY_SIGNATURES", "false").lower() == "true"
        )

    def discover_plugins(self) -> List[Dict[str, Any]]:
        """
        Discover plugins using entry points

        Returns:
            List of discovered plugin information
        """
        discovered = []

        # Entry point groups to check
        entry_point_groups = [
            "abtpro.plugins.strategies",
            "abtpro.plugins.indicators",
            "abtpro.plugins.notifications",
            "abtpro.plugins.datasources",
        ]

        for group in entry_point_groups:
            try:
                # Python 3.10+
                entry_points = importlib.metadata.entry_points()
                if hasattr(entry_points, "select"):
                    # Python 3.10+ new API
                    eps = entry_points.select(group=group)
                else:
                    # Python 3.9 fallback
                    eps = entry_points.get(group, [])

                for ep in eps:
                    try:
                        plugin_class = ep.load()
                        discovered.append(
                            {
                                "name": plugin_class.name,
                                "version": plugin_class.version,
                                "type": plugin_class.type,
                                "description": plugin_class.description,
                                "author": plugin_class.author,
                                "entry_point": ep.value,
                            }
                        )
                        logger.info(
                            "Discovered plugin: %s v%s",
                            plugin_class.name,
                            plugin_class.version,
                        )
                    except Exception as e:
                        logger.error(
                            f"Failed to load plugin from entry point {ep.name}: {e}"
                        )
            except Exception as e:
                logger.error(f"Failed to discover plugins in group {group}: {e}")

        return discovered

    async def register_plugin(
        self,
        name: str,
        version: str,
        plugin_type: str,
        entry_point: str,
        author: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Register a plugin in the database"""
        await self.prisma.connect()

        try:
            # Check if plugin already exists
            existing = await self.prisma.plugin.find_first(where={"name": name})

            if existing:
                # Update existing plugin
                plugin = await self.prisma.plugin.update(
                    where={"id": existing.id},
                    data={
                        "version": version,
                        "type": plugin_type,
                        "entryPoint": entry_point,
                        "author": author,
                        "description": description,
                    },
                )
            else:
                # Create new plugin
                plugin = await self.prisma.plugin.create(
                    data={
                        "name": name,
                        "version": version,
                        "type": plugin_type,
                        "entryPoint": entry_point,
                        "author": author,
                        "description": description,
                        "verified": False,  # Manual verification required
                    }
                )

            return {
                "id": plugin.id,
                "name": plugin.name,
                "version": plugin.version,
                "type": plugin.type,
            }
        finally:
            await self.prisma.disconnect()

    async def install_plugin_for_user(
        self, user_id: int, plugin_name: str, config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Install a plugin for a specific user"""
        await self.prisma.connect()

        try:
            # Find plugin
            plugin = await self.prisma.plugin.find_first(where={"name": plugin_name})

            if not plugin:
                raise ValueError(f"Plugin not found: {plugin_name}")

            # Check if already installed
            existing = await self.prisma.userplugin.find_first(
                where={"userId": user_id, "pluginId": plugin.id}
            )

            if existing:
                # Update configuration
                user_plugin = await self.prisma.userplugin.update(
                    where={"id": existing.id},
                    data={
                        "config": json.dumps(config) if config else None,
                        "enabled": True,
                    },
                )
            else:
                # Create new installation
                user_plugin = await self.prisma.userplugin.create(
                    data={
                        "userId": user_id,
                        "pluginId": plugin.id,
                        "enabled": True,
                        "config": json.dumps(config) if config else None,
                    }
                )

            return {
                "user_plugin_id": user_plugin.id,
                "plugin_name": plugin.name,
                "enabled": user_plugin.enabled,
            }
        finally:
            await self.prisma.disconnect()

    async def toggle_plugin(self, user_plugin_id: int, enabled: bool) -> Dict[str, Any]:
        """Enable or disable a plugin for a user"""
        await self.prisma.connect()

        try:
            user_plugin = await self.prisma.userplugin.update(
                where={"id": user_plugin_id}, data={"enabled": enabled}
            )

            return {"user_plugin_id": user_plugin.id, "enabled": user_plugin.enabled}
        finally:
            await self.prisma.disconnect()

    async def get_user_plugins(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all plugins installed for a user"""
        await self.prisma.connect()

        try:
            user_plugins = await self.prisma.userplugin.find_many(
                where={"userId": user_id}, include={"plugin": True}
            )

            return [
                {
                    "user_plugin_id": up.id,
                    "plugin_name": up.plugin.name,
                    "plugin_version": up.plugin.version,
                    "plugin_type": up.plugin.type,
                    "enabled": up.enabled,
                    "config": json.loads(up.config) if up.config else {},
                }
                for up in user_plugins
            ]
        finally:
            await self.prisma.disconnect()

    def load_plugin(self, plugin_name: str, config: Dict[str, Any]) -> PluginInterface:
        """
        Load and instantiate a plugin

        Args:
            plugin_name: Name of plugin to load
            config: Configuration for plugin

        Returns:
            Instantiated plugin
        """
        if plugin_name in self.plugin_instances:
            return self.plugin_instances[plugin_name]

        # Try to load from entry points
        discovered = self.discover_plugins()
        plugin_info = next((p for p in discovered if p["name"] == plugin_name), None)

        if not plugin_info:
            raise ValueError(f"Plugin not found: {plugin_name}")

        # Load plugin class
        module_name, class_name = plugin_info["entry_point"].rsplit(":", 1)
        module = importlib.import_module(module_name)
        plugin_class = getattr(module, class_name)

        # Instantiate plugin
        plugin_instance = plugin_class(config)
        plugin_instance.initialize()

        # Cache instance
        self.plugin_instances[plugin_name] = plugin_instance

        logger.info(f"Loaded plugin: {plugin_name}")

        return plugin_instance

    def unload_plugin(self, plugin_name: str):
        """Unload a plugin"""
        if plugin_name in self.plugin_instances:
            plugin = self.plugin_instances[plugin_name]
            plugin.cleanup()
            del self.plugin_instances[plugin_name]
            logger.info(f"Unloaded plugin: {plugin_name}")

    async def list_available_plugins(self) -> List[Dict[str, Any]]:
        """List all available plugins from database"""
        await self.prisma.connect()

        try:
            plugins = await self.prisma.plugin.find_many()

            return [
                {
                    "id": p.id,
                    "name": p.name,
                    "version": p.version,
                    "type": p.type,
                    "author": p.author,
                    "description": p.description,
                    "verified": p.verified,
                }
                for p in plugins
            ]
        finally:
            await self.prisma.disconnect()
