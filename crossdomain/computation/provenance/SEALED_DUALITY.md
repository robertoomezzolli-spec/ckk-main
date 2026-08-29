# Versiegelte Vorhersage II — Dualität

**Geschrieben vor dem Rücktest gegen Physik. Nicht mehr verändern.**

Datum: 2026-08-26
Grammatikstand: v4 (c018)
Anlass: ein Cross-Domain-Test gegen Kodierungstheorie hat einen fehlenden
Operator angezeigt, dessen Signatur feststeht, bevor er eingebaut wird.

---

## Woher der Kandidat kommt

Die eingefrorene Physikgrammatik wurde auf Kodierungstheorie gelesen.
Sechs Operatoren haben dort eine natürliche Entsprechung. Einer fehlt:
die Dualität C → C^⊥.

**Wichtige Einschränkung, die mit versiegelt wird:** die sechs
Entsprechungen sind eine **Lesart**, keine Messung. Niemand hat gerechnet,
dass RECURRENCE zyklische Verschiebung *ist*. Der einzige prüfbare Teil
des Cross-Domain-Tests ist das **Fehlen** — und das wird vor dem Einbau
formal nachgewiesen, nicht behauptet.

## Die Signatur, vor dem Einbau festgelegt

```
D : X -> X*
D(D(X)) = X            Involution
D(X) = X   moeglich    Selbstdualitaet als Fixpunkt
```

Das ist ein anderer Fixpunkttyp als Closure:

```
Closure:        T^n X = X    Wiederkehr nach n Schritten
Dualitaet:      D^2 X = X    Wiederkehr nach zwei
Selbstdual:     D X = X      Fixpunkt in einem Schritt
```

## Die Vorhersage

Wird D mit dieser Signatur eingebaut — **ohne** kodierungstheoretische
oder physikalische Inhalte — dann wird der Physikgraph Strukturen
erzeugen, die v4 nicht erreichen konnte.

## Was als Bestätigung gälte

Mindestens eine neu erzeugte Struktur entspricht bekannter Physik, die
vorher unerreichbar war, **und** die Zuordnung wird erst nach dem Lauf
nachgeschlagen.

## Was als Widerlegung gälte

D erzeugt nur Duplikate bereits vorhandener Strukturen, oder alle neuen
Strukturen bleiben ohne Entsprechung.

## Was ausdrücklich NICHT als Bestätigung gilt

- Dass D in der Physik vorkommt. Elektromagnetische Dualität,
  Teilchen-Loch-Symmetrie und Kramers-Wannier sind bekannt. Der Test
  betrifft, ob die **Grammatik** dadurch etwas erreicht, was sie vorher
  nicht erreichte.
- Dass die sechs Cross-Domain-Entsprechungen gut aussehen. Das ist
  Interpretation.

## Verfahrensregel

1. Zuerst formal prüfen, ob die vorhandene Basis eine Involution
   erzeugen kann. Wie bei `sq`: Quellcodeanalyse plus erschöpfende
   Synthese, nicht Stichprobe.
2. Nur bei nachgewiesener Unmöglichkeit einbauen.
3. D bekommt **keine** Domäneninhalte, nur D² = I.
4. Erst nach dem Lauf wird nachgeschlagen, was die neuen Strukturen sind.
