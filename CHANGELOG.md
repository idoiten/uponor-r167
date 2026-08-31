# Changelog

Alla nämnvärda ändringar i det här projektet dokumenteras här.
Formatet följer i stort [Keep a Changelog](https://keepachangelog.com/),
och projektet strävar efter [Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-08-31

Första fungerande versionen.

### Tillagt
- `climate`-entitet per rum, med `Current action` (Heating/Idle) baserat på
  enhetens egen "room in demand"-status.
- Temperatursensor per rum.
- Systemsensorer: utetemperatur och medelinomhustemperatur.
- Larm-/diagnostiksensorer per rum: tekniskt larm, manipulationslarm,
  radiolarm, lågt batteri, fuktgräns, golvgräns.
- API-status-sensor (visar om senaste anropet mot enheten misslyckades).
- Snabb bekräftelse efter temperaturändring: pollar det ändrade rummet
  var 5:e sekund (upp till 2 minuter) tills `Current action` faktiskt
  ändras, istället för att vänta på nästa ordinarie pollning.
- Egen enhet per rum, grupperad under en gemensam gateway-enhet.
- Konfigurerbar `max_channels` och `scan_interval` via integrationens
  Options Flow (Konfigurera-knappen), ingen ominstallation krävs.
- Stöd för HACS.
