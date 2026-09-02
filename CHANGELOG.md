# Changelog

Alla nämnvärda ändringar i det här projektet dokumenteras här.
Formatet följer i stort [Keep a Changelog](https://keepachangelog.com/),
och projektet strävar efter [Semantic Versioning](https://semver.org/).

## [1.3.0] - 2026-09-02

### Tillagt
- **Skydd mot skräpdata vid uppstart: vänta och försök igen.**
  Rumsupptäckten (`discover_and_read`) körs nu upp till **5 försök**
  med **10 sekunders paus** mellan varje, om den misstänker skräpdata
  (t.ex. ett rum vars namn-fält innehöll något annat än ett giltigt
  textnamn, som "1.1") eller inte hittade några rum alls. Ett tomt
  fält (oanvänd kanal) räknas inte som skräp — bara ett fält som
  faktiskt innehöll något ogiltigt.
- Om alla 5 försök misslyckas ger integrationen upp helt istället för
  att starta med en ofullständig/felaktig bild av rummen — det
  triggar Home Assistants inbyggda `setup_retry`-mekanism, som
  fortsätter försöka automatiskt med stigande mellanrum.

## [1.2.1] - 2026-09-02

### Rättat
- **Rumsnamn kunde bli skräp om integrationen laddades om medan R-167
  själv fortfarande höll på att starta upp** (bekräftat via ett
  medvetet stresstest: nätverkskabeln drogs ur och sattes tillbaka,
  och integrationen laddades om innan enheten hunnit bli klar). Under
  det fönstret svarar enhetens webbserver, men med oinitierade
  default-värden istället för riktig data — vilket bland annat kunde
  döpa om ett riktigt rum (t.ex. Klädvård) till "1.1" i HA:s
  enhetsregister, eftersom koden godtog blint vilken icke-tom sträng
  som helst. Rena siffervärden (som "1.1", "1.3") avvisas nu explicit;
  ett rum med ett sådant "namn" hoppas över den sökningen istället för
  att skapas/döpas om till skräp.
- Samma stresstest gav också en orimlig temperaturavläsning (0,0°C för
  ett rum utan aktivt radio- eller batterilarm). Temperaturvärden på
  exakt **0,0°C avvisas nu också**, utöver det tidigare intervallfiltret
  (−30°C till 60°C) — ett golvvärmt rum ska aldrig visa exakt 0°C i
  praktiken, ett sådant värde är alltid skräpdata, inte en verklig
  avläsning.

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
