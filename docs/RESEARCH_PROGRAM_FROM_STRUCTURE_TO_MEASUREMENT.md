# Forschungsprogramm: vom strukturellen Ursprung zur Messvorhersage

Arbeitsstand: 6. September 2026. Ausgangspunkt ist der vom Nutzer formulierte
gesamte Forschungsstrang. Das Ziel ist eine nachvollziehbare Ableitungskette von
minimalen Voraussetzungen zu mathematischen Beziehungen, bekannten Grenzfällen,
neuen quantitativen Erwartungen, Messungen und einer wissenschaftlichen Publikation.

Die Hypothese lautet, dass eine domänenfreie generative Strukturarchitektur
tragende Beziehungen der Natur rekonstruieren kann. Erfolg wird untersucht und
nicht vorausgesetzt. Ein erfolgloser oder unentscheidbarer Test wird ebenfalls
festgehalten. Vollständige Naturabdeckung ist derzeit keine definierte Messgröße.

## Verbindlicher Kern des Vorhabens

- Keine physikalischen Gesetze, biologischen Mechanismen, Agency-Ziele oder
  Zielgleichungen in Seeds, generative Operatoren oder deren Rückkopplung geben.
- Jede mathematische Zusatzannahme offen benennen. Domänenfreiheit bedeutet
  nicht Annahmefreiheit. Ein gewähltes Produkt, eine Gleichheitsrelation oder
  ein mathematisches Realisierungsmodell ist Teil der Voraussetzungen.
- Strukturelle Dimension, physikalische Raumdimension und gemessene Zeit nicht
  ohne eine explizite Abbildung gleichsetzen.
- Alle Eingänge jedes Ableitungsschritts erhalten und nachspielen. Die native
  Bedeutung von DIRECT/INHERITED muss vor ihrer Integration geprüft werden;
  lokale Auditlabels ersetzen sie nicht.
- Ein UNMATCHED ist zunächst ein fehlender Katalogeintrag. Für eine unbekannte
  messbare Naturbeziehung braucht es zusätzlich eine Gleichung und Messvorschrift.

## Die vollständige Kette und ihre Abnahmekriterien

| Stufe | Prüffähiges Ergebnis | Gegenwärtiger Stand |
| --- | --- | --- |
| Voraussetzungen und Ursprung | Exakte Seeds, Operatoren, Gleichheit und Versionsfingerprints | Vorhanden; mehrere getrennte experimentelle Dialekte |
| Strukturelle Erzeugung | Nachspielbare Zustände, Hyperkanten und Vergleiche | Vorhanden in den dokumentierten begrenzten Teilversuchen |
| Mathematische Realisierung | Explizite Objekte, Abbildungen und Relationen für generierte Strukturen; belegte Erhaltung der Operatorgesetze | Nicht allgemein implementiert |
| Gleichungen und Invarianten | Maschinenlesbare Ausdrücke mit Voraussetzungen und Nachweis, dass sie aus der Realisierung folgen | Für die behaupteten physikalischen Gesetze nicht nachgewiesen |
| Bekannte Physik | Unabhängige Fälle mit quantitativen Ergebnissen, Gültigkeitsbereichen und Gegenbeispielen | Newton/Einstein als externe Prüfziele; kein bestandener vollständiger Ableitungsnachweis in diesem Arbeitsstrang |
| Neue Vorhersage | Vor Datenvergleich eingefrorene Formel, Parameter, Messgröße, Unsicherheit und Widerlegungskriterium | Offen |
| Messung und Replikation | Unabhängige Daten oder Experiment, dokumentierte Abweichung, Replikationspaket | Offen |
| Paper | Nachweise, Neuheitsprüfung, Resultate einschließlich Gegenbefunden und vollständige Reproduzierbarkeit | Ein Methodenteil ist möglich; ein Paper über neue bestätigte Naturgesetze noch nicht |

## Erster konkreter Prüfstein: archivierter 4D-Quantum-Hall-Treffer

Der Run-34-Knoten 331 ist als PRODUCT d4 mit dem Katalogurteil REDISCOVERED und
der Bezeichnung „4D quantum Hall / second Chern number“ gespeichert. Sein exakter
Datensatz und die Quellreferenz stehen in
`audit/qhe4d-archived-claim-20260906.json`.

Die neue Prüfung erzeugt zuerst ohne Zielzugriff den unveränderten Python-Fächer
und validiert alle 4.491 Anwendungen. Erst anschließend wird der archivierte
Treffer gelesen. Seine kompakte Signatur wird exakt wiedergefunden:

`RECURRENCE(order=0) -> close -> CYCLE(d1) -> product -> PRODUCT(d2) -> product -> PRODUCT(d4)`

Alle binären Eingänge sind im Ergebnis explizit enthalten. Eine nachgeschaltete
Winding-Anwendung erreicht außerdem INTEGER d4. Diese neue Spur rekonstruiert
passende Zustände unter dem aktuellen Kernel; sie ersetzt nicht die verlorenen
Operatornamen der historischen snapshot_v6-Kanten.

