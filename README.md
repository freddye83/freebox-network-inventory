# Freebox Network Inventory

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![HA Version](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-blue)](https://www.home-assistant.io/)

Complément à l'intégration officielle Freebox, orienté **inventaire réseau** plutôt que présence.

---

## Pourquoi cette intégration ?

L'intégration officielle Freebox crée des `device_tracker` pour la détection de présence.  
Ce besoin est très différent d'un **inventaire réseau** : connaître tous les équipements connectés, leur IP, leur interface, leur fabricant, les détecter automatiquement à leur apparition.

---

## Fonctionnalités

- ✅ **Un Device HA par adresse MAC** (visible dans Paramètres → Appareils)
- ✅ **Capteurs par équipement** : IPv4, IPv6, fabricant, interface, type de connexion, hostname, dernière activité, dernière présence
- ✅ **Capteur binaire** : en ligne / hors ligne
- ✅ **Capteurs globaux** : total, en ligne, hors ligne, nouveaux
- ✅ **Notification automatique** lors de la détection d'un nouvel équipement
- ✅ **Événement HA** `freebox_network_inventory_new_device` utilisable dans les automatisations
- ✅ **Page Diagnostics** intégrée
- ✅ **Config Flow** (pas de YAML)
- ✅ **Intervalle configurable** (10–3600 s, défaut 60 s)
- ✅ **Traductions FR/EN**
- ✅ Compatible Home Assistant 2024.1+

---

## Installation via HACS

1. Ouvrez HACS dans votre HA
2. Cliquez sur **Intégrations** → menu 3 points → **Dépôts personnalisés**
3. Ajoutez l'URL de ce dépôt, catégorie **Intégration**
4. Recherchez **Freebox Network Inventory** et installez
5. Redémarrez Home Assistant

---

## Configuration

1. Allez dans **Paramètres → Appareils et services → Ajouter une intégration**
2. Recherchez **Freebox Network Inventory**
3. Saisissez l'adresse de votre Freebox (`mafreebox.freebox.fr` par défaut)
4. **Appuyez sur le bouton fléché** sur l'écran LCD de la Freebox pour valider l'accès
5. Cliquez sur **Soumettre** dans HA

---

## Structure des entités

Chaque équipement réseau crée un Device HA avec :

```
Samsung TV (aa:bb:cc:dd:ee:ff)
├── binary_sensor.en_ligne
├── sensor.adresse_ipv4
├── sensor.adresse_ipv6
├── sensor.fabricant
├── sensor.interface
├── sensor.derniere_activite
├── sensor.derniere_presence
├── sensor.type_de_connexion
└── sensor.nom_d_hote
```

Plus trois capteurs globaux sur un device « Hub » :

```
Freebox Network Inventory (Hub)
├── sensor.appareils_en_ligne
├── sensor.total_appareils
└── sensor.nouveaux_appareils
```

---

## Notification nouveaux équipements

Quand un équipement inconnu apparaît sur le réseau, HA crée automatiquement une notification persistante :

> **🔍 Nouvel équipement réseau détecté**  
> Nom : ESP32 Garage  
> MAC : AA:BB:CC:DD:EE:FF  
> Fabricant : Espressif  
> IP : 192.168.1.85  
> Interface : wlan0

Un événement `freebox_network_inventory_new_device` est également déclenché, exploitable dans les automatisations :

```yaml
trigger:
  - platform: event
    event_type: freebox_network_inventory_new_device
action:
  - service: notify.mobile_app_mon_telephone
    data:
      title: "Nouvel appareil réseau"
      message: "{{ trigger.event.data.name }} ({{ trigger.event.data.mac }})"
```

---

## Diagnostics

Accédez à **Paramètres → Appareils et services → Freebox Network Inventory → Télécharger les diagnostics** pour obtenir :

```
Total devices : 43
Online        : 31
Offline       : 12
Ethernet      : 8
WiFi          : 35
Unknown vendor: 2
```

---

## API Freebox utilisée

- Endpoint : `GET /api/v8/lan/browser/pub/`
- Authentification : token applicatif (HMAC-SHA1)
- Aucun `device_tracker` créé

---

## Licence

MIT
