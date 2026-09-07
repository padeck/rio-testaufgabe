# Stellungnahme bezüglich der Umsetzung

Sehr geehrte Frau Martinez,

hier im Folgenden eine Stellungnahme bezüglich meiner Herangehensweise für die Testaufgabe. Da sowohl der Code, als auch die Readme KI-generiert sind möchte ich aus Transparenzgründen hier explizit darauf hinweisen, dass der folgende Text ohne jeglichen KI-Einsatz entstanden ist. Ich habe versucht mich möglichst an den vorgegebenen Zeitrahmen zu halten und mich deshalb bewusst versucht auf die geforderten Basisfunktionen zu beschränken. Dadurch, dass Claude sehr überzeugende Arbeit geleistet hat, möchte ich im Folgenden auch nochmal in eigenen Worten wiedergeben, wie ich die Zusammenhänge verstehe.

## Verwendeter Tech-Stack
Zur Umsetzung der Aufgabe wurde Claude verwendet. Hierfür habe ich Claude die Aufgabenstellung übergeben, zunächst im Planungsmodus, um gemeinsam mit Claude die bevorstehende Implementierung zu planen. Zunächst wurde der zu verwendende Tech-Stack ausgewählt. Als primärer Python-Dev stand dadurch die Programmiersprache bereits fest. Was Backend-Entwicklung angeht scheinen FastAPI, Django und Flask die Go-To-Tools zu sein. Für meine Anwendung habe ich mich für FastAPI entschieden, ohne hierfür eine starke Präferenz äußern zu wollen. Die verwendete Datenbank zum Persistieren der verarbeiteten Support Tickets ist PostgreSQL. 

Zur Verarbeitung der Support-Anfragen habe ich in einen API-Key von OpenAI mit 5$ aufgeladen zum Klassifizieren/Kategorisieren der Tickets. Ich habe mich für eine hybride Strategie entschieden, die bei fehlendem API-Key auf reine regelbasierte Strategie zurückgreift, um die Support-Tickets zu verarbeiten. Dazu später mehr.

## Die Anwendung

### main.py
Das Herzstück der Anwendung ist `main.py`, in der die geforderten API Endpunkte implementiert wurden. Zum Anlegen neuer Tickets gibt es einen POST-Endpunkt der über `/api/tickets`zu erreichen ist. In der Methode wird die übergebene Payload durch die KI analysiert, der Status bestimmt und anschließend ein Ticket-Objekt erstellt, das so in der angebundenen Datenbank persistiert werden kann. Darüber hinaus wurden zwei GET-API Endpunkte implementiert. Der erste API-Endpunkt dient zum Einsehen der Felder bei der Übergabe einer spezifischen Ticket-ID, die dem Ticket bei dessen Erstellung über den POST-Endpunkt zugeteilt wurde. Der zweite GET-API-Endpunkt dient zum Abfragen *aller* in der DB persistierten Support-Tickets.

### ai_service.py
Die AI-Komponente ist in `ai_service.py`implementiert. Der System-Prompt wurde ebenfalls durch Claude designed. Er beschreibt, dass die KI Anfragen auf Deutsch oder Englisch zu erwarten hat und diese entsprechend klassifizieren soll und anschließend mit einem validen JSON-Objekt antworten soll. Da für die Kategorien nichts konkret vorgegeben wurde hat Claude sich welche ausgedacht: 
- `incident` für Systemausfälle jeglicher Art
- `account_access` für fehlschlagende Logins oder anderweitige Account-Probleme
- `billing` für Rechnungen o.ä.
- `how_to` für Fragen wie man etwas erledigt
- `general` für alles andere das nicht durch die anderen Kategorien abgedeckt wird

Für die möglichen Werte der Priorität wird angenommen:
- `critical` für produktionsgefährdende Probleme
- `high` falls ein User aktiv vom Arbeiten abgehalten wird
- `medium` ein reales, aber nicht blockierendes Problem
- `low` eine Frage oder sonstiges Anliegen.

Basierend auf den möglichen oben genannten Kategorien wurden entsprechende Teams erfunden, die sich um die möglichen Support-Kategorien kümmern:
- `incident` platform-operations 
- `account_access` identity-operations
- `billing` finance-operations
- `how_to` customer-success
- `general` first-level-support

