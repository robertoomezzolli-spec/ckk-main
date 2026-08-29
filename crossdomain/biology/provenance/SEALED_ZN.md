# Versiegelte Vorhersage IV — endliche Rekurrenz Z_n

**Geschrieben vor dem Einbau. Nicht mehr verändern.**

Datum: 2026-08-26
Grammatikstand: v6 (c023)

---

## Woher der Kandidat kommt

Ein Cross-Domain-Test gegen Biologie. Leserahmen einer Nukleotidsequenz
sind 0, 1, 2 mod 3 — nach drei Basen ist man wieder im selben Rahmen.
Das ist ℤ₃, nicht 2π und nicht π.

**Einschränkung, mitversiegelt:** die biologischen Zuordnungen
— Komplementarität als Involution, 4³ = 64 — sind **Lesarten**. Prüfbar
ist nur, ob die Grammatik ℤ_n ausdrücken kann.

## Der Vorwurf an die eigene Konstruktion

Der Seed lautet `x ~ x+1` und wurde als "vollständige Rekurrenz"
bezeichnet. Das reicht topologisch für den Kreis und **vergisst die
diskrete Periodenordnung**.

Und `factor` ist in der Grammatik eine **Zeichenkette**, `"2pi"` oder
`"pi"`. Sie wird herumgereicht und nie berechnet. Das ist ein Behelf, kein
Strukturmerkmal.

Verdacht: was die Grammatik als π-Familie modelliert, ist in Wahrheit
ℤ₂-Struktur — und wurde mit einem String nachgebaut, weil das Primitiv
fehlte.

## Die Signatur, vor dem Einbau festgelegt

```
Seed:    x ~ x+n        endliche Rekurrenz der Ordnung n
Folge:   Z_n            fuer endliches n
         Z              fuer n -> unendlich
```

Kein Leserahmen, kein Codon, kein Basenpaar. Nur die Ordnung.

## Die Vorhersage

Wird ℤ_n eingebaut, dann gilt:

1. Die π-Familie wird als **ℤ₂-Struktur ableitbar**, statt über einen
   String-Behelf.
2. Es entstehen weitere endliche zyklische Klassen (ℤ₃, ℤ₄ …), die v6
   nicht erreichen konnte.
3. Mindestens eine davon entspricht bekannter Physik.

## Was als Widerlegung gälte

ℤ_n erzeugt die π-Familie **nicht** — dann war der String kein Behelf,
sondern trug etwas, das ℤ₂ nicht hat. Oder die neuen endlichen Klassen
bleiben ohne jede Entsprechung.

## Was ausdrücklich NICHT als Bestätigung gilt

Dass ℤ_n in der Physik vorkommt. ℤ₂-Klassifikationen, ℤ₃-Symmetrien und
Parafermionen sind bekannt. Der Test betrifft, ob die **Grammatik**
dadurch sauberer wird — konkret: ob `factor` als String verschwinden kann.

## Verfahrensregel

1. Formal prüfen, ob die Basis eine endliche Rekurrenzordnung ausdrücken
   kann.
2. Nur bei nachgewiesener Unmöglichkeit einbauen.
3. Danach prüfen, ob `op_halfclose` und `op_dirichlet` durch ℤ₂
   **ersetzbar** werden. Wenn ja, ist das eine Vereinfachung und die
   ersten beiden waren Behelfe.
4. Erst nach dem Lauf nachschlagen.
