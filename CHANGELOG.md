# Changelog

## [1.0.7] - 2026-09-05

### bUG
- freebox_api.py — Bug SSL

Le contexte SSL est maintenant créé via loop.run_in_executor() — plus de blocage de la boucle asyncio

- entity_base.py — Bug via_device

Suppression du via_device dans DeviceInfo des entités par appareil
Ce champ référençait le hub qui n'existe pas encore au moment de la création des entités, ce qui causait le warning HA 2025.12

### Changed
- Amélioration de XXX