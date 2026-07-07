# Copyright (c) 2026, RaceDog Technologies and contributors
"""Self-healing install/migrate setup.

Wiring role/permlevel permissions and indexes through ``after_install`` and
``after_migrate`` (rather than only a one-shot patch) makes them idempotent and
resilient: they run AFTER fixtures every time, so a fixture error early in
install can never leave the permission rows half-applied.
"""

import frappe

from racedog_hr.patches.v0_0_1.add_indexes import execute as _add_indexes
from racedog_hr.patches.v0_0_1.setup_roles_and_permissions import execute as _setup_permissions


def after_install() -> None:
	_apply()


def after_migrate() -> None:
	_apply()


def _apply() -> None:
	_setup_permissions()
	_add_indexes()
	frappe.db.commit()
	frappe.clear_cache()
