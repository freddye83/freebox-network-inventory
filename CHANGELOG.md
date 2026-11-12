# Changelog
## [1.2.0] - 2026-11-12
### Added
- DHCP static leases: services `set_static_lease` / `remove_static_lease` (create, update, delete)
- Global sensor `sensor.freebox_network_inventory_static_leases` (count + `leases` attribute with the full list, DHCP range, gateway, netmask)
- Device attributes `static_lease`, `static_ip`, `static_lease_comment`
- Services translations (EN / FR)
### Fixed
- Translations moved to `custom_components/freebox_network_inventory/translations/` (they were not loaded by Home Assistant)
- Coordinators now receive the config entry explicitly (HA deprecation, "relies on ContextVar")
### Docs
- README in English (French version at the end), Home Assistant 2026.11 Marketplace installation, anonymised screenshot
- LICENSE file added (MIT, as stated in the README)
## [1.1.2] - 2026-10-04
### Changed
- sensor.py : ajout vitesses et erreurs
sensor.freebox_network_inventory_switch_port_1_appareils affichera 20 (le nombre) et la liste complète sera dans l’attribut liste.
- coordinator.py :
  - IPv4 : parmi toutes les adresses de l’appareil, l’intégration retient celle qui est joignable avec la last_activity la plus récente, au lieu de la première de la liste.
  - IPv6 : même règle, avec en plus une préférence pour une adresse globale (2a01:...) plutôt qu’une link-local (fe80::).
  - Attribut ip_list : les adresses sont maintenant triées de la plus récente à la plus ancienne, donc l’actuelle est toujours en premier.
## [1.1.1] - 2026-10-04
### Changed
- sensor.py : ajout vitesses et erreurs

## [1.1.0] - 2026-10-04
### Changed
- Ajout de la gestion du switch

## [1.0.7] - 2026-09-05

### bUG
- freebox_api.py — Bug SSL

Le contexte SSL est maintenant créé via loop.run_in_executor() — plus de blocage de la boucle asyncio

- entity_base.py — Bug via_device

Suppression du via_device dans DeviceInfo des entités par appareil
Ce champ référençait le hub qui n'existe pas encore au moment de la création des entités, ce qui causait le warning HA 2025.12

### Changed
- Amélioration de XXX