Um möglichst deterministische Ausgaben zu erhalten wird die Temperatur auf 0 gesetzt (kontrolliert die "Kreativität"). Das verwendete Modell ist `gpt-4o-mini`. Dem LLM wird ein Response-Schema mitgeliefert, um sicherzustellen, dass der Output am ende ein valides JSON-Objekt ist, das den oben genannten Anforderungen genügt. Das erzeugte JSON-Objekt wird anschließend programmatisch validiert um auch wirklich sicherzustellen, dass die Felder valide Werte enthalten, ansonsten liefert die Methode `None` zurück. Der Status eines Tickets wird beim Anlegen als `open`gekennzeichnet, außer die Priorität wurde zuvor als `critical` gekennzeichnet bzw. es handelt sich um einen `incident` mit `high` priority, dann wird das Support-Ticket als `manual_review_required` geflagged.

Das regelbasierte System schaut stattdessen nach bestimmten Schlüsselwörtern in der ursprünglichen Anfrage und vergibt so eine Kategorie und Priorität des Support-Tickets. Stehen in der Anfrage beispielsweise Texte wie "Wie kann ich ..." erkennt das regelbasierte System darin eine nicht sonderlich dringliche Anfrage. Bei Aussagen wie "Das Produktivsystem is ausgefallen" erkennt das regelbasierte System dagegen wichtige Schlagwörter wie "Produktivsystem" und "ausgefallen" und klassifiziert das Ticket mit der entsprechenden Dringlichkeit.

### config.py

Konfigurationsfile, dient hauptsächlich zum Laden des `.env` files in dem unter anderem der OpenAI API Key abgelegt ist, der natürlich nicht mit ins GitHub Repo committed werden darf.

### database.py

Konfiguriert SQLAlchemy und wählt entweder PostgreSQL oder lokales SQLite  als Fallback. Darüber hinaus werden hier DB Sessions verwaltet.

### models.py

Stellt dar wie Support-Tickets in der Datenbank abgelegt werden sollen.

### schemas.py

In `schemas.py` wird definiert wie die Ticket Daten aussehen müssen die in die API übergeben werden bzw. aus der API rausgehen.

## Deployment
Die Anwendung wurde auf Railway deployed, ohne an dieser Stelle eine starke Präferenz für Railway auszudrücken. Das Deployment ist über ein Dockerfile erfolgt, in dem die einzelnen Schritte für den Build definiert wurden: Installation von uv, Installation der Dependencies aus `uv.lock`, anschließend Kopieren des Anwendungscodes und finaler Sync.

Der eigentliche Deploy-Vorgang erfolgte über die Railway-CLI (`railway up`): Der lokale Projektstand wird dabei als Archiv direkt zu Railway hochgeladen und dort anhand des Dockerfiles gebaut. Es besteht also keine automatische Kopplung an GitHub — ein Push auf das Repository allein löst keinen neuen Deploy aus, dieser musste jeweils manuell über die CLI angestoßen werden.

Als Datenbank wurde über Railways Postgres-Plugin ein verwalteter Postgres-Dienst dem Projekt hinzugefügt. Die Verbindungs-URL wird von Railway selbst generiert und dem App-Service als Umgebungsvariable bereitgestellt. Zusätzlich wurden die Variablen `AI_PROVIDER` und `OPENAI_API_KEY` für den App-Service gesetzt. Für den öffentlichen Zugriff wurde die kostenlose, automatisch von Railway vergebene Subdomain genutzt. Für die Produktivumgebung wurde bewusst Postgres statt SQLite gewählt, da Railways Container-Dateisystem über Redeploys hinweg nicht persistent ist — eine lokale SQLite-Datei würde bei jedem Deploy verloren gehen.

## Tests
Unter `tests/` sind diverse Tests angelegt worden um unter anderem den vollen HTTP-Stack (Ticket anlegen und abrufen, 404 bei unbekannter ID, 422 bei ungültigem Request, usw.), als auch die Klassifikationslogik zu testen. Diese Tests verwenden zur Kosteneinsparung allerdings nicht den API-Key und setzen dadurch lediglich auf die regelbasierte Logik. Darüber hinaus wurde über GitHub-Actions dafür gesorgt, dass bei jedem Push automatisiert die Tests durchlaufen werden.