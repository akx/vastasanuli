# Vastasanuli

Vastasanuli pelaa [SANULI](https://sanuli.fi/) ([@Cadiac/sanuli](https://github.com/Cadiac/sanuli)) -peliä.

Se ei aina voita.

## Käyttö

* Tarttet Pythonin (3.8+).
* Aja `make` (tai lataa `words.txt` [muualta](https://github.com/akx/fi-words/))
* Asentele vaadittavat paketit (`playwright`) requirements.in:stä tai requirements.txt:stä.
* Aja `playwright install`.
* Aja `vastasanuli.py` kovaa.
  `-n`-argumentti määrittää, pelaako Vastasanuli 5- vai 6-kirjaimista peliä. (Ks. `--help`.)
