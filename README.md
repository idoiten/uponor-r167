# Uponor R-167 (U@home) för Home Assistant

Anpassad Home Assistant-integration för Uponor Smatrix Wave PLUS via
kommunikationsmodulen **R-167 (U@home)**. Bygger direkt på modulens lokala
JSON-RPC-API (`http://<IP>/api`), reverse-engineerat från grunden.

## Funktioner

- En `climate`-entitet per rum (termostatkanal), med `Current action`
  (Heating/Idle) baserat på enhetens egen "room in demand"-status.
- En temperatursensor per rum.
- Utetemperatur och medelinomhustemperatur (systemvärden).
- Larm/diagnostik per rum: tekniskt larm, manipulationslarm, radiolarm,
  lågt batteri, fuktgräns, golvgräns.
- En "API-status"-sensor som visar om senaste anropet mot enheten
  misslyckades.
- Snabb bekräftelse efter en temperaturändring: pollar det ändrade rummet
  var 5:e sekund (upp till 2 minuter) tills enhetens "room in demand"
  faktiskt ändras, istället för att vänta på nästa ordinarie pollning.
- Alla enheter grupperas snyggt: en gateway-enhet ("Uponor R-167") med
  varje rum som en egen underenhet.

## Installation

### Via HACS (rekommenderas)

1. HACS → Integrationer → meny (⋮) → **Anpassade repositories**.
2. Lägg till repo-URL:en, kategori **Integration**.
3. Sök upp "Uponor R-167" i HACS och installera.
4. Starta om Home Assistant.
5. Inställningar → Enheter och tjänster → Lägg till integration → sök
   "Uponor", ange IP-adressen till din R-167.

### Manuellt

Kopiera `custom_components/uponor_r167` till din
`<config>/custom_components/`-mapp, starta om HA, och lägg till
integrationen som ovan.

## Konfiguration

Under integrationens **Konfigurera**-knapp kan du i efterhand justera:
- **Max channels** – hur många interna kanalspår som söks igenom vid start
  (standard 30, räcker gott för de flesta installationer).
- **Scan interval** – hur ofta hela systemet pollas i sekunder (standard 60).

## Bakgrund

R-167:s API är inte officiellt dokumenterat av Uponor. Objekt-id:n och
egenskaper i den här integrationen är framtagna genom manuell
reverse-engineering (jämförelse av kända värden mot API-svar, brett sökande
efter BACnet-objektnamn via property 77, m.m.). Fungerar med en
Smatrix Wave PLUS-installation (X-165 + R-167); ej testad mot X-265/R-208.

## Ansvarsfriskrivning

Inofficiell integration, inte utvecklad eller stödd av Uponor. Används på
egen risk.
