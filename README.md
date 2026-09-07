# Support-Ticket-AI

Kleine Anwendung zur automatisierten Analyse eingehender Support-Anfragen: Kategorie, Priorität, zuständiges Team und eine kurze Zusammenfassung werden bestimmt, kritische Anfragen als `manual_review_required` markiert, und das Ergebnis persistiert.

**Live:** `<TBD nach Deployment>`
**API-Doku (Swagger):** `<TBD>/docs`

## Nutzung

### Ticket einreichen

```bash
curl -X POST https://<live-url>/api/tickets \
  -H "Content-Type: application/json" \
  -d '{"request": "Seit heute Morgen ist das Produktivsystem nicht erreichbar."}'
```

Antwort:

```json
{
  "ticketId": "T-49d1ec",
  "category": "incident",
  "priority": "critical",
  "assignedTeam": "platform-operations",
  "summary": "Seit heute Morgen ist das Produktivsystem nicht erreichbar.",
  "status": "manual_review_required",
  "analysisMethod": "simulated",
  "createdAt": "2026-09-07T08:22:00.006328"
}
```

### Ergebnis abrufen

```bash
curl https://<live-url>/api/tickets/T-49d1ec
```

Zusätzlich: `GET /api/tickets?status=manual_review_required` (Liste, optional gefiltert) und `GET /health` (DB-Healthcheck, für das Railway-Deployment).

Alle drei Beispielanfragen aus der Aufgabenstellung wurden manuell gegen die laufende Anwendung getestet (siehe `tests/test_ai_service.py` und `tests/test_api.py` für die automatisierten Varianten davon).

### Lokal starten

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # optional: OPENAI_API_KEY eintragen
uvicorn app.main:app --reload
```

Ohne `OPENAI_API_KEY` läuft die Anwendung vollständig mit der regelbasierten (simulierten) Klassifikation — kein externer Service nötig. Ohne `DATABASE_URL` wird automatisch eine lokale SQLite-Datei (`local.db`) verwendet.

### Tests

```bash
pytest
```

Die Tests laufen deterministisch: `conftest.py` erzwingt `AI_PROVIDER=simulated` und eine isolierte temporäre SQLite-DB, damit keine echten API-Kosten anfallen und lokale `.env`-Werte die Tests nicht beeinflussen.

## Verwendete Technologien

- **Python 3.11 / FastAPI** — REST-API, automatische OpenAPI-Doku unter `/docs`.
- **SQLAlchemy 2.x** (typed ORM) — Persistenz; **PostgreSQL** auf Railway (via Railway-Postgres-Plugin), lokal automatischer **SQLite**-Fallback ohne Zusatzaufwand.
- **OpenAI API** (`gpt-4o-mini`, strukturierte Ausgabe via `json_schema` mit `strict: true`) als eine Stufe der Klassifikation.
- **pytest** für automatisierte Tests, **GitHub Actions** für CI (führt die Tests bei jedem Push aus).
- **Docker** + **Railway** (`railway.json`, Dockerfile-Build, Healthcheck) für das Deployment.

## Wichtigste Annahmen und Entscheidungen

- **Zweistufige Klassifikation statt reiner LLM-Anbindung:** `POST /api/tickets` versucht zuerst OpenAI; schlägt der Aufruf fehl (kein Key, Rate-Limit, Netzwerkfehler, ungültige Antwort) oder ist kein Key gesetzt, greift automatisch eine deterministische, regelbasierte ("simulierte AI") Klassifikation. Dadurch liefert die API **immer** ein valides Ergebnis, unabhängig von der Verfügbarkeit externer Dienste — für eine Support-Pipeline halte ich das für wichtiger als eine reine "LLM oder nichts"-Lösung. Welche Stufe tatsächlich gegriffen hat, wird transparent im Feld `analysisMethod` zurückgegeben.
- **Taxonomie:** Kategorien `incident`, `account_access`, `billing`, `how_to`, `general`; Prioritäten `critical`, `high`, `medium`, `low`; feste Kategorie→Team-Zuordnung (z. B. `incident` → `platform-operations`). Damit reproduziert die Anwendung exakt das in der Aufgabenstellung vorgegebene Beispiel (T-1004).
- **`manual_review_required`-Regel:** `priority == critical`, oder `category == incident` mit `priority == high`. Bewusst einfach und im Code (`compute_status`) nachvollziehbar, statt einer Blackbox-Heuristik.
- **Regelbasierte Komponente:** zweisprachige (DE/EN) gewichtete Keyword-Erkennung für Kategorie und Priorität — bewusst einfach und vollständig nachvollziehbar/testbar, kein Modell-Training nötig. Sie liefert keine echte Übersetzung/Zusammenfassung (die Summary ist bei dieser Stufe der — ggf. gekürzte — Originaltext), während die LLM-Stufe eine echte englische Kurzzusammenfassung erzeugt. Dieser Unterschied ist bewusst in Kauf genommen und im Code kommentiert.
- **Postgres statt SQLite in Produktion:** Railways Dateisystem ist nicht persistent über Redeploys hinweg — reines SQLite würde die Anforderung "Ergebnis in einer Datenbank speichern" auf der Live-Deployment nicht zuverlässig erfüllen. Lokal bleibt SQLite als Zero-Setup-Fallback erhalten.
- **Ticket-ID:** kurzes zufälliges Format `T-<hex>` statt fortlaufender ID, um keine Rückschlüsse auf das Ticketvolumen zuzulassen.
- **Bewusst nicht umgesetzt** (siehe unten): Auth, Rate-Limiting, PATCH/Status-Übergänge — um den Rahmen der Aufgabe (Zeitbudget ~2h) nicht zu sprengen.

## Eingesetzte AI-/Recherchewerkzeuge

- **Claude Code** (Anthropic) für Architektur, Implementierung, Tests und Deployment-Konfiguration dieser Lösung.
- **OpenAI API** (`gpt-4o-mini`) als produktive Klassifikationsstufe der Anwendung selbst (siehe oben) — nicht nur als Entwicklungswerkzeug, sondern Teil der ausgelieferten Lösung.

## Mit mehr Zeit

- Authentifizierung (z. B. API-Key oder JWT) für die Endpunkte.
- Rate-Limiting (aktuell keines — für eine öffentlich erreichbare Demo-API vertretbar, für echten Produktivbetrieb nicht).
- `PATCH /api/tickets/{id}` für Status-Übergänge (z. B. `open` → `resolved`) und ein einfaches Review-Workflow für `manual_review_required`-Tickets.
- Retry/Backoff und Timeout-Tuning für den OpenAI-Call statt einfachem Single-Shot-Try/Except.
- Strukturiertes Logging (JSON, Request-IDs) statt einfacher `logging`-Ausgabe.
- Alembic-Migrationen statt `create_all()` für echte Schema-Evolution.
- Konfidenz-Score statt binärer `manual_review_required`-Flag, ggf. mit Schwellenwert-Konfiguration.
- Benachrichtigung (z. B. Slack/E-Mail-Webhook) bei `manual_review_required`.
- Ein einfaches Dashboard/Frontend zur Anzeige/Filterung der Tickets statt reiner REST-API.
- Breitere automatisierte Testabdeckung für mehrsprachige/mehrdeutige Eingaben und einen echten End-to-End-Test gegen die OpenAI-API (aktuell aus Kostengründen nur die simulierte Stufe automatisiert getestet).
