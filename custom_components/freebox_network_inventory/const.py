"""Constants for Freebox Network Inventory."""

DOMAIN = "freebox_network_inventory"
MANUFACTURER = "Freebox Network Inventory"
VERSION = "1.2.0"

# Config entries
CONF_HOST = "host"
CONF_PORT = "port"
CONF_APP_TOKEN = "app_token"
CONF_SCAN_INTERVAL = "scan_interval"

# Defaults
DEFAULT_HOST = "mafreebox.freebox.fr"
DEFAULT_PORT = 443
DEFAULT_SCAN_INTERVAL = 60

# API
FREEBOX_APP_ID = "freebox_network_inventory"
FREEBOX_APP_NAME = "Freebox Network Inventory"
FREEBOX_APP_VERSION = "1.2.0"
FREEBOX_DEVICE_NAME = "Home Assistant"

FREEBOX_API_VERSION_URL = "/api_version"
FREEBOX_API_BASE = "/api/v{version}"
FREEBOX_LOGIN_URL = "/login"
FREEBOX_AUTHORIZE_URL = "/login/authorize"
FREEBOX_SESSION_URL = "/login/session"
FREEBOX_LAN_BROWSER_URL = "/lan/browser/pub/"
FREEBOX_DHCP_STATIC_LEASE_URL = "/dhcp/static_lease/"
FREEBOX_DHCP_CONFIG_URL = "/dhcp/config/"

# Data keys
DATA_COORDINATOR = "coordinator"
DATA_API = "api"
DATA_SWITCH_COORDINATOR = "switch_coordinator"

# Global sensor keys
SENSOR_DEVICES_ONLINE = "devices_online"
SENSOR_DEVICES_TOTAL = "devices_total"
SENSOR_DEVICES_NEW = "devices_new"
SENSOR_STATIC_LEASES = "static_leases"

# Device attribute keys
ATTR_MAC = "mac"
ATTR_ALIAS = "alias"
ATTR_PRIMARY_NAME = "primary_name"
ATTR_VENDOR = "vendor"
ATTR_REACHABLE = "reachable"
ATTR_ACTIVE = "active"
ATTR_PERSISTENT = "persistent"
ATTR_INTERFACE = "interface"
ATTR_IP_LIST = "ip_list"
ATTR_LAST_ACTIVITY = "last_activity"
ATTR_LAST_SEEN = "last_seen"
ATTR_CONNECTION_TYPE = "connection_type"
ATTR_HOST_TYPE = "host_type"
ATTR_STATIC_LEASE = "static_lease"
ATTR_STATIC_IP = "static_ip"
ATTR_STATIC_COMMENT = "static_lease_comment"

# Services
SERVICE_SET_STATIC_LEASE = "set_static_lease"
SERVICE_REMOVE_STATIC_LEASE = "remove_static_lease"

# Events
EVENT_NEW_DEVICE = f"{DOMAIN}_new_device"

# Storage
STORAGE_KEY = f"{DOMAIN}.known_devices"
STORAGE_VERSION = 1

# Host type labels
HOST_TYPE_LABELS: dict[str, str] = {
    "workstation":       "Ordinateur",
    "laptop":            "Ordinateur portable",
    "smartphone":        "Smartphone",
    "tablet":            "Tablette",
    "television":        "Téléviseur",
    "multimedia_device": "Multimédia",
    "nas":               "NAS / Serveur",
    "networking_device": "Équipement réseau",
    "freebox_player":    "Freebox Player",
    "freebox_wifi":      "Borne WiFi",
    "ip_camera":         "Caméra IP",
    "ip_phone":          "Téléphone IP",
    "vg_console":        "Console de jeu",
    "appliances":        "Électroménager",
    "thermostat":        "Thermostat / Clim",
    "light":             "Éclairage connecté",
    "other":             "Autre",
}