Die angezeigte Chern-Formel stammt nachweislich aus dem konstanten Profil in
`site/physics-cards.js`. Der Karten-Code bezeichnet sie selbst als
`PHYSICS ANNOTATION`. Der getestete Export enthält den strukturellen Treffer,
aber keinen Rechennachweis dieser Formel. Das Fehlen eines Formel-Feldes ist kein
Unmöglichkeitsbeweis für eine spätere Rekonstruktion aus Relationen.

Reproduktion:

```bash
node scripts/audit-qhe-formula-origin.mjs
```

Das Resultat `audit/qhe-formula-origin-20260906.json` erhält das historische
Katalogurteil unverändert und listet die noch offenen Nachweise:

1. Mathematischer Träger und zulässige Abbildungen.
2. Konstruktion und Berechnung eines charakteristischen Invarianten unter
   ausdrücklich angegebenen Voraussetzungen und Normierungskonventionen.
3. Ableitung einer Antwortbeziehung und Zuordnung ihrer Größen zu Messungen.
4. Unabhängiger, vorab festgelegter Fall und geeignete Gegenbeispiele.

Für den späteren externen Vergleich sind quantitative Antworten relevant:
Price et al. leiten lineare und nichtlineare quantisierte Ströme aus einem
konkreten 4D-Modell und seiner Bandtopologie ab. Lohse et al. untersuchen eine
nichtlineare Antwort in einer topologischen Pumpe. Diese Arbeiten dienen hier
als externe Prüfquellen und wurden dem Generator nicht übergeben.
[Price et al., 2015](https://link.aps.org/doi/10.1103/PhysRevLett.115.195303),
[Lohse et al., 2017/2018](https://arxiv.org/abs/1705.08371).

## Nächster Forschungsschritt: eine überprüfbare mathematische Realisierung

Der nächste Schritt soll keine weitere bloße Knotenzählung sein. Er benötigt
ein kleines, vollständig ausführbares mathematisches Modell für eine vorhandene
Strukturfamilie, mit einem vom Kernel getrennten Realisierungsvertrag.

Ein begrenzter erster Kandidat sind die vorhandenen endlichen Rekurrenzen:
eine ausdrücklich deklarierte Realisierung durch endliche Permutationen,
Komposition durch ein ausdrücklich deklariertes gemeinsames Fortschalten und
Orbitberechnung durch tatsächliches Ausführen der Abbildungen. Die entstehenden
Perioden und Relationen werden berechnet. Sie werden nicht aus einem
physikalischen Ziel abgelesen. Diese Wahl ist eine Modellannahme und muss als
solche im Nachweis stehen; sie ist durch das bisherige Feld `order` allein nicht
erzwungen. Der Order-0-Zweig wird dadurch noch nicht realisiert.

Der erste Erfolg wäre ein vollständiger Nachweis vom strukturellen Backtrace
über konkrete Abbildungen zu einer berechneten Beziehung, einschließlich eines
Falles, den die alte kompakte Signatur nicht ausreichend beschreibt. Das ist
ein begrenzter mathematischer Schritt und noch kein Newton- oder Einstein-Test.

Erst danach wird geprüft, welche weiteren allgemeinen mathematischen
Unterscheidungen tatsächlich fehlen. Neue Begriffe dürfen nicht allein deswegen
zugelassen werden, weil sie eine bereits gewünschte physikalische Formel erzeugen.

## Von einer Formel zum Messprojekt

Für jeden Kandidaten wird ein externer Datensatz mit folgenden Angaben eingefroren:

- generierte Beziehung und vollständige Voraussetzungsliste;
- Abbildung der mathematischen Größen auf Messgrößen und Einheiten;
- Gültigkeitsbereich, freie Parameter und unabhängige Kalibration;
- numerische oder funktionale Vorhersage samt erwarteter Unsicherheit;
- geeignete Gegenmodelle, vorab festgelegte Auswertung und Scheiterkriterien;
- Kennzeichnung, welche Daten schon bei der Konstruktion bekannt waren.

Ein Daten-Fit allein ist keine unabhängige Vorhersage. Auch ein post-hoc
Katalogtreffer wird entsprechend gekennzeichnet. Newton, Einstein und Quantum
Hall müssen über konkrete Beziehungen und Grenzfälle geprüft werden; ihre Namen
sind keine numerischen Erfolgsmaße.

## Publikationsziel

Das erste belastbare Paper kann die domänenfreie Grammatik, mathematische
Realisierungen, Äquivalenzregeln, Provenienz und unabhängige Tests behandeln.
Eine neue Naturvorhersage wird erst als solche bezeichnet, wenn die Gleichung
und Messvorschrift vor dem entscheidenden Datenvergleich feststanden. Ein
bestätigtes neues Naturgesetz erfordert entsprechend weitergehende Evidenz und
unabhängige Prüfung. Autorenschaft und veröffentlichte Ansprüche richten sich
nach den tatsächlichen Beiträgen und Ergebnissen.

Die Entwicklungsarbeit bleibt auf dem separaten Branch. Historische Ergebnisse,
Produktionsdaten, Kernannahmen und externe Interpretationen werden nicht
nachträglich an einen gewünschten Erfolg angepasst.
