# Changelog

Alla nämnvärda ändringar i det här projektet dokumenteras här.
Formatet följer i stort [Keep a Changelog](https://keepachangelog.com/),
och projektet strävar efter [Semantic Versioning](https://semver.org/).

## [1.2.0] - 2026-09-02

### Rättat
- **Skydd mot skräpdata från enheten under instabila perioder** (t.ex.
  precis efter en fysisk omstart av R-167). Tidigare kunde en enstaka
  udda avläsning tolkas som "flera tusen grader" eller trigga falska
  larm samtidigt över hela huset. Nu:
  - Larm godtar bara exakt `0` eller `1` — allt annat blir "okänt"
    istället för falskt "på".
  - Temperaturvärden utanför ett rimligt intervall (−30°C till 60°C)
    avvisas och visas som "okänt" istället för det uppenbart felaktiga
    talet.
  - Startsökningen (som frågar ~300 objekt) delas nu upp i mindre
    omgångar om 40 objekt i taget, istället för ett enda stort anrop.
    Det är skonsammare mot enhetens svaga inbyggda webbserver och
    minskar risken att hela integrationen fastnar vid uppstart, även
    om webb-UI:t (som gör mindre anrop) fortsätter fungera som vanligt.

## [1.1.0] - 2026-08-31

### Rättat (viktigt!)
- **Larmen (tekniskt larm, manipulationslarm, radiolarm, batteri) läste
  fel property och visade därför aldrig ett riktigt larm.** De använde
  property `538` med omvänd logik (`1=OK`, `0=larm`) — men det var fel
  property helt och hållet. Bekräftat via Chrome DevTools mot enhetens
  egen webb-UI: det rätta är property **`662`**, med **rak** logik
  (`1=larm`, `0=OK`). Verifierat genom att fysiskt dra ur batteriet ur
  en termostat och jämföra mot ett känt OK-rum.
- Tidigare tester av `538` råkade alltid visa `1` (falskt "OK") eftersom
  många fält i API:t defaultar till `1`, vilket gav en missvisande
  bekräftelse av fel property.

## [1.0.3] - 2026-08-31

### Rättat
- Tog bort en felaktig dubblett av `hacs.json` som legat inne i
  `custom_components/uponor_r167/` (den ska bara ligga i repots
  rotmapp) — det var den verkliga orsaken till att HACS aldrig visade
  det uppdaterade namnet.

## [1.0.2] - 2026-08-31

### Ändrat
- Rättade `hacs.json`s namn från gamla "Uponor R-167 (U@home)" till "Uponor",
  så HACS-dashboarden visar rätt titel.

### Känt problem
- HACS-dashboarden visar "icon not available" trots att integrationen har
  en egen `brand/icon.png`. Det är en öppen bugg i HACS självt
  ([hacs/integration#5171](https://github.com/hacs/integration/issues/5171)) —
  ikonen fungerar redan korrekt på Integrationssidan och enhetssidorna i HA.

## [1.0.1] - 2026-08-31

### Tillagt
- Egen ikon (`brand/icon.png`, `brand/icon@2x.png`) som visas i HA:s
  integrationslista och på enhetssidorna, utan att behöva en PR mot
  home-assistant/brands (stöds från och med HA 2026.3).

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
