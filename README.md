# Freebox Network Inventory

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![HA Version](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-blue)](https://www.home-assistant.io/)
[![Version](https://img.shields.io/github/v/release/freddye83/freebox-network-inventory)](https://github.com/freddye83/freebox-network-inventory/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> Intégration Home Assistant pour l'inventaire réseau de la Freebox.  
> Complément à l'intégration officielle — orienté **inventaire** plutôt que présence.

![Screenshot](https://raw.githubusercontent.com/freddye83/freebox-network-inventory/main/docs/screenshot.png)

---

## Pourquoi cette intégration ?

L'intégration officielle Freebox crée des `device_tracker` pour la détection de présence.  
Ce besoin est très différent d'un **inventaire réseau** : connaître tous les équipements connectés, leur IP, leur fabricant, les détecter à leur première apparition, et pouvoir les renommer directement depuis Home Assistant.

**Freebox Network Inventory ne remplace pas l'intégration officielle — elle la complète.**

---

## Fonctionnalités

- ✅ **Un Device HA par adresse MAC** (Paramètres → Appareils)
- ✅ **4 entités par appareil** : statut, présence en ligne, nom éditable, type éditable
- ✅ **Modification du nom et du type répercutée sur Freebox OS** en temps réel
- ✅ **Tous les détails en attributs** : IPv4, IPv6, fabricant, type, domaine, point d'accès, timestamps
- ✅ **3 capteurs globaux** : total, en ligne, nouveaux appareils
- ✅ **Notification automatique** à chaque nouvel équipement détecté
- ✅ **Événement HA** `freebox_network_inventory_new_device` pour les automatisations
- ✅ **Page Diagnostics** intégrée
- ✅ **Config Flow** (pas de YAML)
- ✅ **Intervalle configurable** (10–3600 s, défaut 60 s)
- ✅ **Traductions FR / EN**
- ✅ Compatible Home Assistant 2024.1+
- ✅ **Aucun `device_tracker` créé**

---

## Installation via HACS

1. Ouvrez **HACS** dans Home Assistant
2. **Intégrations** → menu ⋮ → **Dépôts personnalisés**
3. URL : `https://github.com/freddye83/freebox-network-inventory`
4. Catégorie : **Intégration** → **Ajouter**
5. Recherchez **Freebox Network Inventory** et installez
6. Redémarrez Home Assistant

## Installation manuelle

1. Téléchargez la dernière [release](https://github.com/freddye83/freebox-network-inventory/releases)
2. Copiez le dossier `custom_components/freebox_network_inventory` dans `/config/custom_components/`
3. Redémarrez Home Assistant

---

## Configuration

1. **Paramètres → Appareils et services → Ajouter une intégration**
2. Recherchez **Freebox Network Inventory**
3. Saisissez l'adresse de votre Freebox (`mafreebox.freebox.fr` par défaut)
4. **Appuyez sur le bouton fléché** sur l'écran LCD de la Freebox pour autoriser l'accès
5. Cliquez **Soumettre** ✅

> **Note :** L'intégration demande les droits `settings` et `lan` pour pouvoir modifier les noms et types des équipements depuis HA.

---

## Entités créées

### Par appareil réseau

```
Samsung TV  (D0:D0:03:B0:0A:36)
│
├── binary_sensor.freebox_network_inventory_tv_salon_tizen_en_ligne
│     state : on / off
│
├── sensor.freebox_network_inventory_tv_salon_tizen
│     state : online / offline
│     attributes :
│       mac, ipv4, ipv6, ip_list, ip_count
│       vendor, hostname, alias, host_type
│       domain_name, access_point_mac, ap_speed_mbps
│       reachable, active, persistent
│       first_seen, last_seen, last_activity
│
├── text.freebox_network_inventory_tv_salon_tizen_nom
│     Nom modifiable → répercuté sur Freebox OS
│
└── select.freebox_network_inventory_tv_salon_tizen_type
      Type modifiable (Téléviseur, Smartphone, NAS...) → répercuté sur Freebox OS
```

### Capteurs globaux (Hub)

```
Freebox Network Inventory
├── sensor.freebox_network_inventory_devices_online    → 44
├── sensor.freebox_network_inventory_devices_total     → 66
└── sensor.freebox_network_inventory_devices_new       → 0
```

---

## Notification nouveaux équipements

À chaque nouvel équipement détecté sur le réseau, une notification persistante est créée dans HA :

> **🔍 Nouvel équipement réseau détecté**  
> Nom : ESP32 Garage  
> MAC : 28:56:2F:74:CA:08  
> Fabricant : Espressif Inc.  
> Type : Équipement réseau  
> IP : 192.168.1.92

Un événement `freebox_network_inventory_new_device` est aussi déclenché, exploitable dans les automatisations :

```yaml
automation:
  alias: "Nouvel équipement réseau"
  trigger:
    - platform: event
      event_type: freebox_network_inventory_new_device
  action:
    - service: notify.mobile_app_mon_telephone
      data:
        title: "🔍 Nouvel appareil réseau"
        message: >
          {{ trigger.event.data.name }}
          — {{ trigger.event.data.vendor or 'Inconnu' }}
          — {{ trigger.event.data.ip }}
          ({{ trigger.event.data.mac }})
```

---

## Carte Lovelace associée

Une carte dédiée est disponible dans le dépôt [freebox-network-inventory-card](https://github.com/freddye83/freebox-network-inventory-card) :

- Tableau filtrable, triable, paginé
- Recherche en temps réel
- Popup modal avec modification du nom et du type directement depuis la carte

---

## Diagnostics

**Paramètres → Appareils et services → Freebox Network Inventory → Télécharger les diagnostics**

```json
{
  "summary": {
    "total_devices": 66,
    "online": 44,
    "offline": 22,
    "unknown_vendor": 8,
    "new_devices_last_poll": 0
  }
}
```

---

## API Freebox utilisée

| Endpoint | Description |
|---|---|
| `GET /api/v8/lan/browser/pub/` | Liste tous les hôtes LAN |
| `PUT /api/v8/lan/browser/pub/{id}` | Modifie un hôte (nom, type) |
| `POST /login/authorize` | Demande de token applicatif |
| `POST /login/session` | Ouverture de session (HMAC-SHA1) |

---

## Compatibilité Freebox

| Modèle | Testé |
|---|---|
| Freebox Ultra | ✅ |
| Freebox Revolution | ✅ |
| Freebox Pop | ✅ |
| Freebox Delta | ✅ |
| Freebox mini 4K | ✅ |

---

## Contribuer

Les contributions sont les bienvenues !

1. Fork le dépôt
2. Crée une branche : `git checkout -b feature/ma-fonctionnalite`
3. Committe : `git commit -m "feat: ma fonctionnalité"`
4. Push : `git push origin feature/ma-fonctionnalite`
5. Ouvre une Pull Request

---

## Licence

MIT — voir [LICENSE](LICENSE)
