# Mt. Silver: walka z Redem

Projekt na przedmiot Komunikacja Człowiek-Komputer. Gra w dwóch trybach, tekstowym i graficznym, oparta na
jednej logice. Idziesz przez podnóże i jaskinię na szczyt Mt. Silver, zbierasz przedmioty i walczysz z Redem
z Pokémon HeartGold.

## Uruchomienie

Wymagany Python 3.10 lub nowszy. Tryb tekstowy nie potrzebuje żadnych bibliotek.

```bash
python3 main.py                  # tryb tekstowy (okno min. 132x44)

python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python main.py --gui   # tryb graficzny
```

Tryb wybiera się przy starcie. Oba korzystają z tego samego pliku `save.json`, więc grę zaczętą w terminalu
można kontynuować w oknie.

Testy: `python3 -m unittest discover tests`

## Sterowanie

| Klawisz | Działanie |
|---|---|
| Strzałki | chodzenie, wybór w menu |
| Enter lub spacja | zatwierdzenie, przyspieszenie tekstu |
| Esc | menu albo powrót |
| Wejście w obiekt | rozmowa, podniesienie przedmiotu, przejście, walka |
| Mysz (tryb graficzny) | klik pola mapy: gracz tam idzie; klik opcji menu; klik tekstu: dalej |

## Architektura

```text
core/         Reguły gry: encje, walka, obrażenia, mapa. Nie wie nic o ekranie ani plikach.
ports/        Kontrakty: IGameView (ekran) i IDataRepository (pliki).
adapters/     Implementacje portów: tui_view (curses), gui_view (PySide6), json_repository.
controller/   Scenariusz gry. Rozmawia z widokiem i plikami wyłącznie przez porty.
data/         Treść gry w JSON: Pokémony, ataki, przedmioty, mapy.
assets/       Sprite'y jako pliki tekstowe.
tools/        Jednorazowa zamiana sprite'ów PNG na pliki tekstowe.
main.py       Tworzy obiekty i łączy je ze sobą.
```

Zależności idą tylko do środka: `adapters` i `controller` znają `core`, a `core` nie zna nikogo.
Pilnuje tego `ArchitectureTests` w testach.

Trzy decyzje, które trzymają kod krótkim:

1. **Widok blokuje.** `view.choose(menu)` wraca dopiero po wyborze gracza, a `view.play(event)` po skończonej
   animacji. Kontroler czyta się więc jak scenariusz, bez automatu stanów. W GUI blokowanie to zagnieżdżona
   `QEventLoop`, dzięki czemu okno cały czas reaguje.
2. **Walka to generator zdarzeń.** Każdy `yield` w `BattleEngine` oddaje jedno zdarzenie (`HIT`, `HP`, `FAINT`…),
   a kontroler przekazuje je do widoku. Model jest w każdej chwili dokładnie w tym stanie, co ekran.
3. **Sprite to tekst.** Plik ma paletę i siatkę znaków, więc czyta go jedna krótka funkcja, bez dekodera PNG.

## Wymagania a realizacja

| Wymaganie | Realizacja |
|---|---|
| Architektura ułatwiająca przeniesienie logiki | porty i adaptery; GUI to nowy plik w `adapters`, logika bez zmian |
| Dwa tryby bez utraty danych | wspólny `save.json` i ta sama logika; tryb wybierany przy starcie |
| Menu obsługiwane strzałkami | wszystkie menu w obu trybach |
| Grafika ASCII i animacje | sprite'y 64x64 jako kolorowe pola ze znakami ASCII na krawędziach (albo półbloki), śnieg, pisanie tekstu, przejście do walki, efekty ataków |
| Odświeżanie tylko zmian | krok na mapie to dwa kafelki (ok. 190 bajtów), zmiana w menu to dwie opcje i opis |
| Opcje konfiguracji | szybkość tekstu, trudność, animacje, motyw, rodzaj grafiki |
| Zapis i odczyt danych | `save.json`: drużyna, plecak, pozycja, zebrane przedmioty, ustawienia, statystyki |
| Klawiatura i mysz w GUI | klik mapy z wyszukiwaniem trasy (BFS), przyciski, najazd kursorem |
| Animacje w GUI | płynny krok, spadek HP, atak, trafienie, omdlenie, przejścia między ekranami |

Jeśli sprite'y w trybie półbloków mają w terminalu poziome paski, to wina czcionki. Domyślny tryb ASCII działa
wszędzie, a półbloki najlepiej wyglądają w VS Code i iTerm2.

## Uproszczenia względem HeartGold

- Poziomy drużyny Reda są jak w grze na poziomach normalnym i trudnym, ale Red nie ma trzymanych przedmiotów.
- Ataki Reda są wpisane z pamięci, bo nie udało się ich potwierdzić w źródle. Rest u Snorlaxa zastąpiono atakiem Body Slam.
- Bazowe statystyki pochodzą z PokéAPI i są aktualne, więc mogą minimalnie różnić się od 4. generacji. Moc, celność i PP ataków są przeliczone na wartości z HeartGold.
- Sprite'y pochodzą z FireRed (natywnie 64x64), mimo że walka jest wzorowana na HeartGold.
- Bez zdolności, zmian statystyk, wzdrygnięcia i dezorientacji. Grad działa zawsze, a Blizzard zawsze trafia.
- Mapa jest uproszczona. Nie ma dzikich Pokémonów ani dźwięku.

## Zasoby

Dane i sprite'y Pokémonów (FireRed) pochodzą z PokéAPI, a sprite Reda z Pokémon Showdown. Pokémon to własność
Nintendo, Game Freak i Creatures, więc projekt służy tylko do celów zaliczeniowych. Nie publikuj go w otwartym repozytorium.
