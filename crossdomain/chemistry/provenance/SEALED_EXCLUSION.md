# Versiegelte Vorhersage III — Exklusion

**Geschrieben vor dem Einbau. Nicht mehr verändern.**

Datum: 2026-08-26
Grammatikstand: v5 (c020)
Anlass: ein Cross-Domain-Test gegen Chemie hat einen zweiten fehlenden
Operator angezeigt.

---

## Woher der Kandidat kommt

Die Grammatik kann Zustandsklassen aufspannen und mit `op_degenerate`
angeben, **wie viele äquivalente Zustände existieren**.

Sie kann nicht ausdrücken, **wie viele identische Träger denselben
Zustand besetzen dürfen**.

Das sind zwei verschiedene Fragen:

```
DEGENERACY:  wie viele gleichwertige Zustaende gibt es?
OCCUPANCY:   wie viele Traeger passen in EINEN Zustand?
```

**Einschränkung, die mitversiegelt wird:** dass Chiralität die
Dualitätssignatur erfüllt, ist eine **Lesart**, keine Messung. Prüfbar ist
nur das Fehlen von Exklusion, und das wird vor dem Einbau formal
nachgewiesen.

## Die Signatur, vor dem Einbau festgelegt

```
E : (Zustandsklasse, Traegeridentitaet) -> N_max

N_max = 1     Traeger schliessen einander aus
N_max = inf   Traeger duerfen sich haeufen
```

Kein Domäneninhalt. Kein Spin, keine Quantenzahl, kein Orbital. Nur eine
obere Schranke für die Belegung.

## Die Vorhersage

Wird E mit dieser Signatur eingebaut, erzeugt der Physikgraph Strukturen,
die v5 nicht erreichen konnte, und mindestens eine davon entspricht
bekannter Physik.

## Was als Widerlegung gälte

E erzeugt nur Duplikate, oder alle neuen Strukturen bleiben ohne
Entsprechung, oder E lässt sich als Komposition der vorhandenen Operatoren
darstellen.

## Einschränkung zum Dreieckstest

Der vorgeschlagene Test lautet: hilft D auch außerhalb der
Kodierungstheorie, hilft E auch außerhalb der Chemie.

**Das ist so nicht messbar.** Es existiert nur eine Vergleichsdatenbank,
die für Physik. Für Kodierungstheorie und Chemie gibt es keine — und würde
ich sie jetzt schreiben, schriebe ich sie gegen die bereits bekannten
Antworten.

Messbar ist genau eine Richtung:

```
erzeugt E neue Strukturen im PHYSIKgraphen,
die v5 nicht erreichte und die bekannter Physik entsprechen?
```

Das wird geprüft. Der volle Dreieckstest wird ausdrücklich als **offen**
markiert, nicht als bestanden.

## Verfahrensregel

1. Formal prüfen, ob die Basis Belegungsschranken ausdrücken kann.
2. Nur bei nachgewiesener Unmöglichkeit einbauen.
3. E bekommt keine Domäneninhalte.
4. Erst nach dem Lauf nachschlagen.
